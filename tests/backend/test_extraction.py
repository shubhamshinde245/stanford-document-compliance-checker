"""Upload -> text -> chunks, and Purpose/Scope parsing.

DESIGN.md records a finding worth keeping honest: a 341-word document produces
exactly one chunk at WORDS_PER_CHUNK = 450, so top-3 retrieval has nothing to
choose between. The chunking tests below pin the window arithmetic that causes
it, so a change to the constants is visible rather than silent.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document

from backend.retrieve.chunk import OVERLAP_WORDS, WORDS_PER_CHUNK, chunk_pages
from backend.retrieve.match import slug_from_filename, snippet_from
from backend.retrieve.sections import (
    build_summary_text,
    extract_purpose_and_scope,
    extract_safeguards_section,
)
from backend.retrieve.text import ExtractError, extract_document


def words(count: int, token: str = "word") -> str:
    return " ".join(f"{token}{i}" for i in range(count))


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


def test_a_short_document_is_one_chunk(pages):
    """The DESIGN.md finding, pinned."""
    chunks = chunk_pages(pages(words(341)), "doc")
    assert len(chunks) == 1


def test_a_document_at_the_window_size_is_still_one_chunk(pages):
    assert len(chunk_pages(pages(words(WORDS_PER_CHUNK)), "doc")) == 1


def test_one_word_past_the_window_splits(pages):
    assert len(chunk_pages(pages(words(WORDS_PER_CHUNK + 1)), "doc")) == 2


def test_consecutive_chunks_overlap(pages):
    chunks = chunk_pages(pages(words(WORDS_PER_CHUNK * 2)), "doc")
    first = chunks[0].text.split()
    second = chunks[1].text.split()
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]


def test_chunk_ids_carry_slug_page_and_index(pages):
    chunks = chunk_pages(pages(words(WORDS_PER_CHUNK * 2)), "my-doc")
    assert chunks[0].chunk_id == "my-doc:p1:c1"
    assert chunks[1].chunk_id.startswith("my-doc:p1:c2")


def test_chunk_ids_are_unique(pages):
    chunks = chunk_pages(pages(words(WORDS_PER_CHUNK * 5)), "doc")
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_a_chunk_is_attributed_to_the_page_it_starts_on(pages):
    chunks = chunk_pages(pages(words(500), words(500)), "doc")
    assert chunks[0].page == 1
    assert any(chunk.page == 2 for chunk in chunks)


def test_every_word_survives_chunking(pages):
    """No text may be dropped between the upload and the model."""
    source = words(1200)
    chunks = chunk_pages(pages(source), "doc")
    seen = {token for chunk in chunks for token in chunk.text.split()}
    assert seen == set(source.split())


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t"])
def test_a_blank_document_produces_no_chunks(pages, text):
    assert chunk_pages(pages(text), "doc") == []


def test_no_chunks_from_no_pages():
    assert chunk_pages([], "doc") == []


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------


def test_markdown_is_read_as_plain_text():
    pages = extract_document("policy.md", b"# Title\n\nSome body text.")
    assert "Some body text." in pages[0].text


def test_html_tags_are_stripped():
    html = b"<html><body><h1>Title</h1><p>Body <b>text</b>.</p><script>x=1</script></body></html>"
    text = extract_document("policy.html", html)[0].text
    assert "Title" in text and "Body" in text
    assert "<p>" not in text


def test_docx_paragraphs_are_joined():
    document = Document()
    document.add_paragraph("First paragraph.")
    document.add_paragraph("")
    document.add_paragraph("Second paragraph.")
    buffer = BytesIO()
    document.save(buffer)
    text = extract_document("policy.docx", buffer.getvalue())[0].text
    assert "First paragraph." in text and "Second paragraph." in text


def test_invalid_utf8_is_replaced_not_raised():
    pages = extract_document("policy.txt", b"caf\xe9 policy")
    assert "policy" in pages[0].text


@pytest.mark.parametrize("name", ["policy.exe", "policy.csv", "policy", "policy.PDF.zip"])
def test_an_unsupported_extension_is_refused(name):
    with pytest.raises(ExtractError, match="Unsupported file type"):
        extract_document(name, b"whatever")


@pytest.mark.parametrize("name", ["a.PDF", "a.Md", "a.HTML", "a.DOCX", "a.TXT"])
def test_extension_matching_is_case_insensitive(name):
    """Only the suffix check runs before parsing, so a bad body raises later."""
    with pytest.raises(ExtractError):
        extract_document(name, b"")


@pytest.mark.parametrize("data", [b"", b"   ", b"\n\n"])
def test_an_empty_document_is_refused(data):
    with pytest.raises(ExtractError, match="Could not extract text"):
        extract_document("policy.txt", data)


def test_a_corrupt_pdf_is_refused_with_a_readable_message():
    with pytest.raises(ExtractError, match="Could not read the PDF"):
        extract_document("policy.pdf", b"this is definitely not a pdf")


def test_a_corrupt_docx_is_refused_with_a_readable_message():
    with pytest.raises(ExtractError, match="Could not read the Word document"):
        extract_document("policy.docx", b"not a docx either")


# --------------------------------------------------------------------------
# Purpose and Scope
# --------------------------------------------------------------------------


POLICY = """Access Management Policy

