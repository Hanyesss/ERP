import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 15.0


class TronTokError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class TronTokNotFound(TronTokError):
    pass


class TronTokClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        if not api_key:
            raise ValueError("api_key is required")
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _sign(self, method: str, path_qs: str, ts: str, body_bytes: bytes) -> str:
        msg = f"{method.upper()}\n{path_qs}\n{ts}\n".encode() + body_bytes
        return hmac.new(self._key.encode(), msg, hashlib.sha256).hexdigest()

    def _headers(self, method: str, path_qs: str, body_bytes: bytes) -> dict:
        ts = str(int(time.time()))
        sig = self._sign(method, path_qs, ts, body_bytes)
        return {
            "Content-Type": "application/json",
            "X-Partner-Key": self._key,
            "X-Timestamp": ts,
            "X-Signature": sig,
        }

    def _raise(self, resp: httpx.Response) -> None:
        if resp.status_code < 300:
            return
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        msg = f"TronTok {resp.status_code}: {detail}"
        if resp.status_code == 404:
            raise TronTokNotFound(msg, resp.status_code)
        raise TronTokError(msg, resp.status_code)

    async def _get(self, path: str, params: dict | None = None) -> Any:
        qs = urlencode(params) if params else ""
        path_qs = path + ("?" + qs if qs else "")
        url = self._base + path_qs
        headers = self._headers("GET", path_qs, b"")
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            resp = await c.get(url, headers=headers)
        logger.debug("TronTok GET %s → %s", path, resp.status_code)
        self._raise(resp)
        return resp.json()

    async def _post(self, path: str, body: dict) -> Any:
        body_bytes = json.dumps(body).encode()
        path_qs = path
        url = self._base + path
        headers = self._headers("POST", path_qs, body_bytes)
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            resp = await c.post(url, content=body_bytes, headers=headers)
        logger.debug("TronTok POST %s → %s", path, resp.status_code)
        self._raise(resp)
        return resp.json()

    async def provision(self, email: str, external_id: str) -> dict:
        return await self._post("/partner/provision", {"email": email, "external_id": external_id})

    async def user_status(self, external_id: str) -> dict:
        return await self._get("/partner/user-status", {"external_id": external_id})

    async def get_balance(self, external_id: str) -> dict:
        return await self._get("/partner/balance", {"external_id": external_id})

    async def totp_setup(self, email: str) -> dict:
        return await self._post("/partner/totp-setup", {"email": email})

    async def totp_enable(self, email: str, code: str) -> dict:
        return await self._post("/partner/totp-enable", {"email": email, "code": code})

    async def payment_status(self, ref: str, external_id: str) -> dict:
        return await self._get("/partner/payment-status", {"ref": ref, "external_id": external_id})

    async def forgot_password(self, email: str) -> bool:
        """Unauthenticated — no HMAC signing."""
        url = self._base + "/auth/forgot-password"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                resp = await c.post(url, json={"email": email})
            return resp.status_code == 200
        except Exception as exc:
            logger.error("TronTok forgot_password failed for %s: %s", email, exc)
            return False
