# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    device_ids = fields.One2many("res.device", "user_id", string="Devices")
    custom_field = fields.Boolean(
        string="Cerrar sesion automatica",
        help="Quieres que se te cierre la sesion automaticamente.",
        default=True,
    )