1. Purpose
This policy establishes how access is granted and revoked.

2. Scope
It applies to all staff, contractors, and third parties.

3. Policy
Everything below here is not part of Purpose or Scope.
"""


def test_purpose_and_scope_are_pulled_from_their_headings(pages):
    sections = extract_purpose_and_scope(pages(POLICY))
    assert "granted and revoked" in sections.purpose
    assert "contractors" in sections.scope
    assert sections.fallback is False


def test_a_following_heading_ends_the_section(pages):
    sections = extract_purpose_and_scope(pages(POLICY))
    assert "not part of Purpose" not in sections.purpose
    assert "not part of Purpose" not in sections.scope


def test_an_inline_heading_is_understood(pages):
    text = "Purpose: Establish the rules.\nScope: Everyone at the university.\nPolicy\nBody."
    sections = extract_purpose_and_scope(pages(text))
    assert "Establish the rules." in sections.purpose
    assert "Everyone at the university." in sections.scope


def test_a_combined_heading_fills_both_fields(pages):
    text = "Purpose and Scope\nThis covers why and who.\nPolicy\nBody."
    sections = extract_purpose_and_scope(pages(text))
    assert "why and who" in sections.purpose
    assert "why and who" in sections.scope


def test_a_document_with_no_purpose_heading_falls_back_to_page_one(pages):
    sections = extract_purpose_and_scope(pages("Just some prose with no headings."))
    assert sections.fallback is True
    assert "Just some prose" in sections.purpose


def test_whitespace_is_collapsed(pages):
    sections = extract_purpose_and_scope(pages("Purpose\nOne    two\n\nthree\nPolicy\nx"))
    assert sections.purpose == "One two three"


def test_safeguards_section_is_extracted(pages):
    text = "Purpose\nWhy.\nSafeguards\n1. Do this. 2. Do that.\nDefinitions\nWords."
    body = extract_safeguards_section(pages(text))
    assert "Do this" in body and "Do that" in body
    assert "Words." not in body


def test_safeguards_falls_back_to_the_whole_document(pages):
    """No Safeguards heading means extract from everything rather than nothing."""
    body = extract_safeguards_section(pages("Purpose\nWhy.\nPolicy\nControls live here."))
    assert "Controls live here." in body


def test_summary_text_omits_empty_fields():
    text = build_summary_text(title="A Policy", category="", purpose="Why.", scope="")
    assert "Title: A Policy" in text
    assert "Purpose: Why." in text
    assert "Category:" not in text
    assert "Scope:" not in text


# --------------------------------------------------------------------------
# Filename and snippet helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Privileged Account Procedure.md", "privileged-account-procedure"),
        ("weird__name!!.pdf", "weird-name"),
        ("/tmp/nested/path/doc.txt", "doc"),
        ("....md", "document"),
        ("!!!.txt", "document"),
    ],
)
def test_slug_from_filename(filename, expected):
    assert slug_from_filename(filename) == expected


def test_snippet_collapses_whitespace():
    assert snippet_from("one\n\ttwo   three") == "one two three"


def test_a_long_snippet_is_truncated_with_an_ellipsis():
    snippet = snippet_from(words(500), limit=50)
    assert len(snippet) <= 50
    assert snippet.endswith("...")


def test_a_short_snippet_is_untouched():
    assert snippet_from("short text", limit=50) == "short text"
