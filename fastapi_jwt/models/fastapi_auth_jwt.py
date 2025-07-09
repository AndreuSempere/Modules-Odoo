# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from fastapi import HTTPException, status

from odoo import SUPERUSER_ID, api, fields, models
from odoo.http import request


class FastapiAuthJwt(models.Model):
    _inherit = "auth.jwt.validator"

    token_duration = fields.Integer(
        string="Duración del token", default=60, required=True
    )
    refresh_duration = fields.Integer(
        string="Duración del token", default=3600, required=True
    )
    signature_type = fields.Selection(
        selection_add=[("refresh", "refresh")],
        ondelete={"refresh": "cascade"},
        required=True,
    )

    def generate_jwt_token(self, user_id, validator_jwt):
        if not validator_jwt:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        env = api.Environment(request.cr, SUPERUSER_ID, {})
        user = env["res.users"].sudo().browse(user_id)
        expire = validator_jwt.token_duration
        payload = {
            "sub": str(user_id),
            "name": user.name,
        }

        token = validator_jwt._encode(payload, validator_jwt.secret_key, expire)
        return token
