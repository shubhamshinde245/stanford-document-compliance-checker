# Test documents

Three hand-authored fixtures for exercising the checker end to end, plus an answer key
for the one with planted defects. Upload them at <http://localhost:3000>, or post them
straight at the API.

| File | Purpose |
| --- | --- |
| `01-compliant-privileged-account-procedure.md` | A procedure that satisfies the Privileged Account Management Policy |
| `02-noncompliant-privileged-account-procedure.md` | The same subject with ten deliberate violations |
| `02-noncompliant-ANSWER-KEY.md` | What is wrong with the above, and the verdict each row should get |
| `03-unrelated-document.md` | A campus tree-care calendar — nothing to do with security |

All three target the same standard so results are comparable:
`privileged-account-management-policy` (16 requirements).

## Running them

```bash
# stage 1 — which standard is this?
curl -s -X POST http://127.0.0.1:8000/api/check \
  -F "file=@tests/documents/01-compliant-privileged-account-procedure.md" | python3 -m json.tool

# stage 2 — how well does it comply?
curl -s -X POST http://127.0.0.1:8000/api/evaluate \
  -F "file=@tests/documents/02-noncompliant-privileged-account-procedure.md" \
  -F "slug=privileged-account-management-policy" | python3 -m json.tool
```

## Observed results

Recorded against `gpt-5.6-sol` at high effort with `text-embedding-ada-002`. Treat these
as the regression baseline; LLM output is not bit-stable, so small movements are normal
and a changed *verdict* is the signal worth investigating.

### Stage 1 — routing

| Document | Top match | Confidence | Runner-up gap |
| --- | --- | --- | --- |
| 01 compliant | Privileged Account Management Policy | 91.5% | 5.7 |
| 02 non-compliant | Privileged Account Management Policy | 87.4% | 5.1 |
| 03 unrelated | Log Management Policy | 71.6% | 0.8 |

Both procedures route to the correct standard. See the caveat on document 03 below.

### Stage 2 — verdicts

| Document | Score | aligned | contradicted | missing | flagged |
| --- | --- | --- | --- | --- | --- |
| 01 compliant | **100.0%** | 16 | 0 | 0 | 0 |
| 02 non-compliant | **12.5%** | 2 | 14 | 0 | 0 |

Document 02 matched its answer key exactly: `aligned` on PAM-01 and PAM-02 only — the two
requirements it genuinely satisfies — and `contradicted` on all fourteen others. No
planted violation was passed.

Document 01 scoring 100% is by construction: it was written to state every one of the
sixteen requirements affirmatively and in quotable prose. It is a control, not evidence
that a real-world procedure would score that highly.

## Document 03 and the match rule

This fixture was written to demonstrate the no-match path. On first run it demonstrated
the opposite: a tree-care calendar with no security content scored 71.6% and reported
`matched: true`, because the rule was a bare `top >= 50.0` and nothing
`text-embedding-ada-002` produces comes near 50.

Measured spread across all 36 policies:

| Document | Highest | Lowest | Mean | Std dev |
| --- | --- | --- | --- | --- |
| 01 compliant | 91.5% | 74.6% | 79.3% | 3.37 |
| 02 non-compliant | 87.4% | 73.0% | 77.3% | 2.89 |
| 03 unrelated | 71.6% | 65.9% | 68.9% | 1.00 |

The bands overlap, so no absolute cutoff separates them — but the shape does. A real match
stands clear of the field; noise does not:

| Rule | 01 | 02 | 03 | Separates? |
| --- | --- | --- | --- | --- |
| `top >= 50.0` (old) | match | match | **match** | no |
| `top - second >= 2.5` (**shipped**) | match (5.7) | match (5.1) | **no match (0.8)** | **yes** |
| z-score of top `>= 2.5` | match (3.63) | match (3.48) | match (2.67) | no |

Matching now requires **both** a floor on the top score and a lead over the runner-up.
Fixture 03 returns `matched: false`. Both numbers are editable under **Settings → Match
rule** and are returned on every `/api/check` response as `match_threshold`,
`match_min_gap`, and the measured `match_gap`.

Keep fixture 03 as the negative case. If a change makes it match again, the gate has
regressed.
