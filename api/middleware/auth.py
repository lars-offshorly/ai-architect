from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from core import get_logger, get_settings

logger = get_logger(__name__)
_PUBLIC_PATH_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


def _is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _base64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(f"{segment}{padding}")
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64url segment in JWT.") from exc


def _decode_json_segment(segment: str) -> dict[str, object]:
    try:
        decoded = _base64url_decode(segment)
        payload = json.loads(decoded.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid JSON segment in JWT.") from exc
    if not isinstance(payload, dict):
        raise ValueError("JWT segment must decode to an object.")
    return {str(key): payload[key] for key in payload}


def _parse_jwt(token: str) -> tuple[dict[str, object], dict[str, object], str, str]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT must contain exactly three segments.")
    header_segment, payload_segment, signature_segment = parts
    header = _decode_json_segment(header_segment)
    payload = _decode_json_segment(payload_segment)
    signing_input = f"{header_segment}.{payload_segment}"
    return header, payload, signing_input, signature_segment


def _validate_algorithm(header: dict[str, object], expected_algorithm: str) -> None:
    algorithm = str(header.get("alg", ""))
    if algorithm != expected_algorithm:
        raise ValueError("JWT algorithm mismatch.")
    if algorithm != "HS256":
        raise ValueError("Unsupported JWT algorithm.")


def _validate_signature(
    signing_input: str,
    signature_segment: str,
    secret: str,
) -> None:
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    provided_signature = _base64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("JWT signature validation failed.")


def _validate_expiration(payload: dict[str, object], now_epoch: int) -> None:
    exp = payload.get("exp")
    if exp is None:
        return
    if not isinstance(exp, (int, float)):
        raise ValueError("JWT exp claim must be a number.")
    if int(exp) <= now_epoch:
        raise ValueError("JWT has expired.")


def _extract_user_id(payload: dict[str, object]) -> str | None:
    for key in ("user_id", "sub", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_role_permissions(payload: dict[str, object]) -> dict[str, bool]:
    permissions = payload.get("role_permissions")
    if not isinstance(permissions, dict):
        return {}

    extracted: dict[str, bool] = {}
    for key, value in permissions.items():
        if isinstance(key, str) and isinstance(value, bool):
            extracted[key] = value
    return extracted


def _validate_token(
    token: str,
    secret: str,
    algorithm: str,
) -> dict[str, object]:
    if not secret:
        raise ValueError("JWT secret is not configured.")
    header, payload, signing_input, signature_segment = _parse_jwt(token)
    _validate_algorithm(header, algorithm)
    _validate_signature(signing_input, signature_segment, secret)
    _validate_expiration(payload, int(time.time()))
    return payload


def _unauthorized_response(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        settings = get_settings()
        request.state.auth_token = None
        request.state.user_id = None
        request.state.role_permissions = {}

        if settings.DEBUG or _is_public_path(request.url.path):
            if settings.DEBUG and not request.state.user_id:
                request.state.user_id = "dev-user"
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization"))
        if token is None:
            return _unauthorized_response("Missing or invalid Authorization header.")

        try:
            payload = _validate_token(
                token,
                settings.JWT_SECRET,
                settings.JWT_ALGORITHM,
            )
        except ValueError as exc:
            logger.warning("JWT validation failed: %s", exc)
            return _unauthorized_response("Invalid authorization token.")

        user_id = _extract_user_id(payload)
        if user_id is None:
            return _unauthorized_response("Authorization token missing user identity.")

        request.state.auth_token = token
        request.state.user_id = user_id
        request.state.role_permissions = _extract_role_permissions(payload)
        return await call_next(request)
