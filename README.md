# Stanford Document Compliance Checker

FastAPI backend and Next.js frontend that rank an uploaded procedure against parked SANS policy embeddings. After each template PDF is saved, the backend extracts Purpose and Scope, embeds that summary, and stores one vector per policy. Upload a PDF, DOCX, HTML, Markdown, or text file; the API chunks it, embeds the chunks, and returns every SANS policy ordered by cosine confidence against those summaries.

This pass is retrieval only. It does not issue aligned / contradicted / missing / flagged verdicts.

## Stack

- **Backend:** FastAPI, pypdf, python-docx, NumPy cosine match, Playwright, uv
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS 4
- **LLM:** [Stanford AI API Gateway](https://aiapi-dev.stanford.edu/) (`AI_GATEWAY_API_KEY`) — embeddings default to `text-embedding-ada-002`. Anthropic has no embeddings API; the router falls back to Stanford Gateway or OpenAI.
- **Standards library:** official [SANS / CRF security policy templates](https://www.sans.org/information-security-policy)

## Why this standards source

This app is for university teams that submit operating procedures, then review findings with a mix of **technical and non-technical** stakeholders (policy owners, unit admins, security staff). The library has to be current, easy to navigate, and easy to cite in a findings report.

| Source | Decision | Audience fit | Freshness | Why it wins or loses |
| --- | --- | --- | --- | --- |
| [Official SANS / CRF policy templates](https://www.sans.org/information-security-policy) | **Chosen** | Written as operating policies in plain language. Technical and non-technical reviewers can read a requirement and map it to a procedure. | Maintained. Official templates updated February 2026. | Findings can cite language the institution can still stand behind. |
| [SANS GitHub mirror](https://github.com/deepanshusood/SANS-Security-Policy-Templates) | Rejected | Same policy shape as SANS, so navigation would be fine. | Last pushed October 2021. No material updates since. | Convenient (no download form), but a four- to five-year-old snapshot would train users on stale requirements and make citations look authoritative when they are not. |
| [NIST SP 800-53 (OSCAL)](https://github.com/usnistgov/oscal-content) | Rejected | Built for assessors. Nested control IDs are hard for non-technical stakeholders; even technical reviewers spend time decoding IDs instead of judging a procedure. | Current and machine-readable. | Right source for a control-assessment platform, wrong source here. If a finding must quote the requirement next to evidence, the text has to be readable in the UI. 800-53 fails that test. |

Tradeoff we accept: SANS templates are not a machine-readable OSCAL feed, so ingest is a bit more work than loading NIST JSON. That cost is worth it so every match can point at a requirement a department lead can actually read.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- A Stanford AI API Gateway key (needed to embed the library and query documents)

## Setup

```bash
make install
```

That installs Python deps, Playwright Chromium (for `make scrape`), and the Next.js app.

## Run

```bash
make start
```

That copies `.env.example` to `.env.local` if needed, then **merges any missing keys** (including `SANS_BASE_URL`) without overwriting an existing `AI_GATEWAY_API_KEY`. FastAPI listens on [http://127.0.0.1:8000](http://127.0.0.1:8000) and Next.js on [http://localhost:3000](http://localhost:3000). Ctrl+C stops both.

Paste your gateway key into `.env.local`:

```
AI_GATEWAY_API_KEY=your-key-here
AI_GATEWAY_BASE_URL=https://aiapi-dev.stanford.edu/
LLM_PROVIDER=stanford
SANS_BASE_URL=https://www.sans.org/information-security-policy
```

Refresh the offline SANS library (PDFs + metadata under `data/sans-policies/`):

```bash
make scrape
```

Park Purpose/Scope summary embeddings for those PDFs (writes `data/sans-policies/index.json` and `index.npz`, gitignored):

```bash
make index
```

`make index` embeds a slug only when the PDF bytes or the Settings embedding model changed. Each policy is one summary vector, not overlapping body windows. `POST /api/check` never embeds the library; if the index is missing or was built with a different model, the API returns HTTP 503 and asks you to run `make index`.

`make scrape` is incremental: it compares published dates on the SANS listing to the stored catalog and downloads a PDF only when a date changed, a policy is new, or a file is missing. After each successful download it extracts Purpose and Scope, parks that summary vector, and uses `gpt-5.6-sol` structured output to write safeguards to `data/sans-policies/safeguards/{slug}.csv`. After a successful scrape the API also refreshes stale index slugs in a background thread. Use `uv run python -m backend.scraper --full` to force every PDF.

While the API is running, a daily job also checks at **8:00 AM Pacific Time** (America/Los_Angeles). Change that time — or run a check immediately — from **Policies** in the sidebar.

The home page is the document checker (upload only). Open **Policies** in the sidebar to browse the catalog. Open **Settings** to pick the chat and embedding models the backend should always use.

`.env.local` is gitignored. Individual targets: `make backend`, `make frontend`, `make install`, `make scrape`, `make index`.

The Next.js app proxies `/api/*` to FastAPI (`API_URL`, default `http://127.0.0.1:8000`).

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health (`ai_gateway` is `configured` or `missing`) |
| `POST` | `/api/check` | Multipart file upload; rank against parked SANS embeddings |
| `GET` | `/api/policies` | Scraped SANS policy catalog (metadata + local PDF paths) |
| `GET` | `/api/policies/schedule` | Daily refresh time (Pacific) and last/next run |
| `PUT` | `/api/policies/schedule` | Set daily hour/minute and enabled flag |
| `POST` | `/api/policies/scrape` | Incremental date check; download PDFs only if dates changed |
| `GET` | `/api/policies/{slug}/safeguards` | Extracted safeguards (category + definition) |
| `GET` | `/api/policies/{slug}/pdf` | Downloaded policy PDF |
| `GET` | `/api/llm/settings` | Saved provider, chat model, embedding model, and effort |
| `PUT` | `/api/llm/settings` | Save those defaults |
| `GET` | `/api/llm/models` | Live model list from the current provider |
| `POST` | `/api/llm/chat` | Chat test through the backend router |
| `POST` | `/api/llm/embeddings` | Embedding test through the backend router |

`POST /api/check` is `multipart/form-data` with a `file` field (PDF, DOCX, HTML, Markdown, or text; max ~12 MB). Example:

```bash
curl -s -X POST http://127.0.0.1:8000/api/check \
  -F "file=@procedure.pdf"
```

Response:

```json
{
  "filename": "procedure.pdf",
  "model": "text-embedding-ada-002",
  "matches": [
    {
      "slug": "network-device-management-policy",
      "title": "Network Device Management Policy",
      "category": "Network",
      "confidence": 87.4,
      "score": 0.874,
      "snippet": "Title: Network Device Management Policy Purpose: … Scope: …",
      "chunk_id": "network-device-management-policy:summary",
      "source_url": "https://www.sans.org/information-security-policy/network-device-management-policy"
    }
  ]
}
```
