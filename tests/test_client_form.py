from __future__ import annotations

from pathlib import Path


def test_client_form_contains_expected_fields() -> None:
    form_path = Path("app/templates/client_form.html")
    assert form_path.exists(), "El formulario de clientes debe existir"

    html = form_path.read_text(encoding="utf-8")
    required_fields = [
        "full_name",
        "email",
        "phone",
        "street",
        "city",
        "state",
        "postal_code",
        "status",
        "notes",
    ]
    for field in required_fields:
        assert f'name="{field}"' in html or f'id="{field}"' in html

    assert "Formulario para registrar clientes" in html
    assert "Guardar cliente" in html
