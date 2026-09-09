from __future__ import annotations

import asyncio
import sys

from backend.llm.providers import LLMError
from backend.retrieve.index import IndexBuildError, ensure_index


async def _run() -> int:
    try:
        status = await ensure_index()
    except IndexBuildError as exc:
        print(exc, file=sys.stderr)
        return 1
    except LLMError as extra:
        print(extra, file=sys.stderr)
        return 1
    print(status.message)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
