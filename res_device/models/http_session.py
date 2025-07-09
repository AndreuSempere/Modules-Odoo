# Copyright 2025 Andreu Sempere - asempere@practicas.ontinet.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import logging
import time

from odoo.http import Session

_logger = logging.getLogger(__name__)
original_init = Session.__init__


def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.trace = {}


def update_trace(self, request):
    if not hasattr(self, "trace"):
        self.trace = {}

    try:
        user_agent = request.httprequest.user_agent
        platform = user_agent.platform or "Unknown"
        browser = user_agent.browser or "Unknown"
        ip_address = request.httprequest.remote_addr

        current_time = time.time()
        if not self.trace:
            self.trace = {
                "platform": platform,
                "browser": browser,
                "ip_address": ip_address,
                "first_activity": current_time,
                "last_activity": current_time,
            }
            _logger.info(
                "New trace created for session %s: %s", self.sid[:10], self.trace
            )
        else:
            self.trace.update(
                {
                    "platform": platform,
                    "browser": browser,
                    "ip_address": ip_address,
                    "last_activity": current_time,
                }
            )
            _logger.info("Trace updated for session %s: %s", self.sid[:10], self.trace)

        return self.trace
    except Exception as e:
        _logger.error("Error updating trace: %s", str(e))
        return None


Session.__init__ = patched_init
Session.update_trace = update_trace
