from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from backend.scraper.catalog import (
    ensure_dirs,
    load_catalog,
    pdf_path_for,
    relative_pdf_path,
    save_catalog,
    utc_now,
)
from backend.settings import SANS_BASE_URL

SHOWING_RE = re.compile(r"Showing\s+(\d+)\s+of\s+(\d+)", re.I)
DATE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})")
PDF_SIZE_RE = re.compile(r"PDF[^)]*\(([\d.]+)\s*MB\)", re.I)
DETAIL_PATH_RE = re.compile(r"/information-security-policy/([^/]+)/?$")
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_published_on(text: str | None) -> str | None:
    if not text:
        return None
    match = DATE_RE.search(text.replace(",", " "))
    if not match:
        return None
    raw = match.group(1)
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    parts = raw.split()
    if len(parts) != 3:
        return None
    day, month, year = parts
    month_num = MONTHS.get(month.lower())
    if not month_num:
        return None
    try:
        return datetime(int(year), month_num, int(day)).date().isoformat()
    except ValueError:
        return None


def display_label(text: str | None) -> str:
    if not text:
        return ""
    stripped = " ".join(text.split())
    if stripped != stripped.upper():
        return stripped
    small = {"and", "of", "the", "or", "for"}
    words = stripped.lower().split()
    return " ".join(
        word if index and word in small else word.capitalize()
        for index, word in enumerate(words)
    )


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    match = DETAIL_PATH_RE.search(path)
    if match:
        return match.group(1)
    return path.rsplit("/", 1)[-1]


def _dismiss_cookies(page) -> None:
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button:has-text('I Accept')",
        "button:has-text('Agree')",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            if locator.first.is_visible(timeout=1500):
                locator.first.click(timeout=2000)
                page.wait_for_timeout(400)
                return
        except PlaywrightTimeout:
            continue


def _click_show_60(page) -> None:
    selects = page.locator("select.select__select").filter(
        has=page.locator("option[value='60']")
    )
    last_error: Exception | None = None
    for index in range(selects.count()):
        item = selects.nth(index)
        try:
            if not item.is_visible():
                continue
            item.select_option("60")
            page.wait_for_timeout(800)
            print(f"Selected Show 60 (value={item.input_value()})")
            return
        except Exception as exc:  # noqa: BLE001 — try the next Show control
            last_error = exc
            continue
    algolia = page.locator("select.ais-HitsPerPage-select")
    if algolia.count():
        try:
            algolia.first.select_option("60", force=True)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(
        "Could not select Show 60 on the SANS listing page."
        + (f" Last error: {last_error}" if last_error else "")
    )


def _showing(page) -> tuple[str, int, int]:
    locator = page.locator(".c-lister-showing-x-of-y").first
    if locator.count() == 0:
        body = page.locator("body").inner_text()
        match = SHOWING_RE.search(body)
    else:
        match = SHOWING_RE.search(locator.inner_text())
    if not match:
        raise RuntimeError("Could not find 'Showing X of Y' on the SANS listing page.")
    listed = int(match.group(1))
    total = int(match.group(2))
    return match.group(0), listed, total


def _wait_for_full_list(page, previous_listed: int) -> tuple[str, int, int]:
    deadline = time.time() + 20
    last = _showing(page)
    while time.time() < deadline:
        showing_text, listed, total = _showing(page)
        last = (showing_text, listed, total)
        if listed >= total and total > 0:
            return last
        if listed > previous_listed:
            # Count moved; give the grid a moment to finish rendering.
            page.wait_for_timeout(800)
            return _showing(page)
        page.wait_for_timeout(300)
    raise RuntimeError(
        f"Show 60 did not expand the listing (still {last[0]!r}; expected more than "
        f"{previous_listed} items)."
    )


def _extract_listing_cards(page, base_url: str) -> list[dict[str, str]]:
    payload = page.evaluate(
        """() => {
          return [...document.querySelectorAll(".c-resource-card")].map((card) => {
            const anchor = card.closest("a") || card.querySelector("a");
            const textOf = (sel) => (card.querySelector(sel)?.textContent || "").replace(/\\s+/g, " ").trim();
            return {
              href: anchor ? anchor.href : "",
              title: textOf(".resource-card__title"),
              kind: textOf(".resource-card__resource") || "Policy template",
              category: textOf(".resource-card__subtitle"),
              published_raw: textOf(".resource-card__data-list-item-label"),
            };
          });
        }"""
    )
    policies: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in payload:
        href = urljoin(base_url, item.get("href") or "")
        slug = slug_from_url(href)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        policies.append(
            {
                "slug": slug,
                "title": (item.get("title") or "").strip() or slug,
                "category": display_label(item.get("category")),
                "kind": display_label(item.get("kind") or "Policy template") or "Policy template",
                "published_on": parse_published_on(item.get("published_raw")) or "",
                "source_url": href,
            }
        )
    return policies


