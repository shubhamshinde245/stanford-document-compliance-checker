from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from backend.models import CheckResponse, CheckSummary, Finding, RuleInfo

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
VAGUE_LINK_TEXT = {
    "click here",
    "here",
    "read more",
    "more",
    "link",
    "this",
    "this link",
}

RULES: list[RuleInfo] = [
    RuleInfo(
        id="html-lang",
        title="Document language",
        description="The root <html> element must declare a lang attribute.",
    ),
    RuleInfo(
        id="document-title",
        title="Document title",
        description="The document must include a non-empty <title>.",
    ),
    RuleInfo(
        id="single-h1",
        title="Single page heading",
        description="The document should have exactly one <h1>.",
    ),
    RuleInfo(
        id="heading-order",
        title="Heading order",
        description="Heading levels must not skip (for example h1 then h3).",
    ),
    RuleInfo(
        id="image-alt",
        title="Image alternative text",
        description="Every <img> must include an alt attribute.",
    ),
    RuleInfo(
        id="descriptive-links",
        title="Descriptive links",
        description="Link text must describe the destination, not 'click here'.",
    ),
    RuleInfo(
        id="table-headers",
        title="Table headers",
        description="Data tables must include at least one <th> header cell.",
    ),
    RuleInfo(
        id="stanford-identity",
        title="Stanford identity",
        description="Public documents should name Stanford University.",
    ),
    RuleInfo(
        id="copyright-notice",
        title="Copyright notice",
        description="Documents should include a copyright line.",
    ),
    RuleInfo(
        id="accessibility-contact",
        title="Accessibility contact",
        description="Provide an accessibility statement or contact path.",
    ),
]


def check_html(html: str, filename: str) -> CheckResponse:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    findings = [
        _check_html_lang(soup),
        _check_title(soup),
        _check_single_h1(soup),
        _check_heading_order(soup),
        _check_image_alt(soup),
        _check_descriptive_links(soup),
        _check_table_headers(soup),
        _check_stanford_identity(text),
        _check_copyright(text),
        _check_accessibility_contact(soup, text),
    ]
    passed = sum(1 for f in findings if f.severity == "pass")
    failed = sum(1 for f in findings if f.severity == "fail")
    warnings = sum(1 for f in findings if f.severity == "warn")
    score = round((passed + warnings * 0.5) / len(findings) * 100) if findings else 0
    return CheckResponse(
        filename=filename,
        summary=CheckSummary(
            passed=passed,
            failed=failed,
            warnings=warnings,
            score=score,
        ),
        findings=findings,
    )


def _check_html_lang(soup: BeautifulSoup) -> Finding:
    html = soup.find("html")
    lang = html.get("lang") if isinstance(html, Tag) else None
    if lang and str(lang).strip():
        return Finding(
            id="html-lang",
            title="Document language",
            severity="pass",
            message=f'Language is set to "{str(lang).strip()}".',
        )
    return Finding(
        id="html-lang",
        title="Document language",
        severity="fail",
        message="The <html> element is missing a lang attribute.",
        details='Add lang="en" (or the correct language code) to the root element.',
    )


def _check_title(soup: BeautifulSoup) -> Finding:
    title = soup.find("title")
    value = title.get_text(strip=True) if title else ""
    if value:
        return Finding(
            id="document-title",
            title="Document title",
            severity="pass",
            message=f'Title is "{value}".',
        )
    return Finding(
        id="document-title",
        title="Document title",
        severity="fail",
        message="No non-empty <title> was found.",
        details="Screen readers and browser tabs rely on a unique document title.",
    )


def _check_single_h1(soup: BeautifulSoup) -> Finding:
    headings = soup.find_all("h1")
    texts = [h.get_text(" ", strip=True) for h in headings]
    if len(headings) == 1 and texts[0]:
        return Finding(
            id="single-h1",
            title="Single page heading",
            severity="pass",
            message=f'Found one H1: "{texts[0]}".',
        )
    if not headings:
        return Finding(
            id="single-h1",
            title="Single page heading",
            severity="fail",
            message="The document has no H1 heading.",
        )
    return Finding(
        id="single-h1",
        title="Single page heading",
        severity="warn",
        message=f"Found {len(headings)} H1 headings; pages should have one.",
        details="; ".join(t or "(empty)" for t in texts),
    )


def _check_heading_order(soup: BeautifulSoup) -> Finding:
    levels: list[int] = []
    for tag in soup.find_all(HEADING_TAGS):
        levels.append(int(tag.name[1]))
    if not levels:
        return Finding(
            id="heading-order",
            title="Heading order",
            severity="fail",
            message="No headings were found.",
        )
    skipped: list[str] = []
    previous = levels[0]
    if previous != 1:
        skipped.append(f"first heading is h{previous}")
    for level in levels[1:]:
        if level > previous + 1:
            skipped.append(f"h{previous} jumped to h{level}")
        previous = level
    if not skipped:
        return Finding(
            id="heading-order",
            title="Heading order",
            severity="pass",
            message="Heading levels increase without skipping.",
        )
    return Finding(
        id="heading-order",
        title="Heading order",
        severity="fail",
        message="Heading levels skip in the document outline.",
        details="; ".join(skipped),
    )


