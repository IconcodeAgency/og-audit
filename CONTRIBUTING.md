# Contributing

Bug reports and focused pull requests are welcome. Before proposing a rule, identify whether it
comes from a protocol or crawler specification, a platform recommendation, or a display heuristic.
The finding message must make that distinction explicit.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest -q
```

Keep rule codes stable once released because CI integrations may depend on them. Add parser and
auditor tests for new checks. Security reports should follow [SECURITY.md](SECURITY.md), not public
issues.