def _extract_detail(page) -> dict[str, str]:
    body = page.locator("body").inner_text()
    published = parse_published_on(body) or ""
    size_match = PDF_SIZE_RE.search(body)
    pdf_size_mb = size_match.group(1) if size_match else ""
    heading = page.locator("h1").first
    title = heading.inner_text().strip() if heading.count() else page.title()
    summary = page.evaluate(
        """() => {
          const paragraphs = [...document.querySelectorAll("p")]
            .map((el) => (el.innerText || "").trim())
            .filter((text) => text.length >= 80);
          return paragraphs[0] || "";
        }"""
    )
    return {
        "title": title,
        "published_on": published,
        "pdf_size_mb": pdf_size_mb,
        "summary": summary,
    }


def _looks_like_lead_form(page) -> bool:
    markers = [
        "input[type='email']",
        "form:has(input[type='email'])",
        "text=First Name",
        "text=Work Email",
        "text=Download the template",
    ]
    for marker in markers:
        locator = page.locator(marker)
        try:
            if locator.first.is_visible(timeout=400):
                return True
        except PlaywrightTimeout:
            continue
    return False


def _save_pdf_bytes(dest, body: bytes) -> tuple[str, int] | None:
    if not body.startswith(b"%PDF"):
        return None
    dest.write_bytes(body)
    return relative_pdf_path(dest.stem), dest.stat().st_size


def _download_from_egnyte(page, href: str, dest) -> tuple[str, int] | None:
    token = href.rstrip("/").rsplit("/", 1)[-1]
    if not token:
        return None
    download_url = f"https://sansorg.egnyte.com/dd/{token}/"
    response = page.request.get(download_url)
    if response.ok:
        saved = _save_pdf_bytes(dest, response.body())
        if saved:
            return saved
    return None


def _download_pdf(page, slug: str) -> tuple[str | None, int | None, str | None]:
    dest = pdf_path_for(slug)
    pdf_link = page.get_by_role("link", name=re.compile(r"Download PDF", re.I))
    if pdf_link.count() == 0:
        pdf_link = page.locator("a[href*='egnyte.com/dl/'], a[href*='.pdf']")
    if pdf_link.count() == 0:
        return None, None, "No PDF link found on the template page."

    href = urljoin(page.url, pdf_link.first.get_attribute("href") or "")
    if "egnyte.com/dl/" in href:
        saved = _download_from_egnyte(page, href, dest)
        if saved:
            return saved[0], saved[1], None

    if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
        response = page.request.get(href)
        if response.ok:
            saved = _save_pdf_bytes(dest, response.body())
            if saved:
                return saved[0], saved[1], None

    try:
        with page.expect_download(timeout=20000) as download_info:
            pdf_link.first.click()
        download = download_info.value
        download.save_as(dest)
        if dest.is_file() and dest.read_bytes()[:4] == b"%PDF":
            return relative_pdf_path(slug), dest.stat().st_size, None
        return None, None, "Download was not a PDF."
    except PlaywrightTimeout:
        if _looks_like_lead_form(page):
            return None, None, "PDF download is behind a lead-generation form."
        return None, None, "Timed out waiting for the PDF download."


def _needs_download(
    card: dict, prior: dict | None, incremental: bool
) -> tuple[bool, str]:
    slug = card["slug"]
    pdf_ok = bool(
        prior
        and prior.get("pdf_path")
        and pdf_path_for(slug).is_file()
    )
    if not incremental or prior is None or not pdf_ok:
        if prior is None:
            return True, "added"
        if not pdf_ok:
            return True, "updated"
        return True, "updated"
    listing_date = card.get("published_on") or ""
    stored_date = prior.get("published_on") or ""
    if not listing_date:
        return True, "updated"
    if listing_date != stored_date:
        return True, "updated"
    return False, "unchanged"


def _keep_existing(card: dict, prior: dict, status: str) -> dict:
    record = dict(prior)
    record["title"] = card.get("title") or prior.get("title") or card["slug"]
    record["category"] = card.get("category") or prior.get("category") or ""
    record["kind"] = card.get("kind") or prior.get("kind") or "Policy template"
    record["published_on"] = card.get("published_on") or prior.get("published_on") or ""
    record["source_url"] = card.get("source_url") or prior.get("source_url")
    record["refresh_status"] = status
    record["error"] = None
    return record


