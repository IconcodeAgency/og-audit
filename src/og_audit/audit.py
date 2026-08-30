from __future__ import annotations

import re
import urllib.robotparser
from urllib.parse import urljoin, urlsplit, urlunsplit

from defusedxml import ElementTree

from .models import AuditReport, Finding, Severity
from .network import FetchError, FetchResult, SafeFetcher
from .parser import ParsedPage, parse_html


def _normalized_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


class Auditor:
    def __init__(self, fetcher: SafeFetcher) -> None:
        self.fetcher = fetcher
        self.findings: list[Finding] = []
        self.resources: dict = {}

    def add(
        self,
        code: str,
        severity: Severity,
        category: str,
        title: str,
        message: str,
        *,
        value=None,
        evidence: dict | None = None,
    ) -> None:
        self.findings.append(
            Finding(
                code=code,
                severity=severity,
                category=category,
                title=title,
                message=message,
                value=value,
                evidence=evidence or {},
            )
        )

    async def run(self, url: str) -> AuditReport:
        self.findings = []
        self.resources = {}
        page = await self.fetcher.fetch(url)
        content_type = page.headers.get("content-type", "")
        encoding = None
        match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
        if match:
            encoding = match.group(1).strip("\"'")
        parsed = parse_html(page.body, encoding)
        x_robots_tag = page.headers.get("x-robots-tag", "").lower()
        for directive in ("noindex", "nofollow", "none"):
            if directive in x_robots_tag and directive not in parsed.metadata.robots:
                parsed.metadata.robots.append(directive)

        self._check_http(page, content_type)
        self._check_html(parsed, page.final_url)
        self._check_open_graph(parsed, page.final_url)
        self._check_structured_data(parsed)
        await self._check_og_image(parsed, page.final_url)
        await self._check_robots_and_sitemap(page.final_url, parsed.metadata.canonical)

        rank = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        self.findings.sort(key=lambda item: (rank[item.severity], item.category, item.code))
        return AuditReport(
            requested_url=url,
            final_url=page.final_url,
            status_code=page.status_code,
            redirects=page.redirects,
            metadata=parsed.metadata,
            findings=self.findings,
            resources=self.resources,
        )

    def _check_http(self, page: FetchResult, content_type: str) -> None:
        if page.status_code >= 400:
            self.add(
                "http.status",
                Severity.ERROR,
                "HTTP",
                f"Page returned HTTP {page.status_code}",
                "Search engines and social crawlers may not be able to use this page.",
                value=page.status_code,
            )
        if page.redirects:
            self.add(
                "http.redirects",
                Severity.INFO,
                "HTTP",
                f"Page followed {len(page.redirects)} redirect(s)",
                "Audit metadata against the final canonical URL.",
                value=len(page.redirects),
            )
        if urlsplit(page.final_url).scheme != "https":
            self.add(
                "http.https",
                Severity.WARNING,
                "HTTP",
                "Final URL is not HTTPS",
                "Use HTTPS for public, indexable pages.",
                value=page.final_url,
            )
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            self.add(
                "http.content_type",
                Severity.WARNING,
                "HTTP",
                "Unexpected Content-Type",
                "The response is parsed as HTML, but its Content-Type does not declare HTML.",
                value=content_type or "missing",
            )

    def _check_html(self, page: ParsedPage, final_url: str) -> None:
        metadata = page.metadata
        if not metadata.title:
            self.add(
                "html.title.missing",
                Severity.ERROR,
                "HTML",
                "Missing title",
                "Add one non-empty <title> element.",
            )
        else:
            length = len(metadata.title)
            if length < 15 or length > 60:
                self.add(
                    "html.title.length",
                    Severity.WARNING,
                    "HTML",
                    "Title length is outside the common 15–60 character guideline",
                    "This is a display heuristic, not a search engine requirement.",
                    value=length,
                )
        if len(page.titles) > 1:
            self.add(
                "html.title.multiple",
                Severity.WARNING,
                "HTML",
                "Multiple title elements",
                "Keep a single document title.",
                value=len(page.titles),
            )

        if not metadata.description:
            self.add(
                "html.description.missing",
                Severity.WARNING,
                "HTML",
                "Missing meta description",
                "Add a concise page-specific description.",
            )
        elif len(metadata.description) > 160:
            self.add(
                "html.description.length",
                Severity.WARNING,
                "HTML",
                "Meta description is longer than the common 160-character guideline",
                "Search engines may generate or truncate snippets; this is a heuristic.",
                value=len(metadata.description),
            )
        if len(page.descriptions) > 1:
            self.add(
                "html.description.multiple",
                Severity.WARNING,
                "HTML",
                "Multiple meta descriptions",
                "Keep a single page description.",
                value=len(page.descriptions),
            )

        if not page.canonicals:
            self.add(
                "canonical.missing",
                Severity.WARNING,
                "Indexing",
                "Missing canonical URL",
                "Add one absolute rel=canonical URL for indexable pages.",
            )
        elif len(page.canonicals) > 1:
            self.add(
                "canonical.multiple",
                Severity.ERROR,
                "Indexing",
                "Multiple canonical URLs",
                "Conflicting canonical signals should be removed.",
                value=len(page.canonicals),
            )
        else:
            canonical = urljoin(final_url, page.canonicals[0])
            if not urlsplit(page.canonicals[0]).scheme:
                self.add(
                    "canonical.relative",
                    Severity.WARNING,
                    "Indexing",
                    "Canonical URL is relative",
                    "Prefer an absolute canonical URL.",
                    value=page.canonicals[0],
                )
            if _normalized_url(canonical) != _normalized_url(final_url):
                self.add(
                    "canonical.differs",
                    Severity.WARNING,
                    "Indexing",
                    "Canonical differs from the final URL",
                    "Cross-URL canonicals can be intentional; verify this signal.",
                    value=canonical,
                    evidence={"final_url": final_url},
                )

        if "noindex" in metadata.robots or "none" in metadata.robots:
            self.add(
                "robots.noindex",
                Severity.ERROR,
                "Indexing",
                "Page declares noindex",
                "Remove noindex if this page should appear in search results.",
            )
        if "nofollow" in metadata.robots or "none" in metadata.robots:
            self.add(
                "robots.nofollow",
                Severity.WARNING,
                "Indexing",
                "Page declares nofollow",
                "Verify that links on this page should not be followed.",
            )
        if not metadata.language:
            self.add(
                "html.lang.missing",
                Severity.WARNING,
                "HTML",
                "Missing html lang attribute",
                "Declare the primary document language.",
            )
        if not page.viewport:
            self.add(
                "html.viewport.missing",
                Severity.WARNING,
                "HTML",
                "Missing viewport metadata",
                "Add a responsive viewport declaration.",
            )
        if len(metadata.h1) == 0:
            self.add(
                "html.h1.missing",
                Severity.WARNING,
                "HTML",
                "Missing H1",
                "Add a visible primary heading.",
            )
        elif len(metadata.h1) > 1:
            self.add(
                "html.h1.multiple",
                Severity.INFO,
                "HTML",
                "Multiple H1 headings",
                "Multiple H1 elements are valid HTML, but verify the document outline.",
                value=len(metadata.h1),
            )

    def _check_open_graph(self, page: ParsedPage, final_url: str) -> None:
        og = page.metadata.open_graph
        for key in ("og:title", "og:type", "og:image", "og:url"):
            if not og.get(key) or not og[key][0]:
                self.add(
                    f"{key}.missing",
                    Severity.ERROR,
                    "Open Graph",
                    f"Missing {key}",
                    "The Open Graph protocol defines this as required metadata.",
                )
            elif len(og[key]) > 1 and key != "og:image":
                self.add(
                    f"{key}.multiple",
                    Severity.WARNING,
                    "Open Graph",
                    f"Multiple {key} values",
                    "Verify which value consumers will select.",
                    value=len(og[key]),
                )
        if not og.get("og:description"):
            self.add(
                "og:description.missing",
                Severity.WARNING,
                "Open Graph",
                "Missing og:description",
                "Add a share-specific description.",
            )

        og_url = og.get("og:url", [None])[0]
        if og_url:
            if not urlsplit(og_url).scheme:
                self.add(
                    "og:url.relative",
                    Severity.ERROR,
                    "Open Graph",
                    "og:url is relative",
                    "Open Graph URLs should be absolute.",
                    value=og_url,
                )
            elif _normalized_url(og_url) != _normalized_url(final_url):
                self.add(
                    "og:url.differs",
                    Severity.WARNING,
                    "Open Graph",
                    "og:url differs from the final URL",
                    "Verify that shares should resolve to this object URL.",
                    value=og_url,
                    evidence={"final_url": final_url},
                )

        twitter = page.metadata.twitter
        if not twitter.get("twitter:card"):
            self.add(
                "twitter:card.missing",
                Severity.INFO,
                "Social",
                "Missing twitter:card",
                "Open Graph fallback may work, but an explicit card type is more predictable.",
            )

    def _check_structured_data(self, page: ParsedPage) -> None:
        for error in page.json_ld_errors:
            self.add("jsonld.invalid", Severity.ERROR, "Structured data", "Invalid JSON-LD", error)
        if not page.metadata.json_ld_types and not page.json_ld_errors:
            self.add(
                "jsonld.missing",
                Severity.INFO,
                "Structured data",
                "No JSON-LD detected",
                "Structured data is optional; add it only when it accurately describes the page.",
            )
        if page.metadata.json_ld_types:
            self.add(
                "jsonld.types",
                Severity.INFO,
                "Structured data",
                "JSON-LD types detected",
                ", ".join(page.metadata.json_ld_types),
                value=len(page.metadata.json_ld_types),
            )
        for context in page.json_ld_contexts:
            if "schema.org" not in context:
                self.add(
                    "jsonld.context",
                    Severity.WARNING,
                    "Structured data",
                    "Unusual JSON-LD context",
                    "Search features commonly use Schema.org vocabulary.",
                    value=context,
                )

    async def _check_og_image(self, page: ParsedPage, final_url: str) -> None:
        values = page.metadata.open_graph.get("og:image") or []
        if not values:
            return
        image_url = values[0]
        if not urlsplit(image_url).scheme:
            self.add(
                "og:image.relative",
                Severity.ERROR,
                "Open Graph",
                "og:image is relative",
                "Use an absolute image URL.",
                value=image_url,
            )
            image_url = urljoin(final_url, image_url)
        try:
            result = await self.fetcher.fetch(
                image_url, max_bytes=10_000_000, accept="image/*,*/*;q=0.1"
            )
        except FetchError as exc:
            self.add(
                "og:image.fetch",
                Severity.ERROR,
                "Open Graph",
                "OG image is not reachable",
                str(exc),
                value=image_url,
            )
            return
        content_type = result.headers.get("content-type", "")
        self.resources["og_image"] = {
            "url": result.final_url,
            "status_code": result.status_code,
            "content_type": content_type,
            "bytes": len(result.body),
        }
        if result.status_code >= 400:
            self.add(
                "og:image.status",
                Severity.ERROR,
                "Open Graph",
                f"OG image returned HTTP {result.status_code}",
                "Use a publicly reachable image.",
                value=image_url,
            )
        if not content_type.startswith("image/"):
            self.add(
                "og:image.content_type",
                Severity.ERROR,
                "Open Graph",
                "OG image has a non-image Content-Type",
                "Serve the resource with an image media type.",
                value=content_type or "missing",
            )

    async def _check_robots_and_sitemap(self, final_url: str, canonical: str | None) -> None:
        parsed_url = urlsplit(final_url)
        origin = urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", ""))
        robots_url = f"{origin}/robots.txt"
        sitemap_urls: list[str] = []
        try:
            robots = await self.fetcher.fetch(
                robots_url, max_bytes=500_000, accept="text/plain,*/*;q=0.1"
            )
        except FetchError as exc:
            self.add(
                "robots.fetch",
                Severity.WARNING,
                "Crawling",
                "Could not fetch robots.txt",
                str(exc),
                value=robots_url,
            )
        else:
            self.resources["robots"] = {"url": robots.final_url, "status_code": robots.status_code}
            if robots.status_code == 404:
                self.add(
                    "robots.missing",
                    Severity.WARNING,
                    "Crawling",
                    "robots.txt is missing",
                    (
                        "A missing file usually permits crawling, but cannot advertise "
                        "sitemap locations."
                    ),
                    value=robots_url,
                )
            elif robots.status_code >= 400:
                self.add(
                    "robots.status",
                    Severity.WARNING,
                    "Crawling",
                    f"robots.txt returned HTTP {robots.status_code}",
                    "Verify crawler behavior for this response.",
                    value=robots_url,
                )
            else:
                text = robots.body.decode("utf-8", errors="replace")
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(text.splitlines())
                if not parser.can_fetch("*", final_url):
                    self.add(
                        "robots.disallowed",
                        Severity.ERROR,
                        "Crawling",
                        "robots.txt disallows this page",
                        "Remove the matching Disallow rule if the page should be crawled.",
                        value=final_url,
                    )
                sitemap_urls = [
                    match.strip() for match in re.findall(r"(?im)^\s*sitemap\s*:\s*(\S+)\s*$", text)
                ]

        sitemap_url = sitemap_urls[0] if sitemap_urls else f"{origin}/sitemap.xml"
        try:
            sitemap = await self.fetcher.fetch(
                sitemap_url, max_bytes=10_000_000, accept="application/xml,text/xml,*/*;q=0.1"
            )
        except FetchError as exc:
            self.add(
                "sitemap.fetch",
                Severity.WARNING,
                "Crawling",
                "Could not fetch sitemap",
                str(exc),
                value=sitemap_url,
            )
            return
        self.resources["sitemap"] = {"url": sitemap.final_url, "status_code": sitemap.status_code}
        if sitemap.status_code == 404:
            self.add(
                "sitemap.missing",
                Severity.WARNING,
                "Crawling",
                "Sitemap is missing",
                "Add a sitemap for sites with indexable pages.",
                value=sitemap_url,
            )
            return
        if sitemap.status_code >= 400:
            self.add(
                "sitemap.status",
                Severity.WARNING,
                "Crawling",
                f"Sitemap returned HTTP {sitemap.status_code}",
                "Fix or remove the sitemap declaration.",
                value=sitemap_url,
            )
            return
        try:
            root = ElementTree.fromstring(sitemap.body)
        except ElementTree.ParseError as exc:
            self.add(
                "sitemap.invalid",
                Severity.ERROR,
                "Crawling",
                "Sitemap XML is invalid",
                str(exc),
                value=sitemap_url,
            )
            return
        root_name = root.tag.rsplit("}", 1)[-1]
        if root_name not in {"urlset", "sitemapindex"}:
            self.add(
                "sitemap.root",
                Severity.ERROR,
                "Crawling",
                "Unsupported sitemap root element",
                "A sitemap must use urlset or sitemapindex as its root element.",
                value=root_name,
            )
            return
        locations = [
            element.text.strip()
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == "loc" and element.text
        ]
        if root_name == "sitemapindex":
            self.add(
                "sitemap.index",
                Severity.INFO,
                "Crawling",
                "Sitemap index detected",
                "Child sitemaps are not recursively fetched in v0.1.0.",
                value=len(locations),
            )
            return
        target = (
            _normalized_url(urljoin(final_url, canonical))
            if canonical
            else _normalized_url(final_url)
        )
        normalized_locations = {_normalized_url(item) for item in locations}
        if target not in normalized_locations:
            self.add(
                "sitemap.page_missing",
                Severity.WARNING,
                "Crawling",
                "Page is not listed in the sitemap",
                "Indexable canonical pages should normally be included.",
                value=target,
                evidence={"entries": len(locations)},
            )
