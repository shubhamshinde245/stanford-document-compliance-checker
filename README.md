# Stanford Document Compliance Checker

FastAPI backend and Next.js frontend that check HTML documents against Stanford-oriented accessibility, identity, and structure rules. Beautiful Soup parses the HTML.

## Stack

- **Backend:** FastAPI, Beautiful Soup, uv
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS 4
- **LLM:** [Stanford AI API Gateway](https://aiapi-dev.stanford.edu/) (`AI_GATEWAY_API_KEY`) — one key for GPT, Claude, Gemini, and other models

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- A Stanford AI API Gateway key

## Setup

```bash
uv sync
cd frontend && npm install
```

## Run

```bash
make start
```

That copies `.env.example` to `.env.local` if needed, then starts FastAPI on [http://127.0.0.1:8000](http://127.0.0.1:8000) and Next.js on [http://localhost:3000](http://localhost:3000). Ctrl+C stops both.

Paste your gateway key into `.env.local`:

```
AI_GATEWAY_API_KEY=your-key-here
AI_GATEWAY_BASE_URL=https://aiapi-dev.stanford.edu/
```

`.env.local` is gitignored. Individual targets: `make backend`, `make frontend`, `make install`.

The Next.js app proxies `/api/*` to FastAPI (`API_URL`, default `http://127.0.0.1:8000`).

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health (`ai_gateway` is `configured` or `missing`) |
| `GET` | `/api/rules` | Rule catalog |
| `POST` | `/api/check` | Check an HTML document |

`POST /api/check` body:

```json
{
  "html": "<!DOCTYPE html>...",
  "filename": "policy.html"
}
```
