# Design

How the Stanford Document Compliance Checker is put together, why each load-bearing
choice was made, and what I would build next.

For the click-by-click flow, cosine matching math, on-disk embedding layout, and a
worked example with both a stakeholder and an engineer reading, see
[HOW_IT_WORKS.md](HOW_IT_WORKS.md). The same explainer lives in the app under
**How it works**.

The app answers two questions about an uploaded operating procedure:

1. **Which security standard does this document belong to?** (`POST /api/check`)
2. **Which requirements of that standard does it actually satisfy?** (`POST /api/evaluate`)

Everything below follows from one constraint: a compliance finding is only useful if
a human reviewer can trace it back to a sentence in a real document. That rules out an
architecture where the model is trusted, and it rules out one where the answer changes
between two runs on the same inputs.

Each of the sixteen decisions below carries a **Tradeoff / Impact** table directly under its title.
The impact column is not theoretical — the figures come from an end-to-end browser run
against the live app, recorded in [Verified behavior](#verified-behavior).

---

## Data flow

The central split is **offline vs. online**. Nothing in the request path touches
sans.org, parses a policy PDF, or embeds the standards library.

```
OFFLINE  (make scrape / make index / daily 08:00 PT cron)

  sans.org listing
        │
        │  published date changed?  ──no──▶  keep existing PDF, skip everything
        │
       yes
        ▼
   download PDF ──▶ ONE extract_document() pass over the bytes
                          │
                          ├─▶ Purpose + Scope ──▶ embed ──▶ index.json + index.npz
                          │                                  (one vector per policy)
                          │
                          └─▶ Safeguards section ──▶ gpt-5.6-sol ──▶ safeguards/{slug}.csv
                                                                     (one file per policy)

        both outputs stamped with the same pdf_sha256


ONLINE  (per request, never leaves local disk except for the LLM calls)

  upload ──▶ extract ──▶ chunk (450 words, 80 overlap) ──▶ embed chunks
                                                                │
                                    cosine vs. 36 parked summary vectors
                                                                │
                                                                ▼
                                              ranked policies + check_id      [/api/check]
                                                                │
                       ┌────────────────────────────────────────┘
                       │  chunks + embeddings cached under check_id
                       ▼
   read safeguards CSV ──▶ embed each requirement ──▶ top-3 chunks per requirement
                                                                │
                                            batched judge calls (6 per batch, 2 concurrent)
                                                                │
                                              verify every quote against its chunk
                                                                │
                                                                ▼
                                       aligned / contradicted / missing / flagged   [/api/evaluate]
```

---

## Decisions

### 1. `uv` instead of pip or Poetry

| Tradeoff | Impact on the system |
| --- | --- |
| One more tool to install before anything runs, and `uv` is young relative to pip. | **Measured: `uv sync` resolves 37 packages in 7ms and completes in 35ms warm.** Restarting the backend costs nothing, so `--reload` development is viable and a fresh clone reaches a running app in one command. The exact lockfile means the demo behaves identically on a reviewer's machine. If `uv` ever became a liability, exporting to `requirements.txt` is mechanical — the lockfile is the escape hatch. |

**Context.** The app is a demo someone else has to clone and run, and I restart it
constantly while developing.

**Decision.** `pyproject.toml` + `uv.lock` (37 locked packages), `make install` is
`uv sync`, and every entry point runs through `uv run`.

**Why.** Resolution and install are near-instant against a warm cache, and the lockfile
is exact. `uv run` also means there is no `activate` step to forget and no ambient
interpreter to get wrong.

### 2. A provider router, not a vendor SDK

| Tradeoff | Impact on the system |
| --- | --- |
| A lowest-common-denominator interface. Anthropic loses `reasoning_effort` (discarded at `providers.py:325`) and native structured output — its JSON schema is appended to the prompt as text instead. | Provider-specific features must be emulated or given up, so the app cannot use a capability only one vendor has. In exchange, all four call sites — indexing, safeguard extraction, retrieval, judging — are provider-agnostic, and switching vendors is a dropdown rather than a refactor. **The unfinished half has a visible cost: Ollama appears in Settings but returns 501, so the app cannot currently run offline.** |

**Context.** The Stanford AI API Gateway is a **dev** endpoint (`aiapi-dev.stanford.edu`).
Building directly against one vendor's SDK would mean the app is dead whenever that
endpoint is.

**Decision.** `backend/llm/router.py` exposes a single `llm` object with `chat()`,
`embed()`, and `embed_many()`. Every call site goes through it and never imports a
provider. Behind it, `backend/llm/providers.py` holds `OpenAICompatibleProvider` (shared
by Stanford Gateway and OpenAI, since the gateway speaks the OpenAI wire format),
`AnthropicProvider`, and `OllamaProvider`.

**Current state, stated plainly.** This is a *switchboard*, not yet automatic failover.
The active provider is a persisted setting in `data/llm-settings.json`, changeable from
`/settings` without a restart. The one automatic hop that exists today is embeddings-only:
`_embed_provider()` (`backend/llm/router.py:47`) routes away from Anthropic to Stanford,
then OpenAI, because Anthropic has no embeddings API at all. `OllamaProvider` is a
deliberate placeholder — every method raises 501 and the settings store rejects it at
save time (`backend/llm/store.py:34`). Real health-checked failover is item 2 under
[What I would do next](#what-i-would-do-next).

**Why it still earns its place unfinished.** The abstraction is the expensive part and it
is done. Adding Ollama is filling in one class against an interface four call sites
already depend on.

### 3. One extraction pass per policy, two outputs

| Tradeoff | Impact on the system |
| --- | --- |
| The two outputs are coupled. Changing safeguard extraction alone still requires re-running the whole pass. | A dedicated repair path had to be written to cover the gap: `_backfill_safeguards()` (`backend/retrieve/index.py:345`) exists purely to handle a policy whose embedding is current but whose CSV is not. That is real complexity bought by the coupling. What it buys back is that **the vector and the requirement list can never describe different versions of a PDF** — a whole class of "the score disagrees with the findings" bug is structurally impossible. |

**Context.** Each policy PDF yields two different things the app needs: a vector for
routing, and a list of requirements for judging. The obvious implementation walks the PDF
twice.

**Decision.** `ensure_index()` (`backend/retrieve/index.py:248-293`) calls
`extract_document()` **once**, then derives both outputs from the same in-memory `pages`.
`upsert_summary_chunk()` does the identical pair for a single policy mid-scrape.

**Why.** PDF text extraction is the slow, flaky step and the one most likely to produce
subtly different output on a retry. Doing it once means the vector and the requirement
list are provably derived from the same bytes. Both are stamped with the same
`pdf_sha256`, so if one is stale, both are.

### 4. One CSV per policy, not one shared requirements table

| Tradeoff | Impact on the system |
| --- | --- |
| No cross-policy query without loading all 36 files. There is no way to ask "which policies mention encryption at rest" without a full scan. | At 36 policies this costs nothing measurable — `load_safeguards()` reads one file per request. It would become the binding constraint somewhere around a few thousand policies, at which point this is the first thing to replace. The payoff is that **the non-deterministic LLM step is frozen to disk**: `/api/evaluate` re-runs return the identical requirement set, and a bad extraction shows up as a reviewable line in a git diff rather than as drifting behavior. |

**Context.** Safeguard extraction is an LLM call, and LLM calls are not deterministic.
Requirements from 36 different policies have to stay separable.

**Decision.** `data/sans-policies/safeguards/{slug}.csv`, one file per policy, columns
`slug,title,pdf_sha256,category,definition`. Written atomically via a `.tmp` file and
`replace()`.

**Why.**

- **Determinism where it counts.** The non-deterministic step runs *offline, once*. The
  variance is pushed to a build step a human can inspect, not into the request path.
- **No cross-contamination.** A file per slug means a requirement from the Encryption
  Standard cannot leak into an Acceptable Use evaluation.
- **Self-describing freshness.** `pdf_sha256` sits in every row, so
  `safeguards_are_current()` (`backend/retrieve/safeguards.py:84`) reads the first row and
  compares one hash. No side-car manifest to keep in sync.
- **Reviewable.** CSV diffs cleanly in git and opens in a spreadsheet.

### 5. Parked embeddings — the request path never embeds the library

| Tradeoff | Impact on the system |
| --- | --- |
| A setup step that must run before the first upload, and the index files are gitignored, so a fresh clone cannot serve a request until `make index` has run. | This is the single sharpest edge in onboarding: skip `make index` and every upload returns **HTTP 503**. It is deliberate — the alternative is silently rebuilding with a different embedding model and returning quietly wrong similarity scores. **Measured: ranking 36 policies costs 0.3–0.9s and exactly one embedding call**, and that number does not move whether the library holds 36 policies or 360. |

**Context.** The naive design embeds the standards library on demand and caches it. That
makes the first request after any restart pathologically slow and makes cost per request
unpredictable.

**Decision.** The library index is built by `make index` and lives in two row-aligned
files: `index.json` (metadata: slug, title, purpose, scope, `pdf_sha256`, embedding model)
and `index.npz` (a float32 matrix). `check_upload()` calls `inspect_index()` first and
returns **HTTP 503 telling you to run `make index`** rather than silently rebuilding.

**Why.** Predictable latency and predictable cost. A request embeds exactly the uploaded
document and nothing else.

Writes are atomic (tmp + `replace`) and guarded by a `threading.Lock`, because the
scheduled refresh can rebuild the index on a background thread while requests are served.
Staleness is checked at two levels: whole-index (format version and embedding model) and
per-slug (`pdf_sha256`).

### 6. One summary vector per policy, not body chunks

| Tradeoff | Impact on the system |
| --- | --- |
| A document matching a policy's *body* but not its stated scope ranks lower than it should. And any absolute score threshold is a property of the embedding model, not of the problem. | **The absolute threshold did break, and the fixtures caught it.** `MATCH_THRESHOLD = 50.0` sat far below anything ada-002 produces, so an unrelated tree-care calendar scored 71.6% and reported `matched: true` — the no-match branch was unreachable. Fixed by [decision 15](#15-matching-is-a-two-part-test-both-configurable): matching now also requires a lead over the runner-up, which is model-relative. The upside is unchanged: 36 vectors mean search is one `numpy` matmul and **there is no vector database in the stack**. |

**Context.** Stage 1 has to route a document to the right policy out of 36.

**Decision.** Each policy is represented by exactly one vector, embedded over
`Title / Category / Purpose / Scope` (`build_summary_text()`,
`backend/retrieve/sections.py:97`). Not overlapping windows of the policy body.

**Why.** Routing is a topic-matching problem, and Purpose/Scope is precisely the section
that states a policy's topic. Chunking the body would let boilerplate that every policy
shares — "Exceptions", "Enforcement", "Policy Compliance" — dominate the similarity and
blur the policies together.

Section detection is a heading classifier (`HEADING_KEYS` / `STOP_KEYS` in `sections.py`)
with a first-page fallback when a PDF has no recognizable Purpose heading — the fallback
is flagged in the build log rather than hidden.

### 7. The standards library refreshes on published-date change only

| Tradeoff | Impact on the system |
| --- | --- |
| A silent same-date edit to a PDF would be missed entirely. | Mitigated one layer down: the index and the CSV are both keyed on `pdf_sha256`, so if a changed PDF ever *is* downloaded, everything derived from it rebuilds. The residual risk is narrow — a same-date, same-URL content swap. The payoff is that the daily 08:00 job normally does **zero** downloads and zero LLM calls; the live schedule record reads `0 added, 0 updated, 36 unchanged, 0 kept`. A full re-scrape would instead be 36 downloads plus 36 embedding and extraction round-trips, every day, to discover nothing changed. |

**Context.** Running a full re-scrape daily to discover nothing changed is pure waste.

**Decision.** `_needs_download()` (`backend/scraper/sans.py:330`) compares the published
date on the sans.org listing against the stored catalog and downloads only when the policy
is new, the local PDF is missing, the date is absent, or the date changed. There is a
**second** check after opening the detail page (`backend/scraper/sans.py:475`) that can
downgrade an "updated" back to "unchanged" using the more authoritative detail-page date.
APScheduler runs it daily at 08:00 America/Los_Angeles, configurable from the Policies
page, and kicks off a background index rebuild afterwards.

**Why.** The published date is the cheapest correct invalidation signal the source offers.
The two-stage check exists because the listing date and the detail date occasionally
disagree, and catching it at the detail page saves a download that would be discarded.

Policies that disappear from the listing are **kept**, marked `refresh_status="kept"`,
rather than deleted. A scraper failure or a site redesign should not silently shrink the
compliance library.

### 8. SANS / CRF templates as the standards source

| Tradeoff | Impact on the system |
| --- | --- |
| SANS templates are not a machine-readable OSCAL feed, so ingest is a 585-line Playwright scraper rather than a JSON fetch. | This is the largest single piece of incidental complexity in the codebase: cookie-banner dismissal, a "Show 60" pagination control, an Egnyte download path, lead-form detection, and `%PDF` magic-byte verification all exist only because the source is a marketing site. It also adds a Chromium download to `make install`. Accepted so that **every finding quotes language a department lead can actually read** — which is what makes the report circulable. |

This app is for university teams that submit operating procedures, then review findings
with a mix of **technical and non-technical** stakeholders (policy owners, unit admins,
security staff). The library has to be current, easy to navigate, and easy to cite.

| Source | Decision | Audience fit | Freshness | Why it wins or loses |
| --- | --- | --- | --- | --- |
| [Official SANS / CRF policy templates](https://www.sans.org/information-security-policy) | **Chosen** | Written as operating policies in plain language. Technical and non-technical reviewers can read a requirement and map it to a procedure. | Maintained. Official templates updated February 2026. | Findings can cite language the institution can still stand behind. |
| [SANS GitHub mirror](https://github.com/deepanshusood/SANS-Security-Policy-Templates) | Rejected | Same policy shape as SANS, so navigation would be fine. | Last pushed October 2021. No material updates since. | Convenient (no download form), but a four- to five-year-old snapshot would train users on stale requirements and make citations look authoritative when they are not. |
| [NIST SP 800-53 (OSCAL)](https://github.com/usnistgov/oscal-content) | Rejected | Built for assessors. Nested control IDs are hard for non-technical stakeholders; even technical reviewers spend time decoding IDs instead of judging a procedure. | Current and machine-readable. | Right source for a control-assessment platform, wrong source here. If a finding must quote the requirement next to evidence, the text has to be readable in the UI. 800-53 fails that test. |

### 9. A configurable output schema with locked columns

| Tradeoff | Impact on the system |
| --- | --- |
| Strict `json_schema` support is not universal across providers. | This is the direct cause of decision 2's uneven provider support: Anthropic has to fall back to schema-in-the-prompt, which is weaker and can return malformed JSON. `_parse_rows()` therefore carries fence-stripping and brace-scanning salvage logic it would not need in a single-provider app. In return, **prompt and schema are generated from one list and cannot disagree**, and `GET /api/llm/output-schema` makes the exact prompt inspectable instead of folklore. |

**Context.** Different reviewers want different fields in a findings report, but four
fields are non-negotiable for the report to mean anything.

**Decision.** `backend/llm/schema.py` holds four **locked column names** —
`requirement_id`, `verdict`, `requirement_quote`, `evidence_quote` — whose *descriptions*
remain editable, plus any user-defined columns added from `/settings`. The list compiles
to a strict `json_schema` (`compile_json_schema()`) and a matching system prompt
(`build_system_prompt()`).

**Why.** Prompt and schema drifting apart is a classic failure in structured-output
systems; generating both from one list makes it impossible. Locking the four names means a
customized report is still a compliance report.

`normalize_columns()` is deliberately two-faced: `strict=True` on the save endpoint so bad
input is rejected with a clear message, `strict=False` on load so a hand-edited
`llm-settings.json` drops the bad row instead of bricking startup.

### 10. Verdicts are verified in code, not trusted

| Tradeoff | Impact on the system |
| --- | --- |
| Verbatim containment is strict. A model that quotes correctly but normalizes a Unicode dash gets downgraded, so some false flags land on a human. | **This is the most visible tradeoff in the product.** Measured on a 670-word procedure against a 16-requirement policy: 7 aligned, 1 contradicted, **8 flagged** — half the rows were routed to a human. That is the system erring toward review, by design. The alignment score is correspondingly conservative (43.8%), so the headline number understates compliance rather than overstating it. For a compliance tool that is the right direction to err, but it means the score is not a grade. |

**Context.** The model is asked to quote evidence from the uploaded document. Models
paraphrase when asked to quote, and cite sources they did not read.

**Decision.** `_normalize_finding()` (`backend/retrieve/evaluate.py:227`) treats every
returned row as untrusted input:

- An `aligned` or `contradicted` verdict whose `evidence_quote` is not **literally
  present** in one of the chunks that requirement retrieved (whitespace-collapsed
  containment, `quote_in_text()`) is downgraded to **`flagged`**.
- A row citing a `chunk_id` outside the set actually retrieved for that requirement is
  downgraded to **`flagged`**.
- A missing row becomes `missing`; an unrecognized verdict becomes `flagged`.
- A `missing` verdict has any unverifiable evidence stripped rather than shown.

**Why.** This is the line between a demo and something a compliance reviewer can act on. A
hallucinated citation becomes a flag for a human — never a pass. The system is allowed to
say "I am not sure"; it is not allowed to be confidently wrong. The `sources` array is
deliberately **not** user-configurable for the same reason: provenance is structural, not
a preference.

### 11. Two-stage API with a cached check session

| Tradeoff | Impact on the system |
| --- | --- |
| The cache is in-process and capped at 8 entries, so it does not survive a reload — and the backend runs with `--reload` in development. | `check_id` reuse is therefore **best-effort by design**, not a guarantee. What makes that acceptable rather than a bug is `_session_for()`, which transparently re-runs the check on a miss; the user sees a slower response, never an error. The cost is that a silent re-run doubles the embedding spend for that request, and nothing surfaces that it happened. |

**Context.** The user cannot say which policy to evaluate against until they have seen the
ranking. But embedding the document twice — once to rank, once to judge — is pure waste.

**Decision.** `/api/check` ranks and caches the document's chunks and embeddings under a
`check_id` (`backend/retrieve/session.py`, an `OrderedDict` capped at 8 entries).
`/api/evaluate` takes that `check_id` and reuses the vectors.

**Why.** It matches how the tool is actually used — upload, look at the ranking, pick a
policy, evaluate — while paying for embedding once.

### 12. Flat files over a database

| Tradeoff | Impact on the system |
| --- | --- |
| No concurrent writers and no transactions across files. | Every write path had to hand-roll its own safety: atomic tmp-and-replace in three separate modules, plus a `threading.Lock` around the index because the scheduled refresh writes from a background thread while requests read. **That lock is the ceiling of this design** — it is precisely the point at which a database becomes the right answer, and the app is sitting on it. Below that ceiling the payoff is real: every artifact is `cat`-able, diffable, and hand-editable in an emergency. |

**Context.** The app has real persistent state: a policy catalog, a schedule, an embedding
index, and 36 requirement files.

**Decision.** All of it is files under `data/`. No database, no ORM, no migrations.
`catalog.json`, `schedule.json`, `llm-settings.json`, `index.json` + `index.npz`, and
`safeguards/*.csv`.

**Why.** Thirty-six policies on a single node. Adding Postgres would add a service to run,
a schema to migrate, and a connection to configure, in exchange for nothing this workload
needs.

### 13. A Next.js proxy instead of a browser-side API URL

| Tradeoff | Impact on the system |
| --- | --- |
| The frontend cannot talk to the API without the Next server in front of it, so it is not a static export. The proxy also becomes a timeout boundary the backend does not have. | That boundary bit: Next's default rewrite timeout is 30s, but a large policy's evaluation runs for minutes, which surfaced as `ECONNRESET`. It forced two mitigations — `experimental.proxyTimeout` at 30 minutes in `next.config.ts`, and a dedicated route handler at `app/api/evaluate/route.ts` with its own `AbortSignal.timeout` and a 504 message. **A rewrite that was meant to be invisible infrastructure now owns real error-handling logic.** In exchange there is no CORS preflight and no API origin in the browser bundle. |

**Context.** The frontend has to reach FastAPI without hardcoding an origin that changes
per environment.

**Decision.** `frontend/next.config.ts` rewrites `/api/*` to `API_URL` (a **server-side**
variable, default `http://127.0.0.1:8000`). Every function in `frontend/src/lib/api.ts`
issues a same-origin relative `fetch`.

**Why.** No CORS preflight in the happy path, no `NEXT_PUBLIC_*` URL baked into the
browser bundle to rotate at deploy time, and the API origin stays a server concern.

### 14. The design system is an enforceable checklist, not a convention

| Tradeoff | Impact on the system |
| --- | --- |
| The skill file has to be kept in sync with `globals.css` by hand; nothing enforces that they agree. | Drift has already started in the small: `app-sidebar.tsx` hardcodes `bg-[#8C1515]` while `--color-sidebar-from` / `--color-sidebar-to` sit unused in `@theme`. The checklist blesses that hex, so it is sanctioned rather than accidental — but it shows the failure mode. The payoff held up under test: **the 390px viewport reported `scrollWidth` 390 against a 390 viewport — zero horizontal overflow** — and no second palette has appeared across nine commits. |

**Context.** The characteristic failure of AI-assisted UI work is a second palette, a
second radius scale, and a second typeface quietly appearing over a few sessions.

**Decision.** Tokens are defined exactly once, in `@theme` in
`frontend/src/app/globals.css` (Tailwind v4 — no JS config file). Alongside them,
`.cursor/skills/stanford-ui/` documents the Cardinal token table and component recipes
and — the part that matters — an explicit **Forbidden** list: no navy or electric blue, no
`rounded-sm` on cards, no hardcoded hex where a token exists, no Inter or Roboto.

**Why.** A checkable list turns visual drift into a review item with a yes-or-no answer,
instead of a matter of taste to be re-argued each session.

### 15. Matching is a two-part test, both configurable

| Tradeoff | Impact on the system |
| --- | --- |
| Two knobs instead of one, and the lead test is meaningless with a single candidate — it has to special-case that to "the whole score counts as separation". Both are also user-editable, so a reviewer can widen the gate until everything matches. | Replaces a rule that never fired. The unrelated fixture now returns `matched: false` at a 0.8 lead while both procedures pass at 5.7 and 5.1, so the no-match branch is reachable for the first time. Exposing the numbers in Settings is what makes the tradeoff honest — the rule is a calibration against one embedding model, not a truth, and the person who swaps the model is the one who has to retune it. The checker states the live rule on screen and, on a no-match, says which of the two tests failed and by how much. |

**Context.** Cosine similarity from `text-embedding-ada-002` is compressed into a narrow
band. Across all 36 policies an unrelated document spans 65.9–71.6% and a well-matched one
spans 74.6–91.5%. There is no absolute cutoff that separates them, because the bands
overlap — but the *shape* of the two distributions is completely different.

**Decision.** A document matches a standard only if the top policy passes both tests:

- `top >= match_min_confidence` — a floor, default 50.0. Rejects a uniformly weak field.
- `top - second >= match_min_gap` — a lead, default 2.5. Rejects a field where everything
  scores alike, which is exactly what an unrelated document looks like.

Both live in `data/llm-settings.json`, are editable under **Settings → Match rule**, and
are returned on every `/api/check` response alongside the measured gap.

**Why the lead works where the floor does not.** A real match stands clear of the field;
noise does not. Measured on the committed fixtures: 5.7 and 5.1 points of lead for the two
procedures, 0.8 for the tree-care calendar. That ratio holds regardless of where the model
happens to centre its scores, which is what makes it survive an embedding-model change.

A z-score of the top against the whole field was also tried and rejected: it scored 3.63 /
3.48 / 2.67, too close to separate reliably.

**Tradeoff on validation.** The save path rejects an out-of-range value with a message the
UI shows; the load path silently falls back to the default, so a hand-edited settings file
cannot brick startup. Same split as `normalize_columns()` in decision 9.

### 16. Tests fake the provider rather than skipping without a key

| Tradeoff | Impact on the system |
| --- | --- |
| The fake router is a second implementation of the provider contract, so it can drift from the real one and assert a shape production never returns. The suite proves the pipeline's logic, not that Stanford Gateway still answers. | 326 tests run in about three seconds with no key, no network, and no built index, so the suite is runnable on a machine that has never been configured — which is the only way it gets run before every commit rather than after a failure. The alternative, `skipif` on a missing key, produces a green run that tested nothing; the one thing worse than no tests is a suite that reports success while silently skipping. Contract drift is the accepted cost, and it is the argument for the live smoke test in [next steps](#what-i-would-do-next). |

**Context.** Every interesting path in this codebase runs through an LLM call: ranking
embeds the upload, evaluation embeds each requirement and then judges in batches. A test
suite that needs a real key tests nothing on a fresh clone.

**Decision.** `tests/backend/conftest.py` holds the two rules the whole suite obeys.
Nothing touches the network — `llm` is replaced by a `FakeLLM` whose `embed_many` returns
caller-supplied vectors, so a test dictates the exact similarity field it wants to assert
on. Nothing touches real `data/` — settings, saved reports, and the parked index are
redirected into `tmp_path` by autouse fixtures, so a run cannot clobber a scraped catalog.

Controlling the similarity field precisely is what makes decision 15 testable at all: a
unit vector `[s, sqrt(1 - s^2)]` scores exactly `s` against `[1, 0]`, so
`tests/backend/test_match_gating.py` can replay the three fixtures' measured confidences
(91.5/85.8, 88.1/83.0, 71.6/70.8) as inputs and assert the rule separates them.

**Why this shape.** The suite is arranged around the two places this system can lie to a
reviewer, because those are the failures that matter:

- **Claiming a match that is not one.** `test_match_gating.py` asserts the shipped rule
  rejects the unrelated fixture *and* still accepts the two real procedures, and pins the
  old floor-only rule as a test that would have matched all three.
- **Claiming a verdict the document does not support.** `test_evaluate.py` covers every
  downgrade in `_normalize_finding()`: a quote absent from the retrieved chunks, an
  invented chunk id, an empty evidence quote, a requirement the model skipped.

**Tradeoff on the frontend.** The component tests render real components against a stubbed
`fetch` rather than testing extracted helpers, because the assertion that matters is what
reaches the screen — specifically that a no-match renders **no confidence circles at all**.
That is asserted through the circles' `aria-label`, which makes the test double as an
accessibility check.

---

## Verified behavior

An end-to-end pass driven through a real Chromium session against the running app
(Playwright, headed, 1440x900), using a synthetic university privileged-access procedure
with one deliberately planted contradiction.

| Check | Result |
| --- | --- |
| Home, Policies, Settings render | Pass — 0 console errors, 0 uncaught page errors, 0 failed requests |
| `POST /api/check` (36 policies) | **HTTP 200 in 0.3–0.9s**, `text-embedding-ada-002` |
| Routing accuracy | Correct policy ranked #1 at **91.0%**; runner-up 85.4% |
| `POST /api/evaluate`, 16 requirements | **HTTP 200 in 74.9s**, `gpt-5.6-sol` at high effort, 2 concurrent batches |
| Grounding | **16/16** rows carried an evidence quote; **16/16** cited at least one source chunk id |
| Contradiction detection | **Caught the planted defect.** PAM-10 returned `contradicted`, quoting the inserted sentence permitting shared administrator accounts |
| Verdict spread | 7 aligned / 1 contradicted / 0 missing / 8 flagged — score 43.8% |
| Policies page | 36 cards; search "encryption" filters to 3 |
| Safeguards dialog | Opens, and closes on Escape |
| 390px viewport | `scrollWidth` 390 vs viewport 390 — no horizontal overflow |
| Gateway latency baseline | 1.4s for a single high-effort round trip |

### Committed fixtures

Three hand-authored documents live in `tests/documents/`, with an answer key for the one
carrying planted defects. All three target `privileged-account-management-policy`
(16 requirements).

| Fixture | Stage 1 top match | Score | Verdict spread |
| --- | --- | --- | --- |
| `01-compliant-…` | Correct policy, 91.5% | **100.0%** | 16 aligned |
| `02-noncompliant-…` | Correct policy, 87.4% | **12.5%** | 2 aligned, 14 contradicted |
| `03-unrelated-…` | Log Management Policy, 71.6% | n/a | n/a |

Fixture 02 carries ten deliberate violations and **matched its answer key exactly**:
`aligned` on PAM-01 and PAM-02 — the only two requirements it genuinely satisfies — and
`contradicted` on all fourteen others. No planted violation was passed. The predicted
score (2 of 16 = 12.5%) and the reported score agreed to the decimal.

**Fixture 03 exposed a real defect, now fixed.** It was written to demonstrate the
no-match path and instead demonstrated that the path never fired. The separation exists,
but not in the absolute score — it is in the gap between the top match and the runner-up:

| Rule | 01 compliant | 02 non-compliant | 03 unrelated | Separates? |
| --- | --- | --- | --- | --- |
| `top >= 50.0` (old) | match | match | **match** | no |
| `top - second >= 2.5` (**shipped**) | match (5.7) | match (5.1) | **no match (0.8)** | **yes** |
| `z-score of top >= 2.5` | match (3.63) | match (3.48) | match (2.67) | no |

The lead test shipped as [decision 15](#15-matching-is-a-two-part-test-both-configurable)
and fixture 03 is its regression test — it now returns `matched: false`. Raising the lead
to 6.0 through the Settings API correctly un-matches fixture 01 as well (lead 5.7), which
confirms the setting is live rather than cosmetic.

**One finding worth recording.** A 341-word test document produces exactly **one** chunk
at `WORDS_PER_CHUNK = 450`, so top-3 retrieval had nothing to choose between and every
requirement was judged against the same passage — several rows came back with identical
evidence quotes. This is not a bug, but it shows fixed-width chunking degrades ungracefully
on short documents, and it is the concrete argument for item 5 in the next steps.

---

## Known gaps

Honest inventory of what is not done.

- **No CI, and the linter does not pass.** `make test` runs 255 backend and 71 frontend
  tests offline ([decision 16](#16-tests-fake-the-provider-rather-than-skipping-without-a-key)),
  but nothing runs them automatically — there is no `.github/`. `npx eslint src` also
  reports five pre-existing `react-hooks/set-state-in-effect` errors in `app-shell`,
  `compliance-checker`, `policies-dashboard`, `reports-dashboard`, and `safeguards-dialog`,
  so lint is deliberately not part of `make test`; wiring it in means fixing those first.
- **The suite never calls a real provider.** Every LLM call is faked, so a Stanford Gateway
  contract change — a renamed field, a different embedding shape — would pass CI and fail
  in the browser. A keyed smoke test is the missing half.
- **Scraper and index builder are untested.** `backend/scraper/sans.py` (585 lines) and
  `backend/retrieve/index.py` (553 lines) are the two largest modules and have no
  coverage; both are Playwright- and filesystem-heavy, which is why they were left for a
  fixtured pass rather than done badly now.
- **Hardcoded models bypass Settings.** `EVAL_MODEL` / `EVAL_EFFORT`
  (`backend/retrieve/evaluate.py:23-24`) and `SAFEGUARD_MODEL`
  (`backend/retrieve/safeguards.py:16`) are pinned to `gpt-5.6-sol`, so the chat model the
  Settings UI exposes does not actually govern the two calls that matter most.
- **Frontend types are hand-mirrored.** `frontend/src/lib/types.ts` duplicates the Pydantic
  models in `backend/models.py` with no codegen, so they can drift silently. The component
  tests do not catch this — they build fixtures from those same types, so a wrong type
  produces green tests against a shape the backend never sends. Only codegen closes it.
- **All data fetching is client-side.** The three routes are server components that render
  a `"use client"` child which fetches in `useEffect` with `cache: "no-store"`. No
  server-side fetching, no caching strategy, no loading skeletons.

---

## What I would do next

Ordered by what unblocks the most.

1. **CI, and the two gaps the suite leaves.** The offline suite exists; running it
   automatically does not. A GitHub Actions workflow on `make test` is an afternoon. Then
   the two things it deliberately does not cover: one keyed smoke test against the live
   gateway, so a provider contract change fails a build rather than a demo, and golden-file
   tests for `sections.py` heading extraction against all 36 real PDFs. Fixing the five
   `set-state-in-effect` errors would let lint join the same gate.
2. **Real provider failover.** A health check plus try-the-next-configured-provider in
   `LLMRouter`, and wire `OllamaProvider` against Ollama's `/api/chat` and
   `/api/embeddings` so the app runs fully offline. This is what decision 2 was built for
   and is its most visible unfinished edge.
3. **Route the hardcoded models through `load_settings()`** so Settings governs every call,
   not just the test buttons.
4. **Persist check sessions** to SQLite or `data/sessions/` so evaluation survives a reload
   and a `check_id` can be shared or revisited.
5. **Sentence-boundary, heading-aware chunking** instead of fixed 450-word windows. The
   verified-behavior note above is the argument: short documents collapse to a single
   chunk and every requirement gets the same evidence.
6. **Evaluate a stronger embedding model** now that the threshold rule is relative — better
   separation would let the gap rule run with a wider margin.
7. **Export a findings report** (PDF or CSV) with requirement, verdict, evidence quote, and
   page citation. That artifact — not the web UI — is what a reviewer circulates.
8. **Concurrency in `ensure_index()`** via `asyncio.gather` with a semaphore, as
   `_judge_batches()` already does. Today indexing is a serial 36-policy loop.
9. **Generate `frontend/src/lib/types.ts` from the FastAPI OpenAPI schema** so the client
   types cannot drift from the Pydantic models.