def scrape(base_url: str | None = None, *, incremental: bool = True) -> dict:
    source_url = (base_url or SANS_BASE_URL).rstrip("/")
    ensure_dirs()
    scraped_at = utc_now()
    existing = {
        item.get("slug"): item
        for item in load_catalog().get("policies", [])
        if item.get("slug")
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        page.goto(source_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        _dismiss_cookies(page)
        page.wait_for_selector(".c-lister-showing-x-of-y, .c-resource-card", timeout=20000)

        showing_before, listed_before, total_before = _showing(page)
        print(f"Opened {source_url}")
        print(f"Before Show 60: {showing_before}")
        _click_show_60(page)
        showing_text, listed, total = _wait_for_full_list(page, listed_before)
        print(f"After Show 60: {showing_text}")
        page.wait_for_function(
            "expected => document.querySelectorAll('.c-resource-card').length >= expected",
            arg=max(listed, 1),
            timeout=15000,
        )
        if listed < total:
            print(
                f"Warning: listing still shows {listed} of {total}; continuing with visible cards."
            )
        if total != total_before:
            print(f"Total count changed from {total_before} to {total}.")

        cards = _extract_listing_cards(page, source_url)
        print(f"Found {len(cards)} template links.")
        if not cards:
            browser.close()
            raise RuntimeError("No policy template links found after clicking Show 60.")

        policies: list[dict] = []
        listed_slugs: set[str] = set()
        stats = {"added": 0, "updated": 0, "unchanged": 0, "kept": 0, "failed": 0}

        for index, card in enumerate(cards, start=1):
            slug = card["slug"]
            listed_slugs.add(slug)
            prior = existing.get(slug)
            download, status = _needs_download(card, prior, incremental)
            print(
                f"[{index}/{len(cards)}] {card['title']} ({slug}) "
                f"{card.get('published_on') or 'unknown date'} → {status}"
            )
            if not download and prior:
                policies.append(_keep_existing(card, prior, "unchanged"))
                stats["unchanged"] += 1
                continue

            record = {
                **card,
                "pdf_path": prior.get("pdf_path") if prior else None,
                "pdf_bytes": prior.get("pdf_bytes") if prior else None,
                "summary": prior.get("summary") if prior else "",
                "scraped_at": scraped_at,
                "error": None,
                "refresh_status": status,
                "previous_published_on": (prior or {}).get("published_on") or None,
            }
            try:
                page.goto(card["source_url"], wait_until="domcontentloaded")
                page.wait_for_timeout(500)
                _dismiss_cookies(page)
                detail = _extract_detail(page)
                if detail["title"]:
                    record["title"] = detail["title"]
                if detail["published_on"]:
                    record["published_on"] = detail["published_on"]
                if detail["summary"]:
                    record["summary"] = detail["summary"]
                still_same = (
                    incremental
                    and prior
                    and record["published_on"]
                    and record["published_on"] == (prior.get("published_on") or "")
                    and prior.get("pdf_path")
                    and pdf_path_for(slug).is_file()
                )
                if still_same:
                    record = _keep_existing(card, prior, "unchanged")
                    record["summary"] = detail["summary"] or prior.get("summary") or ""
                    stats["unchanged"] += 1
                    print("  date unchanged after detail page; keeping PDF")
                else:
                    pdf_path, pdf_bytes, error = _download_pdf(page, slug)
                    record["pdf_path"] = pdf_path
                    record["pdf_bytes"] = pdf_bytes
                    record["error"] = error
                    if error:
                        stats["failed"] += 1
                        print(f"  PDF skipped: {error}")
                    else:
                        stats[status] += 1
                        print(f"  Saved {pdf_path} ({pdf_bytes} bytes)")
            except Exception as exc:  # noqa: BLE001 — keep the rest of the catalog
                record["error"] = str(exc)
                stats["failed"] += 1
                print(f"  Error: {exc}")
            policies.append(record)
            time.sleep(0.6)

        browser.close()

    for slug, prior in existing.items():
        if slug not in listed_slugs:
            kept = dict(prior)
            kept["refresh_status"] = "kept"
            policies.append(kept)
            stats["kept"] += 1

    catalog = {
        "source_url": source_url,
        "showing_text": showing_text,
        "listed": listed,
        "total": total,
        "scraped_at": scraped_at,
        "last_check": {"checked_at": scraped_at, **stats},
        "policies": policies,
    }
    path = save_catalog(catalog)
    saved = sum(1 for item in policies if item.get("pdf_path"))
    print(
        f"Wrote {path} ({saved}/{len(policies)} PDFs; "
        f"{stats['added']} added, {stats['updated']} updated, "
        f"{stats['unchanged']} unchanged, {stats['kept']} kept)."
    )
    return catalog


def main() -> None:
    import sys

    scrape(incremental="--full" not in sys.argv)


if __name__ == "__main__":
    main()
