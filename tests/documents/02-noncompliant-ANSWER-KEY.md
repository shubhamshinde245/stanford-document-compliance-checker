# Answer key — `02-noncompliant-privileged-account-procedure.md`

Target standard: **Privileged Account Management Policy**
(`data/sans-policies/safeguards/privileged-account-management-policy.csv`, 16 requirements)

Nine violations were planted deliberately. Each row gives the requirement it breaks, the
sentence that breaks it, and the verdict a correct system should return.

`contradicted` is expected where the document makes an affirmative statement that
conflicts with the requirement. `missing` is expected where the document simply never
addresses it. A `flagged` verdict instead of `contradicted` is an acceptable near-miss —
the evidence was found but the system declined to commit — and is not scored as a failure
below. An `aligned` verdict on any row here **is** a failure.

| # | Requirement | Planted violation (quote from the document) | Expected |
| --- | --- | --- | --- |
| 1 | **PAM-03** — inventory privileged accounts on network devices | "Network devices are excluded from the privileged account inventory." | `contradicted` |
| 2 | **PAM-04** — inventory privileged accounts on enterprise business applications | "Enterprise business applications are likewise out of scope for the inventory." | `contradicted` |
| 3 | **PAM-05 / PAM-06** — dedicated privileged accounts required on endpoints and servers | "Administrators use their normal day-to-day user account for administrative work." | `contradicted` |
| 4 | **PAM-09** — no default credentials in use | "Default vendor administrator credentials are retained on network appliances after installation." | `contradicted` |
| 5 | **PAM-10** — no shared privileged accounts except emergency or via a PAM system | "A shared `netadmin` account is used by the whole Networking Team… The password is circulated to team members by email." Explicitly *not* emergency use and *not* brokered through a PAM tool. | `contradicted` |
| 6 | **PAM-11** — maintain a PAM or password manager for shared secrets | "The campus does not operate a Privileged Account Management system or a password manager." Secrets live in a file-share spreadsheet. | `contradicted` |
| 7 | **PAM-12 / PAM-13** — PAM system auto-rotates unique credentials per host and per network device | "There is no automated rotation for endpoints, for servers, or for network devices, and the same administrative password is reused across all switches of the same model." Breaks both automation and uniqueness. | `contradicted` |
| 8 | **PAM-14** — IDPs require MFA for all privileged accounts | "Multi-factor authentication is not required for privileged accounts on internal systems; a password alone is sufficient." | `contradicted` |
| 9 | **PAM-15** — IDPs log and alert on privileged group membership changes | "Changes to privileged group membership — for example adding an account to Domain Admins — are not logged or alerted." | `contradicted` |
| 10 | **PAM-16** — IDPs log and alert logon events, successful **and** failed | "Failed logon attempts for administrator accounts are not recorded, in order to reduce log volume." Successful logons *are* logged, so this is a partial breach. | `contradicted` |

## Requirements the document does satisfy

Included so the fixture is not uniformly negative and can distinguish a working system
from one that simply returns `contradicted` for everything.

| Requirement | Supporting text | Expected |
| --- | --- | --- |
| **PAM-01** — inventory privileged accounts on endpoints | "IT Operations maintains a spreadsheet inventory of privileged accounts on endpoint computing systems…" | `aligned` |
| **PAM-02** — inventory privileged accounts on servers | "…and on server computing systems." | `aligned` |

## Requirements never addressed

| Requirement | Expected |
| --- | --- |
| **PAM-07** — network device privileged accounts authorized and dedicated | `missing` or `contradicted` |
| **PAM-08** — business application privileged accounts authorized and dedicated | `missing` or `contradicted` |

## Scoring this fixture

A correct run should produce:

- **`aligned` on PAM-01 and PAM-02 only.** Any other `aligned` is a false pass and the
  most serious failure mode — it tells a reviewer a control is in place when the document
  says the opposite.
- **`contradicted` or `flagged` on all ten planted rows.** Treat `contradicted` as a full
  pass and `flagged` as a partial pass.
- **A low alignment score.** Two aligned rows out of sixteen is 12.5%. Because
  `_normalize_finding()` downgrades unverifiable quotes to `flagged`, the reported score
  may sit below that; it should not sit meaningfully above it.

Every planted violation is stated in plain, quotable prose so that a correct
`evidence_quote` exists verbatim in the document. A row that comes back `flagged` with the
rationale that no supporting passage was found points at retrieval, not at the fixture.

---

## Verified result

Run against `gpt-5.6-sol` at high effort, `text-embedding-ada-002`, 16 requirements in
one evaluation (44s).

**Reported score: 12.5% — exactly the value predicted above.**

| Verdict | Count | Requirements |
| --- | --- | --- |
| `aligned` | 2 | PAM-01, PAM-02 |
| `contradicted` | 14 | PAM-03 … PAM-16 |
| `missing` | 0 | — |
| `flagged` | 0 | — |

Every one of the ten planted violations was returned as `contradicted`. There were no
false passes: no requirement the document breaks came back `aligned`. PAM-07 and PAM-08,
listed above as "never addressed", were also returned `contradicted` rather than
`missing` — a defensible reading, since the document's blanket statement that
administrators use their day-to-day accounts conflicts with the dedicated-account
requirement for those system classes too.

Use this table as the regression baseline. LLM output is not bit-stable, so treat a
changed *verdict* as the signal, not a changed rationale or quote.
