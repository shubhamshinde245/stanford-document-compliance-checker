from __future__ import annotations

import re
from dataclasses import dataclass

from backend.retrieve.text import PageText

WORDS_PER_CHUNK = 450
OVERLAP_WORDS = 80
WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    page: int
    index: int


def chunk_pages(pages: list[PageText], slug: str) -> list[Chunk]:
    words: list[tuple[int, str]] = []
    for page in pages:
        for word in WORD_RE.findall(page.text):
            words.append((page.page, word))
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 1
    total = len(words)
    step = max(WORDS_PER_CHUNK - OVERLAP_WORDS, 1)
    while start < total:
        end = min(start + WORDS_PER_CHUNK, total)
        window = words[start:end]
        page = window[0][0]
        text = " ".join(token for _, token in window)
        chunks.append(
            Chunk(
                chunk_id=f"{slug}:p{page}:c{index}",
                text=text,
                page=page,
                index=index,
            )
        )
        if end >= total:
            break
        start += step
        index += 1
    return chunks
