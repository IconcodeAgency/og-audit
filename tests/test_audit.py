from __future__ import annotations

import httpx
import pytest

from og_audit.audit import Auditor
from og_audit.models import Severity
from og_audit.network import SafeFetcher


def response_for(request: httpx.Request, html: bytes) -> httpx.Response:
    if request.url.path == "/page":
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, content=html
        )
    if request.url.path == "/og.png":
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"PNG")
    if request.url.path == "/robots.txt":
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            text="User-agent: *\nAllow: /\nSitemap: https://site.test/sitemap.xml\n",
        )
    if request.url.path == "/sitemap.xml":
        return httpx.Response(
            200,
            headers={"content-type": "application/xml"},
            text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://site.test/page</loc></url></urlset>',
        )
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_valid_page_has_no_errors_or_warnings(valid_html: bytes) -> None:
    transport = httpx.MockTransport(lambda request: response_for(request, valid_html))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        fetcher = SafeFetcher(client=client, allow_private=True)
        report = await Auditor(fetcher).run("https://site.test/page")

    assert report.status_code == 200
    assert report.counts["error"] == 0
    assert report.counts["warning"] == 0
    assert report.score == 100
    assert report.resources["og_image"]["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_broken_page_returns_actionable_findings() -> None:
    html = b"<html><head><meta name='robots' content='noindex'></head><body></body></html>"
    transport = httpx.MockTransport(lambda request: response_for(request, html))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        report = await Auditor(SafeFetcher(client=client, allow_private=True)).run(
            "https://site.test/page"
        )

    codes = {finding.code for finding in report.findings}
    assert {
        "html.title.missing",
        "canonical.missing",
        "og:title.missing",
        "robots.noindex",
    } <= codes
    assert report.counts["error"] >= 5


@pytest.mark.asyncio
async def test_redirect_chain_is_reported(valid_html: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/page"})
        return response_for(request, valid_html)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        report = await Auditor(SafeFetcher(client=client, allow_private=True)).run(
            "https://site.test/old"
        )

    assert report.final_url == "https://site.test/page"
    assert len(report.redirects) == 1
    assert any(
        item.code == "http.redirects" and item.severity == Severity.INFO for item in report.findings
    )


@pytest.mark.asyncio
async def test_rejects_non_sitemap_xml(valid_html: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                headers={"content-type": "application/xml"},
                text="<html><body>not a sitemap</body></html>",
            )
        return response_for(request, valid_html)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        report = await Auditor(SafeFetcher(client=client, allow_private=True)).run(
            "https://site.test/page"
        )

    assert any(item.code == "sitemap.root" for item in report.findings)
