import json

from og_audit.models import AuditReport, PageMetadata
from og_audit.reporting import render_html, render_json


def test_reports_include_summary() -> None:
    report = AuditReport(
        requested_url="https://example.com",
        final_url="https://example.com/",
        status_code=200,
        metadata=PageMetadata(),
        findings=[],
    )
    payload = json.loads(render_json(report))
    assert payload["summary"] == {"score": 100, "info": 0, "warning": 0, "error": 0}
    html = render_html(report)
    assert "Score" in html
    assert "https://example.com/" in html
