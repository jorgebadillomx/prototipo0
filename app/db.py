from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from uuid import UUID, uuid4

from .schemas import Role, RoleCreate, User, UserCreate, UserRead


class DataStore:
    """Simple in-memory store for users and roles."""

    def __init__(self) -> None:
        self.roles: Dict[UUID, Role] = {}
        self.users: Dict[UUID, User] = {}
        self.super_admin_user_id: Optional[UUID] = None

    def create_super_admin_role(self) -> Role:
        role = Role(id=uuid4(), name="Super Administrador", menus=["admin"], is_super_admin=True)
        self.roles[role.id] = role
        return role

    def create_role(self, payload: RoleCreate) -> Role:
        normalized = payload.normalized()
        if any(role.name.lower() == normalized.name.lower() for role in self.roles.values()):
            raise ValueError("Ya existe un rol con ese nombre")
        if normalized.is_super_admin:
            raise ValueError("No se permite crear más roles de super administrador")
        role = Role(
            id=uuid4(),
            name=normalized.name,
            menus=normalized.menus,
            is_super_admin=normalized.is_super_admin,
        )
        self.roles[role.id] = role
        return role

    def list_roles(self) -> List[Role]:
        return list(self.roles.values())

    def get_role(self, role_id: UUID) -> Role:
        if role_id not in self.roles:
            raise KeyError("Rol no encontrado")
        return self.roles[role_id]

    def create_user(self, payload: UserCreate) -> User:
        normalized = payload.normalized()
        missing_roles = [role_id for role_id in normalized.role_ids if role_id not in self.roles]
        if missing_roles:
            raise KeyError("Alguno de los roles no existe")

        includes_super_admin = any(self.roles[role_id].is_super_admin for role_id in normalized.role_ids)
        if includes_super_admin:
            if self.super_admin_user_id is not None:
                raise ValueError("Ya existe un usuario super administrador")

        user = User(id=uuid4(), name=normalized.name, role_ids=normalized.role_ids)
        self.users[user.id] = user

        if includes_super_admin:
            self.super_admin_user_id = user.id

        return user

    def list_users(self) -> List[UserRead]:
        return [self._build_user_read(user) for user in self.users.values()]

    def get_user(self, user_id: UUID) -> User:
        if user_id not in self.users:
            raise KeyError("Usuario no encontrado")
        return self.users[user_id]

    def _build_user_read(self, user: User) -> UserRead:
        roles = [self.roles[role_id] for role_id in user.role_ids]
        return UserRead(id=user.id, name=user.name, roles=roles)

    def build_user_read(self, user: User) -> UserRead:
        return self._build_user_read(user)

    def is_super_admin(self, user_id: UUID) -> bool:
        try:
            user = self.get_user(user_id)
        except KeyError:
            return False
        return any(self.roles[role_id].is_super_admin for role_id in user.role_ids)

    def list_menus_for_user(self, user_id: UUID) -> List[str]:
        user = self.get_user(user_id)
        menus: List[str] = []
        for role_id in user.role_ids:
            role = self.roles[role_id]
            menus.extend(role.menus)
        # preserve order but remove duplicates
        seen = set()
        ordered: List[str] = []
        for menu in menus:
            if menu not in seen:
                seen.add(menu)
                ordered.append(menu)
        return ordered

    def reset(self) -> None:
        self.roles.clear()
        self.users.clear()
        self.super_admin_user_id = None

    def load_roles(self, roles: Iterable[Role]) -> None:
        for role in roles:
            self.roles[role.id] = role

