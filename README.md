# Stanford Document Compliance Checker

FastAPI backend and Next.js frontend that check HTML documents against Stanford-oriented accessibility, identity, and structure rules. Beautiful Soup parses the HTML.

## Stack

- **Backend:** FastAPI, Beautiful Soup, Playwright, uv
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS 4
- **LLM:** [Stanford AI API Gateway](https://aiapi-dev.stanford.edu/) (`AI_GATEWAY_API_KEY`) — one key for GPT, Claude, Gemini, and other models
- **Standards library:** official [SANS / CRF security policy templates](https://www.sans.org/information-security-policy)

## Why this standards source

This app is for university teams that submit operating procedures, then review findings with a mix of **technical and non-technical** stakeholders (policy owners, unit admins, security staff). The library has to be current, easy to navigate, and easy to cite in a findings report.

| Source | Decision | Audience fit | Freshness | Why it wins or loses |
| --- | --- | --- | --- | --- |
| [Official SANS / CRF policy templates](https://www.sans.org/information-security-policy) | **Chosen** | Written as operating policies in plain language. Technical and non-technical reviewers can read a requirement and map it to a procedure. | Maintained. Official templates updated February 2026. | Findings can cite language the institution can still stand behind. |
| [SANS GitHub mirror](https://github.com/deepanshusood/SANS-Security-Policy-Templates) | Rejected | Same policy shape as SANS, so navigation would be fine. | Last pushed October 2021. No material updates since. | Convenient (no download form), but a four- to five-year-old snapshot would train users on stale requirements and make citations look authoritative when they are not. |
| [NIST SP 800-53 (OSCAL)](https://github.com/usnistgov/oscal-content) | Rejected | Built for assessors. Nested control IDs are hard for non-technical stakeholders; even technical reviewers spend time decoding IDs instead of judging a procedure. | Current and machine-readable. | Right source for a control-assessment platform, wrong source here. If a finding must quote the requirement next to evidence, the text has to be readable in the UI. 800-53 fails that test. |

Tradeoff we accept: SANS templates are not a machine-readable OSCAL feed, so ingest is a bit more work than loading NIST JSON. That cost is worth it so every verdict can point at a requirement a department lead can actually read.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- A Stanford AI API Gateway key

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
SANS_BASE_URL=https://www.sans.org/information-security-policy
```

Refresh the offline SANS library (PDFs + metadata under `data/sans-policies/`):

```bash
make scrape
```

The home page is the document checker. Open **Policies** in the sidebar to browse the catalog.

`.env.local` is gitignored. Individual targets: `make backend`, `make frontend`, `make install`, `make scrape`.

The Next.js app proxies `/api/*` to FastAPI (`API_URL`, default `http://127.0.0.1:8000`).

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health (`ai_gateway` is `configured` or `missing`) |
| `GET` | `/api/rules` | Rule catalog |
| `POST` | `/api/check` | Check an HTML document |
| `GET` | `/api/policies` | Scraped SANS policy catalog (metadata + local PDF paths) |
| `GET` | `/api/policies/{slug}/pdf` | Downloaded policy PDF |

`POST /api/check` body:

```json
{
  "html": "<!DOCTYPE html>...",
  "filename": "policy.html"
}
```
