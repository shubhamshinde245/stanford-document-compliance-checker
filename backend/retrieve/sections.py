from __future__ import annotations

import re
from dataclasses import dataclass

from backend.retrieve.text import PageText

NUMBER_PREFIX_RE = re.compile(r"^(?:section|sec\.?)\s+|\d+(?:\.\d+)*\.?\s+", re.I)
INLINE_HEADING_RE = re.compile(
    r"^(purpose(?:\s+and\s+scope)?|scope(?:\s+and\s+purpose)?)\b[:.\s]+(.+)$",
    re.I,
)

HEADING_KEYS = {
    "purpose": "purpose",
    "scope": "scope",
    "purpose and scope": "purpose_and_scope",
    "scope and purpose": "purpose_and_scope",
    "safeguards": "safeguards",
    "safeguard": "safeguards",
}

STOP_KEYS = {
    "policy",
    "policy statement",
    "policy statements",
    "policy sanctions",
    "sanctions",
    "policy compliance",
    "roles",
    "role",
    "roles and responsibilities",
    "responsibilities",
    "compliance",
    "definitions",
    "definition",
    "definitions and terms",
    "related standards",
    "related standard",
    "exceptions",
    "exception",
    "enforcement",
    "revision history",
    "revision",
    "audience",
    "applicability",
    "overview",
    "background",
    "procedure",
    "procedures",
    "standard",
    "standards",
    "guidelines",
    "guideline",
    "controls",
    "control",
    "requirements",
    "requirement",
}


@dataclass(frozen=True)
class PolicySections:
    purpose: str
    scope: str
    page: int
    fallback: bool = False


def extract_purpose_and_scope(pages: list[PageText]) -> PolicySections:
    """Pull Purpose and Scope bodies from extracted PDF pages."""
    lines = _numbered_lines(pages)
    headings = _heading_spans(lines)
    purpose, purpose_page = _section_body(lines, headings, "purpose")
    scope, scope_page = _section_body(lines, headings, "scope")
    combined, combined_page = _section_body(lines, headings, "purpose_and_scope")
    if combined:
        if not purpose:
            purpose, purpose_page = combined, combined_page
        if not scope:
            scope, scope_page = combined, combined_page

    fallback = False
    if not purpose:
        purpose = _first_page_text(pages)
        purpose_page = 1
        fallback = True
    page = purpose_page or scope_page or 1
    return PolicySections(
        purpose=_clean(purpose),
        scope=_clean(scope),
        page=page,
        fallback=fallback,
    )


def build_summary_text(*, title: str, category: str, purpose: str, scope: str) -> str:
    lines = [f"Title: {title.strip()}"]
    if category.strip():
        lines.append(f"Category: {category.strip()}")
    if purpose.strip():
        lines.append(f"Purpose: {purpose.strip()}")
    if scope.strip():
        lines.append(f"Scope: {scope.strip()}")
    return "\n".join(lines)


def extract_safeguards_section(pages: list[PageText]) -> str:
    """Body of the Safeguards section, or the full document if that heading is missing."""
    lines = _numbered_lines(pages)
    headings = _heading_spans(lines)
    body, _page = _section_body(lines, headings, "safeguards")
    text = _clean(body)
    if text:
        return text
    return _clean(" ".join(page.text for page in pages))


def _numbered_lines(pages: list[PageText]) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for page in pages:
        for raw in page.text.splitlines():
            text = raw.strip()
            if text:
                lines.append((page.page, text))
    return lines


def _heading_spans(
    lines: list[tuple[int, str]],
) -> list[tuple[int, str, str]]:
    """Return (line_index, key, leftover_inline_body) for each heading."""
    found: list[tuple[int, str, str]] = []
    for index, (_page, text) in enumerate(lines):
        key, leftover = _classify_heading(text)
        if key:
            found.append((index, key, leftover))
    return found


def _classify_heading(text: str) -> tuple[str | None, str]:
    stripped = NUMBER_PREFIX_RE.sub("", text, count=1).strip().rstrip(":").strip()
    if not stripped or len(stripped) > 80:
        return None, ""
    key = " ".join(stripped.lower().split())
    if key in HEADING_KEYS:
        return HEADING_KEYS[key], ""
    if key in STOP_KEYS:
        return "stop", ""
    inline = INLINE_HEADING_RE.match(stripped)
    if inline:
        name = " ".join(inline.group(1).lower().split())
        mapped = HEADING_KEYS.get(name)
        if mapped:
            return mapped, inline.group(2).strip()
    return None, ""


def _section_body(
    lines: list[tuple[int, str]],
    headings: list[tuple[int, str, str]],
    key: str,
) -> tuple[str, int]:
    start = next((item for item in headings if item[1] == key), None)
    if start is None:
        return "", 0
    start_index, _name, leftover = start
    end_index = len(lines)
    for later_index, later_key, _rest in headings:
        if later_index > start_index:
            end_index = later_index
            break
    parts: list[str] = []
    if leftover:
        parts.append(leftover)
    for page, text in lines[start_index + 1 : end_index]:
        parts.append(text)
    page = lines[start_index][0]
    return " ".join(parts), page


def _first_page_text(pages: list[PageText]) -> str:
    for page in pages:
        if page.page == 1 and page.text.strip():
            return page.text
    for page in pages:
        if page.text.strip():
            return page.text
    return ""


def _clean(text: str) -> str:
    return " ".join(text.split())
