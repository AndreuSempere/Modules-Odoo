{
    "name": "Res Device",
    "summary": "Gestión de dispositivos y sesiones en Odoo 17",
    "version": "17.0.1.0.0",
    "author": "Ontinet.com S.L.U.",
    "website": "https://www.ontinet.com",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "depends": [
        "base",
        "web",
    ],
    "data": [
        "security/base_security.xml",
        "security/ir.model.access.csv",
        "views/res_device_views.xml",
        "views/res_users_views.xml",
        "data/data_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "res_device/static/src/js/res_device.esm.js",
        ],
    },
}
