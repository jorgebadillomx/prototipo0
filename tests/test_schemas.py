from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas import RoleCreate, UserCreate, ValidationError


def test_role_create_normalization_trims_and_validates() -> None:
    role = RoleCreate(name="  Analista  ", menus=["  dashboard  "], is_super_admin=False)
    normalized = role.normalized()

    assert normalized.name == "Analista"
    assert normalized.menus == ["dashboard"]


@pytest.mark.parametrize(
    "name,minimum",
    [
        ("ab", 3),
        ("", 3),
    ],
)
def test_role_create_name_must_have_minimum_length(name: str, minimum: int) -> None:
    role = RoleCreate(name=name, menus=["dashboard"], is_super_admin=False)

    with pytest.raises(ValidationError):
        role.normalized()


def test_user_create_requires_role_ids_and_deduplicates() -> None:
    duplicated_role = UUID(int=1)
    payload = UserCreate(name="  Admin  ", role_ids=[duplicated_role, duplicated_role])
    normalized = payload.normalized()

    assert normalized.name == "Admin"
    assert normalized.role_ids == [duplicated_role]


def test_user_create_rejects_empty_roles() -> None:
    payload = UserCreate(name="Sin roles", role_ids=[])

    with pytest.raises(ValidationError):
        payload.normalized()


def test_user_create_requires_non_empty_name() -> None:
    duplicated_role = UUID(int=1)
    payload = UserCreate(name="   ", role_ids=[duplicated_role])

    with pytest.raises(ValidationError):
        payload.normalized()
