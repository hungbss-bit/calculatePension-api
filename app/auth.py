from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader


API_KEY_HEADER_NAME = "X-API-Key"
API_KEY_ENV_CANDIDATES = (
    "API_KEY",
    "CALCULATEPENSION_API_KEY",
    "X_API_KEY",
)

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    scheme_name="CalculatePensionApiKey",
    description="Khóa bí mật dùng cho GPT Action, gửi qua header X-API-Key.",
    auto_error=False,
)


@dataclass(frozen=True)
class ApiKeyConfig:
    raw_value: str | None
    normalized_value: str | None
    env_name: str | None
    normalization_changed: bool


def _normalize_secret(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    # Render/GPT users sometimes paste a secret with wrapping quotes.
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {"'", '"'}
    ):
        normalized = normalized[1:-1].strip()

    return normalized or None


def _read_expected_api_key() -> ApiKeyConfig:
    for env_name in API_KEY_ENV_CANDIDATES:
        raw_value = os.getenv(env_name)
        normalized_value = _normalize_secret(raw_value)
        if normalized_value:
            return ApiKeyConfig(
                raw_value=raw_value,
                normalized_value=normalized_value,
                env_name=env_name,
                normalization_changed=(raw_value != normalized_value),
            )

    return ApiKeyConfig(
        raw_value=None,
        normalized_value=None,
        env_name=None,
        normalization_changed=False,
    )


def _env_flag(name: str, default: bool = False) -> bool:
    value = _normalize_secret(os.getenv(name))
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def verify_api_key(
    x_api_key: str | None = Security(api_key_header),
) -> None:
    config = _read_expected_api_key()
    require_api_key = _env_flag("REQUIRE_API_KEY", default=True)

    if not config.normalized_value:
        if require_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "API_KEY_NOT_CONFIGURED",
                    "message_vi": (
                        "Dịch vụ yêu cầu API key nhưng chưa đọc được biến API_KEY "
                        "trong môi trường chạy."
                    ),
                },
            )
        return

    received = _normalize_secret(x_api_key)
    if not received:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "X_API_KEY_MISSING",
                "message_vi": "Thiếu header X-API-Key.",
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(received, config.normalized_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "X_API_KEY_MISMATCH",
                "message_vi": "Khóa X-API-Key không khớp với khóa của dịch vụ.",
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )


def get_auth_diagnostics(x_api_key: str | None) -> dict[str, object]:
    if not _env_flag("AUTH_DIAGNOSTICS_ENABLED", default=False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "AUTH_DIAGNOSTICS_DISABLED",
                "message_vi": (
                    "Chẩn đoán xác thực đang tắt. Đặt AUTH_DIAGNOSTICS_ENABLED=true "
                    "trên Render và triển khai lại để sử dụng tạm thời."
                ),
            },
        )

    config = _read_expected_api_key()
    received_raw = x_api_key
    received_normalized = _normalize_secret(received_raw)

    match = bool(
        config.normalized_value
        and received_normalized
        and secrets.compare_digest(received_normalized, config.normalized_value)
    )

    return {
        "service": "calculatePension",
        "version": "1.0.5-rc",
        "diagnostics_enabled": True,
        "api_key_required": _env_flag("REQUIRE_API_KEY", default=True),
        "configured": bool(config.normalized_value),
        "configured_env_name": config.env_name,
        "expected_length": (
            len(config.normalized_value) if config.normalized_value else 0
        ),
        "expected_fingerprint_sha256_12": _fingerprint(config.normalized_value),
        "expected_normalization_changed": config.normalization_changed,
        "received_header_name": API_KEY_HEADER_NAME,
        "received_present": bool(received_raw),
        "received_length_raw": len(received_raw) if received_raw else 0,
        "received_length_normalized": (
            len(received_normalized) if received_normalized else 0
        ),
        "received_fingerprint_sha256_12": _fingerprint(received_normalized),
        "received_normalization_changed": (
            received_raw != received_normalized if received_raw is not None else False
        ),
        "normalized_match": match,
        "next_step_vi": (
            "Khóa đã khớp; có thể tắt AUTH_DIAGNOSTICS_ENABLED."
            if match
            else (
                "So sánh expected_fingerprint và received_fingerprint. "
                "Nếu received_present=false thì client không gửi X-API-Key; "
                "nếu hai fingerprint khác nhau thì khóa Render và khóa client không giống nhau."
            )
        ),
    }
