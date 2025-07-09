# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import logging
import os
from datetime import datetime, timedelta

from odoo import _, api, fields, models, tools
from odoo.http import GeoIP, request, root
from odoo.tools import SQL, OrderedSet, unique

_logger = logging.getLogger(__name__)


class ResDeviceLog(models.Model):
    _name = "res.device.log"
    _description = "Device Log"
    _rec_names_search = ["platform", "browser"]

    session_identifier = fields.Char(required=True, index="btree")
    platform = fields.Char()
    browser = fields.Char()
    ip_address = fields.Char()
    country = fields.Char()
    city = fields.Char()
    device_type = fields.Selection(
        [("computer", "Computer"), ("mobile", "Mobile")], "Device Category"
    )
    user_id = fields.Many2one("res.users", index="btree")
    first_activity = fields.Datetime()
    last_activity = fields.Datetime(index="btree")
    revoked = fields.Boolean(
        help="""If True, the session file corresponding to this device
                                    no longer exists on the filesystem.""",
    )
    is_current = fields.Boolean("Current Device", compute="_compute_is_current")
    linked_ip_addresses = fields.Text(
        "Linked IP address", compute="_compute_linked_ip_addresses"
    )

    def init(self):
        self.env.cr.execute(
            SQL(
                """
            CREATE INDEX IF NOT EXISTS res_device_log__composite_idx
            ON %s(user_id,
            session_identifier,
            platform,
            browser,
            last_activity,
            id)
            WHERE revoked = False
        """,
                SQL.identifier(self._table),
            )
        )

    def _compute_display_name(self):
        for device in self:
            platform = device.platform or _("Unknown")
            browser = device.browser or _("Unknown")
            device.display_name = f"{platform.capitalize()} {browser.capitalize()}"

    def _compute_is_current(self):
        for device in self:
            device.is_current = request and request.session.sid.startswith(
                device.session_identifier
            )

    def _compute_linked_ip_addresses(self):
        device_group_map = {}
        for *device_info, ip_array in self.env["res.device.log"]._read_group(
            domain=[("session_identifier", "in", self.mapped("session_identifier"))],
            groupby=["session_identifier", "platform", "browser"],
            aggregates=["ip_address:array_agg"],
        ):
            device_group_map[tuple(device_info)] = ip_array
        for device in self:
            device.linked_ip_addresses = "\n".join(
                OrderedSet(
                    device_group_map.get(
                        (device.session_identifier, device.platform, device.browser), []
                    )
                )
            )

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        if field_name == "is_current" and request:
            return SQL("session_identifier = %s DESC", request.session.sid[:42])
        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    def _is_mobile(self, platform):
        if not platform:
            return False
        mobile_platform = [
            "android",
            "iphone",
            "ipad",
            "ipod",
            "blackberry",
            "windows phone",
            "webos",
        ]
        return platform.lower() in mobile_platform

    @api.model
    def _update_device(self, request):
        """
        Must be called when we want to update the device for the current request.
        Passage through this method must leave a "trace" in the session.

        :param request: Request or WebsocketRequest object
        """
        trace = request.session.update_trace(request)
        if not trace:
            return

        geoip = GeoIP(trace["ip_address"])
        user_id = request.session.uid
        session_identifier = request.session.sid[:42]

        is_readonly = False
        try:
            is_readonly = self.env.cr.readonly
        except AttributeError:
            is_readonly = self.env.registry.in_test_mode()

        if is_readonly:
            self.env.cr.rollback()
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, user_id, self.env.context)
                self._insert_device_log(env, session_identifier, trace, geoip, user_id)
        else:
            self._insert_device_log(self.env, session_identifier, trace, geoip, user_id)

    def _insert_device_log(self, env, session_identifier, trace, geoip, user_id):
        """Helper method to insert the device log record"""
        env.cr.execute(
            SQL(
                """
            INSERT INTO res_device_log
            (session_identifier, platform,
            browser, ip_address, country,
            city, device_type, user_id,
            first_activity, last_activity, revoked)
            VALUES (%(session_identifier)s, %(platform)s,
            %(browser)s, %(ip_address)s, %(country)s,
            %(city)s, %(device_type)s, %(user_id)s,
            %(first_activity)s, %(last_activity)s, %(revoked)s)
        """,
                session_identifier=session_identifier,
                platform=trace["platform"],
                browser=trace["browser"],
                ip_address=trace["ip_address"],
                country=geoip.get("country_name"),
                city=geoip.get("city"),
                device_type="mobile"
                if self._is_mobile(trace["platform"])
                else "computer",
                user_id=user_id,
                first_activity=datetime.fromtimestamp(trace["first_activity"]),
                last_activity=datetime.fromtimestamp(trace["last_activity"]),
                revoked=False,
            )
        )
        _logger.info("User %d inserts device log (%s)", user_id, session_identifier)

    @api.model
    def _delete_old_logs(self):
        two_hours_ago = datetime.now() - timedelta(hours=2)
        old_logs = self.env["res.device.log"].search(
            [("last_activity", "<", two_hours_ago)]
        )
        old_logs.unlink()
        _logger.info("Deleted %d old device logs", len(old_logs))

    def delete_log(self):
        for record in self:
            if record.exists():
                session_identifier = getattr(record, "session_identifier", None)
                log_id = record.id

                self.delete_from_identifiers([session_identifier])

                record.unlink()
                _logger.info(
                    "Deleted device log with ID %d and removed session %s",
                    log_id,
                    session_identifier,
                )
        return True

    def delete_user_sessions(self, user_id):
        if not user_id:
            return {
                "success": False,
                "message": _("No se proporcionó un ID de usuario válido."),
            }

        user = self.env["res.users"].browse(user_id)
        if not user.exists():
            return {"success": False, "message": _("El usuario no existe.")}

        if not user._is_internal():
            return {
                "success": False,
                "message": _(
                    "Solo se pueden borrar las sesiones de usuarios internos. "
                    "Este usuario es de tipo portal o público."
                ),
            }

        device_logs = self.search([("user_id", "=", user_id), ("revoked", "=", False)])

        if not device_logs:
            return {
                "success": True,
                "message": _("No se encontraron sesiones activas para el usuario."),
            }

        session_identifiers = list(
            unique(device.session_identifier for device in device_logs)
        )

        try:
            self.delete_from_identifiers(session_identifiers)
            device_logs.write({"revoked": True})

            _logger.info(
                "Deleted %d sessions for user ID %d", len(session_identifiers), user_id
            )

            return {
                "success": True,
                "message": _("Se han borrado %d sesiones del usuario.")
                % len(session_identifiers),
                "count": len(session_identifiers),
            }

        except Exception as e:
            _logger.error(
                "Error al borrar las sesiones del usuario %d: %s", user_id, str(e)
            )
            return {
                "success": False,
                "message": _("Error al borrar las sesiones: %s") % str(e),
            }

    def delete_from_identifiers(self, identifiers):
        session_path = "/opt/odoo/data/sessions/"
        _logger.info("Using session path: %s", session_path)

        if not os.path.exists(session_path):
            _logger.warning(
                "Session path %s does not exist, skipping deletion", session_path
            )
            return

        files_to_unlink = []
        for identifier in identifiers:
            normalized_path = os.path.normpath(
                os.path.join(session_path, identifier[:2], identifier)
            )
            _logger.info("Looking for session files in path: %s", normalized_path)

            try:
                os.unlink(normalized_path)
                _logger.info("Successfully deleted session file: %s", normalized_path)
            except OSError as e:
                _logger.error("Error deleting file %s: %s", normalized_path, str(e))

        _logger.info("Deleted %d session files from identifiers", len(files_to_unlink))

    @api.autovacuum
    def _gc_device_log(self):
        # Keep the last device log
        # (even if the session file no longer exists on the filesystem)
        self.env.cr.execute(
            """
            DELETE FROM res_device_log log1
            WHERE EXISTS (
                SELECT 1
                FROM res_device_log log2
                WHERE
                    log1.session_identifier = log2.session_identifier
                    AND log1.platform = log2.platform
                    AND log1.browser = log2.browser
                    AND log1.ip_address = log2.ip_address
                    AND log1.last_activity < log2.last_activity
            )
        """
        )
        _logger.info("GC device logs delete %d entries", self.env.cr.rowcount)


