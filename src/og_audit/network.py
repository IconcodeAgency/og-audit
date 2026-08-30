from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from .models import RedirectHop


class FetchError(RuntimeError):
    pass


class UnsafeTargetError(FetchError):
    pass


@dataclass(slots=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    redirects: list[RedirectHop] = field(default_factory=list)


def _is_unsafe_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


async def validate_public_url(url: str, *, allow_private: bool = False) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeTargetError("only http and https URLs are supported")
    if not parsed.hostname:
        raise UnsafeTargetError("URL must contain a hostname")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("credentials in URLs are not allowed")
    if allow_private:
        return

    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise FetchError(f"cannot resolve {parsed.hostname}") from exc
        addresses = {record[4][0] for record in records}
    else:
        addresses = {str(literal)}

    if any(_is_unsafe_address(address) for address in addresses):
        raise UnsafeTargetError("private, local and reserved network targets are blocked")


class SafeFetcher:
    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_redirects: int = 5,
        allow_private: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.allow_private = allow_private
        self.max_redirects = max_redirects
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "IconCode-OG-Audit/0.1 (+https://github.com/IconcodeAgency/og-audit)"
                )
            },
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def fetch(
        self,
        url: str,
        *,
        max_bytes: int = 2_000_000,
        accept: str = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    ) -> FetchResult:
        requested_url = url
        current_url = url
        redirects: list[RedirectHop] = []

        for _ in range(self.max_redirects + 1):
            await validate_public_url(current_url, allow_private=self.allow_private)
            try:
                async with self.client.stream(
                    "GET", current_url, headers={"Accept": accept}
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError(f"redirect from {current_url} has no Location header")
                        target = urljoin(str(response.url), location)
                        redirects.append(
                            RedirectHop(
                                status_code=response.status_code,
                                source=str(response.url),
                                target=target,
                            )
                        )
                        current_url = target
                        continue

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise FetchError(f"response body exceeds the {max_bytes}-byte limit")
                    return FetchResult(
                        requested_url=requested_url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        headers={key.lower(): value for key, value in response.headers.items()},
                        body=bytes(body),
                        redirects=redirects,
                    )
            except httpx.HTTPError as exc:
                raise FetchError(f"request failed for {current_url}: {exc}") from exc

        raise FetchError(f"more than {self.max_redirects} redirects")
