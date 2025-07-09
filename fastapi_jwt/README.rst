.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
    :alt: License: LGPL-3

===========
Fastapi JWT
===========
Fastapi JWT is a FastAPI extension designed to integrate with Odoo, providing
secure API endpoints utilizing Bearer Token authentication.


Configuration and Installation
------------------------------

- Instalar el módulo en el servidor de Odoo
- Acceder dentro del panel de Ajustes y dentro de Usuarios y Compañias entrar en el módulo de Auth JWT, donde crearemos 
  un validador para generar tokens y otro para refrescar los tokens. 
- Luego entramos en el panel de control de FastApi donde crearemos el endpoint usando en el select la App de OntinetJwt,
  luego selecionamos el validador que hara referencia al endpoint.
- Luego probaremos a hacer una petición de Login para que nos genere los tokens, uno que es el token normal y otro el 
  refresh token par volver a generar tokens una vez caduquen. 
- En los endpoints protegidos utilizaremos el token normal para hacer la petición y una vez caduque utilizaremos 
  el endpoint de refresh par volver a generar un token y seguir haciendo peticiones.

**Ejemplo de peticición por curl:**

http://localhost:8069/ontinetjwt/login
```
curl --location 'url \
--header 'api-key: XXXXXX' \
--header 'Content-Type: application/json' \
--data '{ 
"email": "user@example.com",
"password": "example"
} '
```

Ejemplo de respuesta:

{ 
  "access_token": "---------------------", 
  "token_type": "bearer",
  "refresh_token": "-----------------" 
}


Contributors
------------

* Andreu Sempere Mico <asempere@practicas.ontinet.com>