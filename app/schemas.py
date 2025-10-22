from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List
from uuid import UUID


class ValidationError(ValueError):
    """Raised when an incoming payload does not comply with the rules."""


def _normalize_name(raw: str, *, minimum: int, kind: str) -> str:
    name = raw.strip()
    if len(name) < minimum:
        raise ValidationError(f"El nombre del {kind} debe tener al menos {minimum} caracteres")
    return name


def _normalize_menus(raw_menus: Iterable[str]) -> List[str]:
    menus: List[str] = []
    for raw_menu in raw_menus:
        menu = raw_menu.strip()
        if not menu:
            raise ValidationError("Los menús no pueden estar vacíos")
        menus.append(menu)
    return menus


@dataclass(frozen=True)
class Role:
    id: UUID
    name: str
    menus: List[str] = field(default_factory=list)
    is_super_admin: bool = False


@dataclass
class RoleCreate:
    name: str
    menus: List[str]
    is_super_admin: bool = False

    def normalized(self) -> "RoleCreate":
        return RoleCreate(
            name=_normalize_name(self.name, minimum=3, kind="rol"),
            menus=_normalize_menus(self.menus),
            is_super_admin=self.is_super_admin,
        )


@dataclass
class User:
    id: UUID
    name: str
    role_ids: List[UUID] = field(default_factory=list)


@dataclass
class UserCreate:
    name: str
    role_ids: List[UUID]

    def normalized(self) -> "UserCreate":
        if not self.role_ids:
            raise ValidationError("El usuario debe tener al menos un rol asignado")
        unique_roles = list(dict.fromkeys(self.role_ids))
        return UserCreate(
            name=_normalize_name(self.name, minimum=1, kind="usuario"),
            role_ids=unique_roles,
        )


@dataclass(frozen=True)
class UserRead:
    id: UUID
    name: str
    roles: List[Role] = field(default_factory=list)


@dataclass(frozen=True)
class MenusResponse:
    menus: List[str] = field(default_factory=list)

