import json
from pathlib import Path

from typer.testing import CliRunner

from og_audit import __version__
from og_audit.cli import app
from og_audit.models import AuditReport, PageMetadata

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert f"og-audit {__version__}" in result.stdout


def test_writes_html_report(monkeypatch, tmp_path: Path) -> None:
    async def fake_audit(url: str, timeout: float, allow_private: bool) -> AuditReport:
        assert timeout == 10.0
        assert allow_private is False
        return AuditReport(
            requested_url=url,
            final_url=url,
            status_code=200,
            metadata=PageMetadata(title="Example"),
            findings=[],
        )

    monkeypatch.setattr("og_audit.cli._audit", fake_audit)
    output = tmp_path / "report.html"

    result = runner.invoke(
        app,
        ["https://example.com", "--format", "html", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "<!doctype html>" in output.read_text(encoding="utf-8")
    assert "Report written to" in result.output


def test_json_stdout_is_machine_readable(monkeypatch) -> None:
    async def fake_audit(url: str, timeout: float, allow_private: bool) -> AuditReport:
        return AuditReport(
            requested_url=url,
            final_url=url,
            status_code=200,
            metadata=PageMetadata(title="A title that remains on one JSON string"),
            findings=[],
        )

    monkeypatch.setattr("og_audit.cli._audit", fake_audit)

    result = runner.invoke(app, ["https://example.com", "--format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["final_url"] == "https://example.com"
