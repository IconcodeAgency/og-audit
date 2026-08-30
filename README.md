# OG Audit

[Русская версия](README.ru.md)

Audit SEO, Open Graph, robots, JSON-LD and sitemap metadata from the command line or CI.

OG Audit fetches the server-rendered HTML, validates standards-based metadata, checks referenced crawler resources, and produces console, JSON, or standalone HTML reports. It distinguishes protocol requirements from display-length heuristics and returns meaningful exit codes.

## What it checks

- HTTP status, HTTPS, redirect chain, response size, and HTML Content-Type.
- Document title, description, language, viewport, H1, and canonical URL.
- `robots` meta and `X-Robots-Tag` directives.
- Required Open Graph fields: `og:title`, `og:type`, `og:image`, and `og:url`.
- OG description, absolute URLs, final URL consistency, image reachability, and image Content-Type.
- Twitter Card presence.
- JSON-LD syntax, detected types, and Schema.org context.
- `/robots.txt`, whether the page is allowed, and declared sitemap locations.
- Sitemap XML validity and canonical page inclusion.

Rules are based on the [Open Graph protocol](https://ogp.me/), [Google Search Central](https://developers.google.com/search/docs), [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html), and the [Sitemaps protocol](https://www.sitemaps.org/protocol.html). Title and description lengths are explicitly reported as heuristics, not ranking requirements.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
og-audit https://example.com
```

Or use Docker:

```bash
docker build -t og-audit .
docker run --rm og-audit https://example.com
```

## Output formats

Human-readable console report:

```bash
og-audit https://example.com
```

Machine-readable JSON:

```bash
og-audit https://example.com --format json --output reports/example.json
```

Standalone HTML report:

```bash
og-audit https://example.com --format html --output reports/example.html
```

When `--output` is omitted, JSON and HTML are written to stdout.

## CI behavior

```bash
# Exit 1 only when errors are found; network/configuration failures exit 2.
og-audit https://example.com --fail-on error

# Treat warnings as build failures.
og-audit https://example.com --fail-on warning

# Always return 0 after a completed audit.
og-audit https://example.com --fail-on never
```

The JSON schema is represented by the Pydantic `AuditReport` model and includes a summary, normalized findings, extracted metadata, redirects, and checked resources.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Audit completed and did not cross the selected threshold. |
| `1` | Findings crossed `--fail-on`. |
| `2` | Audit could not be completed. |

## Private and local targets

Private, loopback, link-local, reserved, and URL-credential targets are blocked by default. This makes accidental requests to metadata endpoints and internal services less likely.

For a trusted local site:

```bash
og-audit http://127.0.0.1:3000 --allow-private
```

Read [SECURITY.md](SECURITY.md) before exposing the auditor as a web service.

## Scope and limitations

Version 0.1.0 audits one URL and the directly referenced OG image, robots file, and sitemap. It does not crawl a whole website, execute JavaScript, recursively inspect sitemap indexes, predict ranking, or validate eligibility for a specific Google rich result.

Client-rendered metadata is intentionally outside the current scope: Telegram, social crawlers, and many search crawlers need useful metadata in the original HTML response. A future browser adapter can be added without changing the audit model.

## Development

```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

## License

[MIT](LICENSE) · Maintained by [IconCode](https://iconcode.ru) · [Support](https://t.me/iconcode_support)