def _check_image_alt(soup: BeautifulSoup) -> Finding:
    images = soup.find_all("img")
    if not images:
        return Finding(
            id="image-alt",
            title="Image alternative text",
            severity="pass",
            message="No images present.",
        )
    missing = [
        img.get("src") or "(no src)"
        for img in images
        if not img.has_attr("alt")
    ]
    if not missing:
        return Finding(
            id="image-alt",
            title="Image alternative text",
            severity="pass",
            message=f"All {len(images)} image(s) include alt text.",
        )
    return Finding(
        id="image-alt",
        title="Image alternative text",
        severity="fail",
        message=f"{len(missing)} of {len(images)} image(s) are missing alt.",
        details=", ".join(str(src) for src in missing[:8]),
    )


def _check_descriptive_links(soup: BeautifulSoup) -> Finding:
    vague: list[str] = []
    empty = 0
    links = soup.find_all("a")
    for link in links:
        label = " ".join(link.get_text(" ", strip=True).split())
        if not label:
            empty += 1
            continue
        if label.lower() in VAGUE_LINK_TEXT:
            vague.append(label)
    if not links:
        return Finding(
            id="descriptive-links",
            title="Descriptive links",
            severity="pass",
            message="No links present.",
        )
    if not vague and empty == 0:
        return Finding(
            id="descriptive-links",
            title="Descriptive links",
            severity="pass",
            message=f"All {len(links)} link(s) have descriptive text.",
        )
    parts = []
    if empty:
        parts.append(f"{empty} empty link(s)")
    if vague:
        parts.append(f"vague text: {', '.join(sorted(set(vague)))}")
    return Finding(
        id="descriptive-links",
        title="Descriptive links",
        severity="fail",
        message="Some links are empty or use non-descriptive text.",
        details="; ".join(parts),
    )


def _check_table_headers(soup: BeautifulSoup) -> Finding:
    tables = soup.find_all("table")
    if not tables:
        return Finding(
            id="table-headers",
            title="Table headers",
            severity="pass",
            message="No tables present.",
        )
    missing = sum(1 for table in tables if table.find("th") is None)
    if missing == 0:
        return Finding(
            id="table-headers",
            title="Table headers",
            severity="pass",
            message=f"All {len(tables)} table(s) include header cells.",
        )
    return Finding(
        id="table-headers",
        title="Table headers",
        severity="fail",
        message=f"{missing} of {len(tables)} table(s) have no <th> headers.",
    )


def _check_stanford_identity(text: str) -> Finding:
    if re.search(r"stanford\s+university", text, re.IGNORECASE):
        return Finding(
            id="stanford-identity",
            title="Stanford identity",
            severity="pass",
            message='Document names "Stanford University".',
        )
    if re.search(r"\bstanford\b", text, re.IGNORECASE):
        return Finding(
            id="stanford-identity",
            title="Stanford identity",
            severity="warn",
            message='Found "Stanford" but not the full university name.',
        )
    return Finding(
        id="stanford-identity",
        title="Stanford identity",
        severity="fail",
        message="Stanford University is not identified in the document.",
        details="Public-facing Stanford content should name the university.",
    )


def _check_copyright(text: str) -> Finding:
    if re.search(r"©|copyright|&copy;", text, re.IGNORECASE):
        return Finding(
            id="copyright-notice",
            title="Copyright notice",
            severity="pass",
            message="A copyright notice is present.",
        )
    return Finding(
        id="copyright-notice",
        title="Copyright notice",
        severity="fail",
        message="No copyright notice was found.",
        details="Include a line such as © Board of Trustees of the Leland Stanford Junior University.",
    )


def _check_accessibility_contact(soup: BeautifulSoup, text: str) -> Finding:
    pattern = re.compile(
        r"accessib|ada\b|equal opportunity|disability|accommodation",
        re.IGNORECASE,
    )
    if pattern.search(text):
        return Finding(
            id="accessibility-contact",
            title="Accessibility contact",
            severity="pass",
            message="Accessibility or accommodation language is present.",
        )
    mailto = soup.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
    if mailto:
        return Finding(
            id="accessibility-contact",
            title="Accessibility contact",
            severity="warn",
            message="A contact email exists, but no accessibility statement was found.",
        )
    return Finding(
        id="accessibility-contact",
        title="Accessibility contact",
        severity="fail",
        message="No accessibility statement or contact path was found.",
        details="Add an accessibility statement or a contact for accommodation requests.",
    )
