from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup

from .models import PageMetadata


@dataclass(slots=True)
class ParsedPage:
    metadata: PageMetadata
    canonicals: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    viewport: str | None = None
    json_ld_errors: list[str] = field(default_factory=list)
    json_ld_contexts: list[str] = field(default_factory=list)


def _values_by_key(soup: BeautifulSoup, attribute: str, prefix: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for tag in soup.find_all("meta"):
        key = tag.get(attribute)
        content = tag.get("content")
        if not isinstance(key, str) or not isinstance(content, str):
            continue
        normalized = key.strip().lower()
        if normalized.startswith(prefix):
            values.setdefault(normalized, []).append(content.strip())
    return values


def _merge_values(*groups: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for group in groups:
        for key, values in group.items():
            merged.setdefault(key, []).extend(values)
    return merged


def _collect_json_ld_types(value: Any, types: list[str], contexts: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_json_ld_types(item, types, contexts)
        return
    if not isinstance(value, dict):
        return
    context = value.get("@context")
    if isinstance(context, str):
        contexts.append(context)
    kind = value.get("@type")
    if isinstance(kind, str):
        types.append(kind)
    elif isinstance(kind, list):
        types.extend(item for item in kind if isinstance(item, str))
    graph = value.get("@graph")
    if graph is not None:
        _collect_json_ld_types(graph, types, contexts)


def parse_html(body: bytes, encoding: str | None = None) -> ParsedPage:
    soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)

    titles = [tag.get_text(" ", strip=True) for tag in soup.find_all("title")]
    titles = [value for value in titles if value]
    descriptions: list[str] = []
    robots: list[str] = []
    viewport: str | None = None
    for tag in soup.find_all("meta"):
        name = tag.get("name")
        content = tag.get("content")
        if not isinstance(name, str) or not isinstance(content, str):
            continue
        normalized = name.strip().lower()
        if normalized == "description":
            descriptions.append(content.strip())
        elif normalized in {"robots", "googlebot", "yandex"}:
            robots.extend(
                directive.strip().lower() for directive in content.split(",") if directive.strip()
            )
        elif normalized == "viewport":
            viewport = content.strip()

    canonicals: list[str] = []
    for tag in soup.find_all("link"):
        rel = tag.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        if "canonical" in {item.lower() for item in rel}:
            href = tag.get("href")
            if isinstance(href, str) and href.strip():
                canonicals.append(href.strip())

    json_ld_types: list[str] = []
    json_ld_contexts: list[str] = []
    json_ld_errors: list[str] = []
    for index, script in enumerate(soup.find_all("script", attrs={"type": "application/ld+json"})):
        raw = script.string or script.get_text()
        if not raw.strip():
            json_ld_errors.append(f"block {index + 1} is empty")
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            json_ld_errors.append(f"block {index + 1}: {exc.msg} at line {exc.lineno}")
            continue
        _collect_json_ld_types(value, json_ld_types, json_ld_contexts)

    html_tag = soup.find("html")
    language = html_tag.get("lang") if html_tag else None
    h1 = [tag.get_text(" ", strip=True) for tag in soup.find_all("h1")]

    return ParsedPage(
        metadata=PageMetadata(
            title=titles[0] if titles else None,
            description=descriptions[0] if descriptions else None,
            canonical=canonicals[0] if canonicals else None,
            robots=sorted(set(robots)),
            open_graph=_values_by_key(soup, "property", "og:"),
            twitter=_merge_values(
                _values_by_key(soup, "name", "twitter:"),
                _values_by_key(soup, "property", "twitter:"),
            ),
            json_ld_types=sorted(set(json_ld_types)),
            language=language.strip() if isinstance(language, str) else None,
            h1=h1,
        ),
        canonicals=canonicals,
        descriptions=descriptions,
        titles=titles,
        viewport=viewport,
        json_ld_errors=json_ld_errors,
        json_ld_contexts=json_ld_contexts,
    )
