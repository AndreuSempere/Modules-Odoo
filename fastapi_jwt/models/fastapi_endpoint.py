from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from odoo import _, fields, models
from odoo.http import request

from odoo.addons.fastapi.dependencies import fastapi_endpoint

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
ontinet_api_router = APIRouter()


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    validator_jwt = fields.Many2one("auth.jwt.validator", string="Validador JWT")

    app = fields.Selection(
        selection_add=[("ontinetjwt", "Ontinet JWT")],
        ondelete={"ontinetjwt": "cascade"},
    )

    def _get_fastapi_routers(self) -> list[APIRouter]:
        if self.app == "ontinetjwt":
            return [ontinet_api_router]
        return super()._get_fastapi_routers()


def decode_token(validator, token):
    try:
        return validator._decode(token, validator.secret_key)
    except Exception:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    endpoint=Depends(fastapi_endpoint),  # noqa: B008
):
    env = endpoint.env
    jwt_validator = endpoint.sudo().validator_jwt

    if not jwt_validator:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    payload = decode_token(jwt_validator, token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_("Invalid or expired token"),
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = env["res.users"].sudo().browse(int(user_id))
    if not user.exists():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


@ontinet_api_router.post("/token")
def login_user(
    email: str,
    password: str,
    endpoint=Depends(fastapi_endpoint),  # noqa: B008
):
    try:
        env = endpoint.env
        user_model = env["res.users"]

        user = user_model.sudo().search([("login", "=", email)], limit=1)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        jwt_validator = endpoint.sudo().validator_jwt
        if not jwt_validator:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        user_id = user_model._login(
            request.db, email, password, request.httprequest.environ
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        token = jwt_validator.generate_jwt_token(user_id, jwt_validator)
        refresh_token = jwt_validator.generate_jwt_token(
            user_id, endpoint.sudo().validator_jwt.next_validator_id
        )

        return {
            "access_token": token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
        }

    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from err


@ontinet_api_router.get("/protected")
def protected_route(
    current_user: dict = Depends(get_current_user),  # noqa: B008
):
    response = {
        "message": _("You have accessed a protected route"),
        "user": current_user.name,
    }

    return response


@ontinet_api_router.post("/refresh")
def refresh_token(
    token: str = Depends(oauth2_scheme),
    endpoint=Depends(fastapi_endpoint),  # noqa: B008
):
    try:
        env = endpoint.env
        jwt_validator = endpoint.sudo().validator_jwt

        if not jwt_validator:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payload = decode_token(jwt_validator.next_validator_id, token)

        if payload is None:
            raise HTTPException(
                _(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
            )

        user_id = int(payload.get("sub"))
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        user = env["res.users"].sudo().browse(user_id)
        if not user.exists():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        new_token = jwt_validator.generate_jwt_token(
            user_id, endpoint.sudo().validator_jwt
        )
        return {"access_token": new_token, "token_type": "Bearer"}

    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from err
