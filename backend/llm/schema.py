from __future__ import annotations

import re
from typing import Any

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_COLUMNS = 16
MAX_DESCRIPTION = 600

VERDICTS = ("aligned", "contradicted", "missing", "flagged")

# The exercise grades these four fields, so they are always present and always
# first. Their descriptions stay editable — the names do not.
LOCKED_COLUMNS: tuple[dict[str, str], ...] = (
    {
        "name": "requirement_id",
        "description": (
            "The id of the requirement being judged, copied exactly from the "
            "requirement given in the prompt."
        ),
    },
    {
        "name": "verdict",
        "description": (
            "aligned when the procedure satisfies the requirement, contradicted "
            "when it states something that conflicts with it, missing when the "
            "procedure never addresses it, flagged when the evidence is ambiguous "
            "and a person should review it."
        ),
    },
    {
        "name": "requirement_quote",
        "description": (
            "The sentence from the standard that states this requirement, quoted "
            "verbatim."
        ),
    },
    {
        "name": "evidence_quote",
        "description": (
            "The sentence from the uploaded document that supports the verdict, "
            "quoted verbatim from one of the supplied chunks. Empty string only "
            "when the verdict is missing."
        ),
    },
)

DEFAULT_CUSTOM_COLUMNS: tuple[dict[str, str], ...] = (
    {
        "name": "rationale",
        "description": (
            "One or two sentences explaining why this verdict follows from the "
            "quoted evidence."
        ),
    },
)

LOCKED_NAMES = frozenset(column["name"] for column in LOCKED_COLUMNS)

# Provenance is not user-configurable: every row must say which retrieved chunks
# it used so the report can link back and highlight them.
SOURCES_PROPERTY: dict[str, Any] = {
    "type": "array",
    "description": (
        "Every retrieved chunk you actually used to decide this row. Copy chunk "
        "ids exactly as they appear in the context block. Never invent one."
    ),
    "items": {
        "type": "object",
        "properties": {
            "chunk_id": {
                "type": "string",
                "description": "The id of a chunk from the context block.",
            },
            "quote": {
                "type": "string",
                "description": (
                    "The span of that chunk you relied on, quoted verbatim so it "
                    "can be located and highlighted in the source document."
                ),
            },
        },
        "required": ["chunk_id", "quote"],
        "additionalProperties": False,
    },
}

GROUNDING_RULES = (
    "Quote verbatim. Never paraphrase inside a field whose name ends in _quote.",
    "Every evidence_quote must appear character for character inside one of the "
    "supplied chunks. If you cannot find such a span, the verdict is not aligned "
    "or contradicted.",
    'List in "sources" every chunk id you actually used, exactly as given. An '
    "empty list is correct only when the verdict is missing.",
    "Never invent a chunk id, a page number, or a requirement id.",
    "When the chunks are ambiguous or conflict with each other, answer flagged "
    "rather than guessing.",
    "Answer only from the supplied chunks and the requirement. Do not use outside "
    "knowledge about what the policy ought to say.",
)


def default_columns() -> list[dict[str, str]]:
    return [dict(column) for column in (*LOCKED_COLUMNS, *DEFAULT_CUSTOM_COLUMNS)]


def normalize_columns(value: Any, *, strict: bool) -> list[dict[str, str]]:
    """Merge saved columns onto the locked set.

    Locked columns keep their position and name; a saved row matching a locked
    name only overrides its description. With ``strict`` a bad row raises, which
    is what the save endpoint wants. Without it a bad row is dropped, so a
    hand-edited settings file cannot brick startup.
    """
    rows = value if isinstance(value, list) else []
    overrides: dict[str, str] = {}
    custom: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        try:
            name, description = _read_row(row)
            if name in seen:
                raise ValueError(f"Duplicate column name {name!r}.")
        except ValueError:
            if strict:
                raise
            continue
        seen.add(name)
        if name in LOCKED_NAMES:
            overrides[name] = description
        else:
            custom.append({"name": name, "description": description})

    if len(custom) + len(LOCKED_COLUMNS) > MAX_COLUMNS:
        if strict:
            raise ValueError(
                f"Too many columns. The limit is {MAX_COLUMNS} including the "
                f"{len(LOCKED_COLUMNS)} required ones."
            )
        custom = custom[: MAX_COLUMNS - len(LOCKED_COLUMNS)]

    merged = [
        {
            "name": column["name"],
            "description": overrides.get(column["name"], column["description"]),
        }
        for column in LOCKED_COLUMNS
    ]
    merged.extend(custom)
    return merged


def _read_row(row: Any) -> tuple[str, str]:
    if not isinstance(row, dict):
        raise ValueError("Each column must be an object with name and description.")
    name = str(row.get("name") or "").strip().lower()
    description = " ".join(str(row.get("description") or "").split())
    if not NAME_RE.match(name):
        raise ValueError(
            f"Column name {name or '(empty)'!r} is invalid. Use lowercase letters, "
            "digits, and underscores, starting with a letter."
        )
    if not description:
        raise ValueError(f"Column {name!r} needs a description.")
    if len(description) > MAX_DESCRIPTION:
        raise ValueError(
            f"Description for {name!r} is too long ({len(description)} characters, "
            f"limit {MAX_DESCRIPTION})."
        )
    return name, description


def compile_json_schema(columns: list[dict[str, str]]) -> dict[str, Any]:
    """Build the response_format json_schema sent with every verdict call."""
    properties: dict[str, Any] = {}
    for column in columns:
        name = column["name"]
        if name == "verdict":
            properties[name] = {
                "type": "string",
                "enum": list(VERDICTS),
                "description": column["description"],
            }
        else:
            properties[name] = {
                "type": "string",
                "description": column["description"],
            }
    properties["sources"] = SOURCES_PROPERTY

    row = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    return {
        "name": "compliance_rows",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"rows": {"type": "array", "items": row}},
            "required": ["rows"],
            "additionalProperties": False,
        },
    }


def build_system_prompt(columns: list[dict[str, str]]) -> str:
    lines = [
        "You are a compliance analyst at a university.",
        "",
        "You are given one requirement from an official security standard and the "
        "chunks retrieved from an uploaded operating procedure. Decide how the "
        "procedure treats that requirement, and return one row per requirement in "
        'the "rows" array.',
        "",
        "Columns:",
    ]
    lines.extend(f"- {column['name']}: {column['description']}" for column in columns)
    lines.extend(
        [
            "- sources: " + str(SOURCES_PROPERTY["description"]),
            "",
            "Rules:",
        ]
    )
    lines.extend(f"- {rule}" for rule in GROUNDING_RULES)
    return "\n".join(lines)
