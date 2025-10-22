from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from .db import DataStore
from .schemas import MenusResponse, Role, RoleCreate, UserCreate, UserRead


class ServiceError(Exception):
    """Base class for domain-level errors."""


class NotFoundError(ServiceError):
    pass


class PermissionError(ServiceError):
    pass


class BadRequestError(ServiceError):
    pass


@dataclass
class RoleService:
    datastore: DataStore

    def __init__(self, datastore: Optional[DataStore] = None) -> None:
        self.datastore = datastore or DataStore()
        if not self.datastore.roles:
            self.datastore.create_super_admin_role()

    # Roles
    def create_role(self, payload: RoleCreate) -> Role:
        try:
            return self.datastore.create_role(payload)
        except ValueError as exc:  # duplicate name or super admin flag
            raise BadRequestError(str(exc)) from exc

    def list_roles(self) -> List[Role]:
        return self.datastore.list_roles()

    # Users
    def create_user(self, payload: UserCreate) -> UserRead:
        try:
            user = self.datastore.create_user(payload)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
        except KeyError as exc:
            raise NotFoundError("Rol no encontrado") from exc
        return self.datastore.build_user_read(user)

    def _get_current_user(self, user_id: UUID) -> UserRead:
        try:
            user = self.datastore.get_user(user_id)
        except KeyError as exc:
            raise NotFoundError("Usuario no encontrado") from exc
        return self.datastore.build_user_read(user)

    def list_users(self, requester_id: UUID) -> List[UserRead]:
        if self.datastore.is_super_admin(requester_id):
            return self.datastore.list_users()
        requester = self._get_current_user(requester_id)
        return [requester]

    def get_user(self, requester_id: UUID, user_id: UUID) -> UserRead:
        if requester_id != user_id and not self.datastore.is_super_admin(requester_id):
            raise PermissionError("No tienes permisos para ver este usuario")
        return self._get_current_user(user_id)

    def list_my_menus(self, requester_id: UUID) -> MenusResponse:
        self._get_current_user(requester_id)  # ensure it exists
        menus = self.datastore.list_menus_for_user(requester_id)
        return MenusResponse(menus=menus)

