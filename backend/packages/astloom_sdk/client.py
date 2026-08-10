"""HTTP client helpers for Astloom public API paths.

Role: transport wrapper for GET/POST with correlation and idempotency headers.
SoT: caller-supplied base_url, headers, and keys; never invents tenant/project ids.
Allowed failure: SdkError on missing base_url/method. Forbidden: logging secret values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

if TYPE_CHECKING:
    import httpx


class SdkError(ValueError):
    pass


class AstloomClient:
    """Minimal SDK helper for base URL, headers, and API path joining."""

    def __init__(
        self,
        base_url: str,
        *,
        default_headers: dict[str, str] | None = None,
        api_prefix: str = "/api/v1",
        http_client: httpx.Client | None = None,
    ) -> None:
        base = (base_url or "").strip()
        if not base:
            raise SdkError("base_url is required")
        self.base_url = base.rstrip("/") + "/"
        self.api_prefix = api_prefix.rstrip("/")
        self.default_headers = dict(default_headers or {})
        self._http_client = http_client

    @property
    def http_client(self) -> httpx.Client:
        if self._http_client is None:
            import httpx

            self._http_client = httpx.Client()
        return self._http_client

    def url(self, path: str) -> str:
        relative = path if path.startswith("/") else f"/{path}"
        if not relative.startswith(self.api_prefix):
            relative = f"{self.api_prefix}{relative}"
        return urljoin(self.base_url, relative.lstrip("/"))

    def headers(
        self,
        *,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = dict(self.default_headers)
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if extra:
            headers.update(extra)
        return headers

    def build_request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        verb = (method or "").strip().upper()
        if not verb:
            raise SdkError("method is required")
        return {
            "method": verb,
            "url": self.url(path),
            "headers": self.headers(
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                extra=headers,
            ),
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        built = self.build_request(
            method,
            path,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            headers=headers,
        )
        return self.http_client.request(
            built["method"],
            built["url"],
            headers=built["headers"],
            json=json,
        )

    def get(
        self,
        path: str,
        *,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return self.request(
            "GET",
            path,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            headers=headers,
        )

    def post(
        self,
        path: str,
        *,
        json: Any | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return self.request(
            "POST",
            path,
            json=json,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            headers=headers,
        )
