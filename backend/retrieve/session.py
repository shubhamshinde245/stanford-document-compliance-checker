from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from uuid import uuid4

import numpy as np

from backend.models import PolicyMatch
from backend.retrieve.chunk import Chunk

MAX_SESSIONS = 8


@dataclass
class RankedCheck:
    check_id: str
    filename: str
    chunks: list[Chunk]
    embeddings: np.ndarray
    matches: list[PolicyMatch]
    matched: bool


_SESSIONS: OrderedDict[str, RankedCheck] = OrderedDict()


def store_check(
    *,
    filename: str,
    chunks: list[Chunk],
    embeddings: np.ndarray,
    matches: list[PolicyMatch],
    matched: bool,
) -> RankedCheck:
    record = RankedCheck(
        check_id=str(uuid4()),
        filename=filename,
        chunks=chunks,
        embeddings=np.asarray(embeddings, dtype=np.float32),
        matches=list(matches),
        matched=matched,
    )
    _SESSIONS[record.check_id] = record
    while len(_SESSIONS) > MAX_SESSIONS:
        _SESSIONS.popitem(last=False)
    return record


def get_check(check_id: str | None) -> RankedCheck | None:
    if not check_id:
        return None
    return _SESSIONS.get(check_id)
