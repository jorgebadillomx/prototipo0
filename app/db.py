from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, List, Optional, Union
from uuid import UUID, uuid4

from .schemas import Role, RoleCreate, User, UserCreate, UserRead


class DataStore:
    """SQLite-backed storage for users and roles."""

    def __init__(self, *, db_path: Optional[Union[str, Path]] = None) -> None:
        default_path = os.getenv("ROLE_SERVICE_DB_PATH", ":memory:")
        raw_path: Union[str, Path] = db_path if db_path is not None else default_path
        self._db_path = str(raw_path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self._db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            uri=self._db_path.startswith("file:"),
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()

    # Schema management -------------------------------------------------
    def _ensure_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    menus TEXT NOT NULL,
                    is_super_admin INTEGER NOT NULL CHECK (is_super_admin IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                );
                """
            )

    # Role helpers ------------------------------------------------------
    def _row_to_role(self, row: sqlite3.Row) -> Role:
        return Role(
            id=UUID(row["id"]),
            name=row["name"],
            menus=json.loads(row["menus"]),
            is_super_admin=bool(row["is_super_admin"]),
        )

    def ensure_super_admin_role(self) -> Role:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, name, menus, is_super_admin FROM roles WHERE is_super_admin = 1 LIMIT 1"
            )
            row = cursor.fetchone()
        if row is not None:
            return self._row_to_role(row)
        return self.create_super_admin_role()

    def create_super_admin_role(self) -> Role:
        role_id = uuid4()
        role = Role(id=role_id, name="Super Administrador", menus=["admin"], is_super_admin=True)
        with self._lock:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO roles (id, name, menus, is_super_admin) VALUES (?, ?, ?, ?)",
                    (str(role.id), role.name, json.dumps(role.menus), int(role.is_super_admin)),
                )
        return role

    # Roles -------------------------------------------------------------
    def create_role(self, payload: RoleCreate) -> Role:
        normalized = payload.normalized()
        with self._lock:
            cursor = self._connection.execute(
                "SELECT 1 FROM roles WHERE LOWER(name) = ?",
                (normalized.name.lower(),),
            )
            existing = cursor.fetchone()
        if existing:
            raise ValueError("Ya existe un rol con ese nombre")
        if normalized.is_super_admin:
            raise ValueError("No se permite crear más roles de super administrador")
        role = Role(
            id=uuid4(),
            name=normalized.name,
            menus=normalized.menus,
            is_super_admin=normalized.is_super_admin,
        )
        with self._lock:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO roles (id, name, menus, is_super_admin) VALUES (?, ?, ?, ?)",
                    (str(role.id), role.name, json.dumps(role.menus), int(role.is_super_admin)),
                )
        return role

    def list_roles(self) -> List[Role]:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, name, menus, is_super_admin FROM roles ORDER BY name"
            )
            rows = cursor.fetchall()
        return [self._row_to_role(row) for row in rows]

    def get_role(self, role_id: UUID) -> Role:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, name, menus, is_super_admin FROM roles WHERE id = ?",
                (str(role_id),),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError("Rol no encontrado")
        return self._row_to_role(row)

    # Users -------------------------------------------------------------
    def _role_is_super_admin(self, role_id: UUID) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT is_super_admin FROM roles WHERE id = ?",
                (str(role_id),),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError("Rol no encontrado")
        return bool(row["is_super_admin"])

    def _super_admin_user_exists(self) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT 1
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON r.id = ur.role_id
                WHERE r.is_super_admin = 1
                LIMIT 1
                """
            )
            return cursor.fetchone() is not None

    def create_user(self, payload: UserCreate) -> User:
        normalized = payload.normalized()
        missing_roles = []
        includes_super_admin = False
        for role_id in normalized.role_ids:
            try:
                if self._role_is_super_admin(role_id):
                    includes_super_admin = True
            except KeyError:
                missing_roles.append(role_id)
        if missing_roles:
            raise KeyError("Alguno de los roles no existe")
        if includes_super_admin and self._super_admin_user_exists():
            raise ValueError("Ya existe un usuario super administrador")

        user_id = uuid4()
        with self._lock:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO users (id, name) VALUES (?, ?)",
                    (str(user_id), normalized.name),
                )
                self._connection.executemany(
                    "INSERT INTO user_roles (user_id, role_id, position) VALUES (?, ?, ?)",
                    [
                        (str(user_id), str(role_id), index)
                        for index, role_id in enumerate(normalized.role_ids)
                    ],
                )
        return User(id=user_id, name=normalized.name, role_ids=normalized.role_ids)

    def _build_user_read(self, user: User) -> UserRead:
        roles = self._fetch_roles_for_user(user.id)
        return UserRead(id=user.id, name=user.name, roles=roles)

    def _fetch_roles_for_user(self, user_id: UUID) -> List[Role]:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT r.id, r.name, r.menus, r.is_super_admin
                FROM roles r
                JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = ?
                ORDER BY ur.position
                """,
                (str(user_id),),
            )
            rows = cursor.fetchall()
        return [self._row_to_role(row) for row in rows]

    def list_users(self) -> List[UserRead]:
        with self._lock:
            cursor = self._connection.execute("SELECT id, name FROM users ORDER BY name")
            user_rows = cursor.fetchall()
        users: List[UserRead] = []
        for row in user_rows:
            user = User(
                id=UUID(row["id"]),
                name=row["name"],
                role_ids=self._user_role_ids(UUID(row["id"])),
            )
            users.append(self._build_user_read(user))
        return users

    def _user_role_ids(self, user_id: UUID) -> List[UUID]:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT role_id FROM user_roles WHERE user_id = ? ORDER BY position",
                (str(user_id),),
            )
            rows = cursor.fetchall()
        return [UUID(row["role_id"]) for row in rows]

    def get_user(self, user_id: UUID) -> User:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, name FROM users WHERE id = ?",
                (str(user_id),),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError("Usuario no encontrado")
        role_ids = self._user_role_ids(user_id)
        return User(id=user_id, name=row["name"], role_ids=role_ids)

    def build_user_read(self, user: User) -> UserRead:
        return self._build_user_read(user)

    def is_super_admin(self, user_id: UUID) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT 1
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = ? AND r.is_super_admin = 1
                LIMIT 1
                """,
                (str(user_id),),
            )
            return cursor.fetchone() is not None

    def list_menus_for_user(self, user_id: UUID) -> List[str]:
        roles = self._fetch_roles_for_user(user_id)
        menus: List[str] = []
        seen = set()
        for role in roles:
            for menu in role.menus:
                if menu not in seen:
                    seen.add(menu)
                    menus.append(menu)
        return menus

    # Maintenance -------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            with self._connection:
                self._connection.execute("DELETE FROM user_roles")
                self._connection.execute("DELETE FROM users")
                self._connection.execute("DELETE FROM roles")

    def load_roles(self, roles: Iterable[Role]) -> None:
        with self._lock:
            with self._connection:
                for role in roles:
                    self._connection.execute(
                        """
                        INSERT INTO roles (id, name, menus, is_super_admin)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            menus = excluded.menus,
                            is_super_admin = excluded.is_super_admin
                        """,
                        (str(role.id), role.name, json.dumps(role.menus), int(role.is_super_admin)),
                    )

