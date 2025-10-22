# Gestión de usuarios y roles

El proyecto implementa un servicio en memoria para administrar usuarios, roles y menús asociados a cada rol. Los puntos clave del dominio son:

- Los usuarios pueden poseer uno o varios roles.
- Solo puede existir un único usuario con el rol de **super administrador**.
- Los menús disponibles para cada usuario se generan combinando los menús de todos sus roles sin duplicados.

El núcleo de la aplicación reside en `app/main.py`, donde la clase `RoleService` expone métodos de alto nivel para crear roles y usuarios, consultar información y obtener los menús visibles.

## Requisitos

- Python 3.11+

No se necesitan dependencias externas para usar la librería. Las pruebas se ejecutan con `pytest`, disponible como dependencia de desarrollo.

## Uso

```python
from app.main import RoleService
from app.schemas import RoleCreate, UserCreate

service = RoleService()

super_admin_role = next(role for role in service.list_roles() if role.is_super_admin)
service.create_user(UserCreate(name="Root", role_ids=[super_admin_role.id]))

ventas = service.create_role(RoleCreate(name="Ventas", menus=["dashboard", "clientes"]))
usuario = service.create_user(UserCreate(name="Ana", role_ids=[ventas.id]))

menus = service.list_my_menus(usuario.id)
print(menus.menus)
```

## Pruebas

```bash
pytest
```

