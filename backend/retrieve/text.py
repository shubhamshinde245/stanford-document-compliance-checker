from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".html", ".htm", ".docx"}


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


class ExtractError(ValueError):
    """The upload could not be turned into text."""


def extract_document(filename: str, data: bytes) -> list[PageText]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractError(
            "Unsupported file type. Upload a PDF, DOCX, HTML, Markdown, or text file."
        )
    if suffix == ".pdf":
        pages = _extract_pdf(data)
    elif suffix == ".docx":
        pages = _extract_docx(data)
    elif suffix in {".html", ".htm"}:
        pages = _extract_html(data)
    else:
        pages = _extract_plain(data)
    if not any(page.text.strip() for page in pages):
        raise ExtractError("Could not extract text from the document.")
    return pages


def _extract_pdf(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError("Could not read the PDF.") from exc
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        pages.append(PageText(page=index, text=text))
    return pages or [PageText(page=1, text="")]


def _extract_docx(data: bytes) -> list[PageText]:
    try:
        document = Document(BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError("Could not read the Word document.") from exc
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n".join(part for part in paragraphs if part)
    return [PageText(page=1, text=text)]


def _extract_html(data: bytes) -> list[PageText]:
    soup = BeautifulSoup(_decode(data), "html.parser")
    return [PageText(page=1, text=soup.get_text(" ", strip=True))]


def _extract_plain(data: bytes) -> list[PageText]:
    return [PageText(page=1, text=_decode(data))]


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")
