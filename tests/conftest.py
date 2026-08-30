from __future__ import annotations

import pytest


@pytest.fixture
def valid_html() -> bytes:
    return b"""<!doctype html>
<html lang="en"><head>
<title>A useful test page for metadata auditing</title>
<meta name="description" content="A concise and unique description for the page under audit.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://site.test/page">
<meta property="og:title" content="A useful test page">
<meta property="og:type" content="website">
<meta property="og:image" content="https://site.test/og.png">
<meta property="og:url" content="https://site.test/page">
<meta property="og:description" content="Share description">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage"}</script>
</head><body><h1>A useful test page</h1></body></html>"""