class ResDevice(models.Model):
    _name = "res.device"
    _inherit = ["res.device.log"]
    _description = "Devices"
    _auto = False
    _order = "last_activity desc"

    def revoke(self):
        """
        Revoca el acceso a los dispositivos seleccionados.
        Si se llama desde la vista tree, revoca la sesión específica.
        """
        for device in self:
            if device.user_id and hasattr(device.user_id, "check_identity"):
                device.user_id.check_identity()

        result = self._revoke()

        if isinstance(result, dict) and result.get("type"):
            return result

        if result.get("logout"):
            return {
                "type": "ir.actions.act_url",
                "url": "/web/session/logout",
                "target": "self",
            }

        notification_type = "success" if result.get("success") else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revocación de sesiones"),
                "message": result.get("message", _("Operación completada")),
                "sticky": False,
                "type": notification_type,
            },
        }

    def revoke_all_sessions(self):
        """
        Revoca todas las sesiones del usuario actual.
        Este método es similar al botón 'Cerrar sesión en todos los dispositivos'
        de las preferencias de usuario.
        """
        devices = self.env["res.device"].search(
            [("user_id", "=", self.env.user.id), ("revoked", "=", False)]
        )

        if not devices:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No hay sesiones activas"),
                    "message": _("No se encontraron sesiones activas para revocar."),
                    "sticky": False,
                    "type": "warning",
                },
            }

        result = devices._revoke()

        if isinstance(result, dict) and result.get("type"):
            return result

        if result.get("logout"):
            return {
                "type": "ir.actions.act_url",
                "url": "/web/session/logout",
                "target": "self",
            }

        notification_type = "success" if result.get("success") else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revocación de sesiones"),
                "message": result.get("message", _("Operación completada")),
                "sticky": False,
                "type": notification_type,
            },
        }

    def delete_all_user_sessions(self):
        errors = []
        successes = 0

        for device in self:
            device.ensure_one()

            if not device.user_id or not device.user_id.custom_field:
                errors.append(
                    _(
                        """El usuario {} no es válido o
                        "Cerrar sesión automática" está desactivado."""
                    ).format(device.user_id.name if device.user_id else "Desconocido")
                )
                continue

            result = self.env["res.device.log"].delete_user_sessions(device.user_id.id)
            if result.get("success"):
                successes += 1
            else:
                errors.append(
                    result.get(
                        "message",
                        _("Error desconocido en el usuario {}.").format(
                            device.user_id.name
                        ),
                    )
                )

        if successes and errors:
            message = _(
                "Se eliminaron sesiones de %(count)s usuarios, "
                "pero hubo errores con otros:\n%(errors)s"
            ) % {
                "count": successes,
                "errors": "\n".join(errors),
            }
            notification_type = "warning"
        elif successes:
            message = _(
                f"Se eliminaron sesiones de {successes} usuarios correctamente."
            )
            notification_type = "success"
        else:
            message = _(
                "No se pudieron eliminar sesiones:\n{}".format("\n".join(errors))
            )
            notification_type = "warning"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Borrado de sesiones"),
                "message": message,
                "sticky": False,
                "type": notification_type,
            },
        }

    def _revoke(self):
        """
        Revoca las sesiones de los dispositivos seleccionados.
        Este método es llamado por revoke() y revoke_all_sessions().

        :return: Diccionario con información sobre las sesiones revocadas
        """
        if not self:
            return {
                "success": False,
                "message": _("No se seleccionaron dispositivos para revocar."),
            }

        ResDeviceLog = self.env["res.device.log"]
        session_identifiers = list(unique(device.session_identifier for device in self))

        if not session_identifiers:
            return {
                "success": False,
                "message": _(
                    "No se encontraron identificadores de sesión para revocar."
                ),
            }

        try:
            must_logout = bool(self.filtered("is_current"))

            deleted_count = root.session_store.delete_from_identifiers(
                session_identifiers
            )

            revoked_devices = ResDeviceLog.sudo().search(
                [("session_identifier", "in", session_identifiers)]
            )
            revoked_devices.write({"revoked": True})

            _logger.info(
                "User %d revokes devices (%s)",
                self.env.uid,
                ", ".join(session_identifiers),
            )

            if must_logout:
                _logger.info("Revoking current session, redirecting to login page")
                return {
                    "success": True,
                    "message": _(
                        "Sesión actual revocada. Redirigiendo a la "
                        "página de inicio de sesión..."
                    ),
                    "logout": True,
                    "type": "ir.actions.act_url",
                    "url": "/web/session/logout",
                    "target": "self",
                }

            return {
                "success": True,
                "message": _(
                    "Se revocaron %(count)s sesiones "
                    "(%(deleted)s eliminadas del almacén)."
                )
                % {
                    "count": len(revoked_devices),
                    "deleted": deleted_count,
                },
                "revoked_count": len(revoked_devices),
                "deleted_count": deleted_count,
            }
        except Exception as e:
            _logger.error("Error al revocar sesiones: %s", str(e))
            return {
                "success": False,
                "message": _("Error al revocar sesiones: %s") % str(e),
            }

    @api.model
    def _select(self):
        return "SELECT D.*"

    @api.model
    def _from(self):
        return "FROM res_device_log D"

    @api.model
    def _where(self):
        return """
            WHERE
                NOT EXISTS (
                    SELECT 1
                    FROM res_device_log D2
                    WHERE
                        D2.user_id = D.user_id
                        AND D2.session_identifier = D.session_identifier
                        AND D2.platform IS NOT DISTINCT FROM D.platform
                        AND D2.browser IS NOT DISTINCT FROM D.browser
                        AND (
                            D2.last_activity > D.last_activity
                            OR (D2.last_activity = D.last_activity AND D2.id > D.id)
                        )
                        AND D2.revoked = False
                )
                AND D.revoked = False
        """

    @property
    def _query(self):
        return f"{self._select()} {self._from()} {self._where()}"

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            SQL(
                """
            CREATE or REPLACE VIEW %s as (%s)
        """,
                SQL.identifier(self._table),
                SQL(self._query),
            )
        )
