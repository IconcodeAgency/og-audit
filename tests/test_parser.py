from og_audit.parser import parse_html


def test_extracts_metadata(valid_html: bytes) -> None:
    page = parse_html(valid_html)
    assert page.metadata.title == "A useful test page for metadata auditing"
    assert page.metadata.canonical == "https://site.test/page"
    assert page.metadata.open_graph["og:image"] == ["https://site.test/og.png"]
    assert page.metadata.twitter["twitter:card"] == ["summary_large_image"]
    assert page.metadata.json_ld_types == ["WebPage"]
    assert page.metadata.language == "en"
    assert page.metadata.h1 == ["A useful test page"]


def test_reports_invalid_json_ld() -> None:
    page = parse_html(b'<script type="application/ld+json">{"broken":</script>')
    assert page.json_ld_errors


def test_preserves_twitter_values_from_name_and_property() -> None:
    page = parse_html(
        b"""
        <meta name="twitter:image" content="https://site.test/one.png">
        <meta property="twitter:image" content="https://site.test/two.png">
        """
    )

    assert page.metadata.twitter["twitter:image"] == [
        "https://site.test/one.png",
        "https://site.test/two.png",
    ]
