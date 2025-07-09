# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
{
    "name": "FastApi JWT Ontinet",
    "summary": "Extends the functionality of Fastapi",
    "author": "Ontinet.com S.L.U.",
    "website": "https://www.ontinet.com",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "depends": [
        "fastapi",
        "auth_jwt",
    ],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/fastapi_jwt_data.xml",
        "views/fastapi_jwt_auth_view.xml",
        "views/fastapi_jwt_endpoint_view.xml",
    ],
    "external_dependencies": {"python": ["pydantic"]},
}
