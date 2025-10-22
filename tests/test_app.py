from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import BadRequestError, NotFoundError, PermissionError, RoleService
from app.schemas import RoleCreate, UserCreate


@pytest.fixture()
def service() -> RoleService:
    return RoleService()


def _super_admin_role_id(service: RoleService) -> UUID:
    for role in service.list_roles():
        if role.is_super_admin:
            return role.id
    raise AssertionError("Debe existir un rol de super administrador por defecto")


def test_only_one_super_admin_user_is_allowed(service: RoleService) -> None:
    super_admin_role = _super_admin_role_id(service)
    service.create_user(UserCreate(name="Root", role_ids=[super_admin_role]))

    with pytest.raises(BadRequestError) as exc:
        service.create_user(UserCreate(name="Otro Root", role_ids=[super_admin_role]))
    assert "super administrador" in str(exc.value).lower()


def test_non_super_admin_can_only_view_self(service: RoleService) -> None:
    super_admin_role = _super_admin_role_id(service)
    super_admin = service.create_user(UserCreate(name="Root", role_ids=[super_admin_role]))

    manager_role = service.create_role(
        RoleCreate(name="Gerente", menus=["dashboard", "reportes"])
    )
    employee = service.create_user(UserCreate(name="Empleado", role_ids=[manager_role.id]))

    visible_users = service.list_users(employee.id)
    assert [user.id for user in visible_users] == [employee.id]

    with pytest.raises(PermissionError):
        service.get_user(employee.id, super_admin.id)


def test_super_admin_can_view_everyone(service: RoleService) -> None:
    super_admin_role = _super_admin_role_id(service)
    super_admin = service.create_user(UserCreate(name="Root", role_ids=[super_admin_role]))

    analyst_role = service.create_role(
        RoleCreate(name="Analista", menus=["dashboard", "analitica"])
    )
    analyst = service.create_user(UserCreate(name="Analista", role_ids=[analyst_role.id]))

    users = service.list_users(super_admin.id)
    assert {user.id for user in users} == {super_admin.id, analyst.id}

    fetched = service.get_user(super_admin.id, analyst.id)
    assert fetched.id == analyst.id


def test_menus_are_aggregated_by_roles(service: RoleService) -> None:
    super_admin_role = _super_admin_role_id(service)
    editor_role = service.create_role(
        RoleCreate(name="Editor", menus=["publicaciones", "comentarios"])
    )
    reviewer_role = service.create_role(
        RoleCreate(name="Revisor", menus=["comentarios", "moderacion"])
    )

    user = service.create_user(
        UserCreate(
            name="Editor Jefe",
            role_ids=[super_admin_role, editor_role.id, reviewer_role.id],
        )
    )

    menus = service.list_my_menus(user.id)
    assert menus.menus == ["admin", "publicaciones", "comentarios", "moderacion"]


def test_requesting_unknown_user_raises_not_found(service: RoleService) -> None:
    with pytest.raises(NotFoundError):
        service.list_users(UUID(int=1))


def test_creating_role_with_existing_name_is_rejected(service: RoleService) -> None:
    service.create_role(RoleCreate(name="Auditor", menus=["auditorias"]))

    with pytest.raises(BadRequestError) as exc:
        service.create_role(RoleCreate(name="auditor", menus=["reportes"]))

    assert "rol" in str(exc.value).lower()


def test_super_admin_role_cannot_be_created_twice(service: RoleService) -> None:
    with pytest.raises(BadRequestError) as exc:
        service.create_role(
            RoleCreate(name="Otro Root", menus=["todo"], is_super_admin=True)
        )

    assert "super" in str(exc.value).lower()


def test_creating_user_with_unknown_role_fails(service: RoleService) -> None:
    unknown_role = UUID(int=999)

    with pytest.raises(NotFoundError) as exc:
        service.create_user(UserCreate(name="SinRol", role_ids=[unknown_role]))

    assert "rol" in str(exc.value).lower()


def test_creating_user_requires_at_least_one_role(service: RoleService) -> None:
    with pytest.raises(BadRequestError) as exc:
        service.create_user(UserCreate(name="SinRol", role_ids=[]))

    assert "rol" in str(exc.value).lower()


def test_user_roles_are_deduplicated_preserving_order(service: RoleService) -> None:
    super_admin_role = _super_admin_role_id(service)
    editor_role = service.create_role(RoleCreate(name="Editor", menus=["editar"]))

    user = service.create_user(
        UserCreate(name="Editor", role_ids=[super_admin_role, editor_role.id, editor_role.id])
    )

    assert [role.id for role in user.roles] == [super_admin_role, editor_role.id]
