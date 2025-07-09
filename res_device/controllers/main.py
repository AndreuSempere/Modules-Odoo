# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ResDeviceController(http.Controller):
    @http.route("/web/session/update_device", type="json", auth="user")
    def update_device(self):
        _logger.info(
            "Device update requested for user ID: %s",
            request.session.uid if request.session else "No session",
        )

        if request and request.env:
            try:
                session_timeout_minutes = int(
                    request.env["ir.config_parameter"]
                    .sudo()
                    .get_param("res_device.session_timeout_minutes", default="30")
                )

                session_identifier = request.session.sid[:42]
                existing_device = (
                    request.env["res.device.log"]
                    .sudo()
                    .search(
                        [
                            ("session_identifier", "=", session_identifier),
                            ("user_id", "=", request.session.uid),
                        ],
                        limit=1,
                    )
                )

                if not existing_device:
                    request.env["res.device.log"]._update_device(request)
                    _logger.info(
                        "Device information updated successfully for user ID: %s",
                        request.session.uid,
                    )
                else:
                    _logger.info(
                        "Device already registered for user ID: %s, session: %s",
                        request.session.uid,
                        session_identifier,
                    )

                return {
                    "success": True,
                    "session_timeout_minutes": session_timeout_minutes,
                    "already_registered": bool(existing_device),
                }
            except Exception as e:
                _logger.error("Error updating device information: %s", str(e))
                return {"success": False, "error": str(e)}

        _logger.warning("Cannot update device: no request or environment")
        return {"success": False}
