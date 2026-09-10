export type Audience = "stakeholder" | "technical";

export type FlowStep = {
  label: string;
};

export type ExampleRow = {
  document: string;
  top: string;
  runnerUp: string;
  lead: string;
  gate: "match" | "no-match";
  then: string;
};

export type HowItWorksSection = {
  id: string;
  title: string;
  paragraphs: string[];
  bullets?: string[];
  formula?: string;
};

export type HowItWorksCopy = {
  kicker: string;
  title: string;
  intro: string;
  flowLabel: string;
  flowSteps: FlowStep[];
  sections: HowItWorksSection[];
  exampleTitle: string;
  exampleCaption: string;
  exampleRows: ExampleRow[];
  exampleNote: string;
};

export const AUDIENCE_LABEL: Record<Audience, string> = {
  stakeholder: "For stakeholders",
  technical: "For engineers",
};

export const FLOW_STEPS: FlowStep[] = [
  { label: "Extract" },
  { label: "Chunk" },
  { label: "Embed upload" },
  { label: "Cosine vs parked" },
  { label: "Gate" },
];

export const EXAMPLE_ROWS: ExampleRow[] = [
  {
    document: "Privileged-access procedure (compliant)",
    top: "91.5",
    runnerUp: "85.8",
    lead: "5.7",
    gate: "match",
    then: "16/16 aligned → 100% alignment",
  },
  {
    document: "Same topic, planted violations",
    top: "88.1",
    runnerUp: "83.0",
    lead: "5.1",
    gate: "match",
    then: "2/16 aligned → 12.5% alignment",
  },
  {
    document: "Tree-care calendar (unrelated)",
    top: "71.6",
    runnerUp: "70.8",
    lead: "0.8",
    gate: "no-match",
    then: "Evaluate stays off; no percentage shown",
  },
];

const STAKEHOLDER: HowItWorksCopy = {
  kicker: "How it works",
  title: "From upload to a chosen standard",
  intro:
    "Click Run compliance check and the app asks one question first: which security standard does this procedure belong to? It only names a standard when one policy is clearly ahead of the others. A second, separate score appears later if you evaluate that policy’s requirements.",
  flowLabel: "What the check does",
  flowSteps: FLOW_STEPS,
  sections: [
    {
      id: "questions",
      title: "Two questions, two percentages",
      paragraphs: [
        "Match similarity is how close the document is, in meaning, to a policy’s stated purpose and who it applies to. Alignment is how many of that policy’s requirements the procedure actually satisfies.",
        "Those numbers are not interchangeable. A procedure can clearly belong to Privileged Account Management and still fail most of its rules.",
      ],
    },
    {
      id: "after-click",
      title: "After you click Run compliance check",
      paragraphs: [
        "The file never leaves this app except for the model calls that turn text into numbers and, later, judge requirements. The library of 36 SANS policies is already prepared on disk, so a check does not re-read those PDFs.",
      ],
      bullets: [
        "Pull the text out of the PDF, Word file, or markdown you uploaded.",
        "Split it into overlapping windows so a long procedure can be compared piece by piece.",
        "Turn those windows into numbers that capture meaning, not keywords.",
        "Compare them to one prepared summary per policy — the policy’s title, purpose, and scope.",
        "Call it a match only when the nearest policy is both strong enough and clearly ahead of second place.",
      ],
    },
    {
      id: "matching",
      title: "How the closest standard is chosen",
      paragraphs: [
        "Think of each policy as a point on a map of meaning, parked there from its Purpose and Scope. Your document is several nearby points, one per window of text. The policy that any window sits closest to is that policy’s score.",
        "Closeness is shown as a percentage. It is not a probability and it is not a grade. An unrelated document can still look “pretty close” to everything in the library — around 71% — because the map is crowded. What separates a real match is the gap: a true neighbor stands several points clear of the runner-up. A tree-care calendar does not.",
      ],
    },
    {
      id: "storage",
      title: "Where the library lives",
      paragraphs: [
        "The policy summaries are prepared ahead of time, on this machine, when someone runs the index step. A check only reads that prepared library. Your uploaded document’s numbers stay in memory for a short time so Evaluate can reuse them; they are not written to disk.",
        "If the library has not been prepared, the check refuses to guess rather than quietly building a different one.",
      ],
    },
    {
      id: "evaluate",
      title: "What Evaluate does next",
      paragraphs: [
        "Only after a match. The app reads the chosen policy’s extracted requirements, finds the three closest passages in your procedure for each one, and asks a model to judge aligned, contradicted, missing, or flagged.",
        "A pass is not trusted on the model’s say-so. The quoted sentence has to actually appear in those passages. If it does not, the row is flagged for a person. The alignment percentage is the share of requirements judged aligned — flagged and missing rows pull that number down on purpose.",
      ],
    },
  ],
  exampleTitle: "Worked example",
  exampleCaption:
    "Three test documents, all aimed at Privileged Account Management. The first two are real procedures. The third is a tree-care calendar.",
  exampleRows: EXAMPLE_ROWS,
  exampleNote:
    "71% can still be a miss if two policies are almost tied. A real match stands clear of the field; noise does not.",
};

const TECHNICAL: HowItWorksCopy = {
  kicker: "How it works",
  title: "From POST /api/check to cosine ranking",
  intro:
    "Run compliance check calls checkDocument() → POST /api/check. Next rewrites to FastAPI check_upload(). The request path embeds the upload only. The 36 policy vectors are parked on disk and never rebuilt here.",
  flowLabel: "check_upload pipeline",
  flowSteps: FLOW_STEPS,
  sections: [
    {
      id: "questions",
      title: "Two questions, two percentages",
      paragraphs: [
        "Match similarity is round(cosine × 100, 1) from rank_policies(), shown on Findings only if matched is true. Alignment score is round(100 × aligned / total, 1) from evaluate_upload() after the judge + quote-verify step.",
        "Do not mix them. Fixture 02 matches at ~88% cosine and then scores 12.5% alignment (2 of 16 requirements).",
      ],
    },
    {
      id: "after-click",
      title: "After you click Run compliance check",
      paragraphs: [
        "inspect_index() returns HTTP 503 unless format is summary-v1 and the parked embedding model matches Settings. extract_document() then chunk_pages() (450 words, 80 overlap, ids {slug}:p{page}:c{index}). llm.embed_many() embeds those chunk texts only.",
      ],
      bullets: [
        "Load index.json rows where chunk_kind == \"summary\" and the aligned rows of the embeddings matrix.",
        "L2-normalize Q (n_chunks × 1536) and P (36 × 1536) with a 1e-12 floor.",
        "S = Q @ P.T; best = S.max(axis=0); confidence = round(best × 100, 1).",
        "matched = top >= match_min_confidence AND gap >= match_min_gap (defaults 50 and 2.5).",
        "store_check() keeps chunks + embeddings in an OrderedDict capped at 8 check_ids. They are not written to disk.",
      ],
    },
    {
      id: "matching",
      title: "How vector matching works",
      paragraphs: [
        "No vector database. One NumPy matmul in rank_policies(). Each policy is a single parked vector over Title / Category / Purpose / Scope from build_summary_text(), not body windows — shared “Exceptions” / “Enforcement” boilerplate would otherwise collapse the field.",
        "ada-002 compresses scores into a narrow band. The old MATCH_THRESHOLD = 50 sat below everything the model produces, so a tree-care calendar at 71.6% reported matched: true. The lead over the runner-up is model-relative and is what makes the no-match branch reachable.",
      ],
      formula:
        "query = Q / ||Q||\nparked = P / ||P||\nS = query @ parked.T\nbest = S.max(axis=0)\nconfidence = round(best * 100, 1)",
    },
    {
      id: "storage",
      title: "Where embeddings live on disk",
      paragraphs: [
        "Policy vectors: data/sans-policies/index.json (metadata, format summary-v1, embedding_model, dimensions 1536) plus index.npz, an np.savez archive with key embeddings, float32, shape (n_rows, 1536). Row i in JSON is row i in the matrix. Written atomically (index.json.tmp / index.tmp.npz then replace) under INDEX_LOCK. Both files are gitignored.",
        "Document vectors stay in RAM (backend/retrieve/session.py). /api/evaluate re-runs the check on a session miss. Sibling files — pdfs/, safeguards/{slug}.csv, catalog.json, llm-settings.json, reports/{uuid}.json — are not embeddings.",
      ],
    },
    {
      id: "evaluate",
      title: "What Evaluate does next",
      paragraphs: [
        "Requires matched. Reuse the RAM session. Embed each safeguard definition, cosine against the same document vectors, top-3 chunks. Judge in batches of 6 with 2 concurrent calls (gpt-5.6-sol, high effort).",
        "_normalize_finding() downgrades aligned/contradicted to flagged if evidence_quote is not literally in a retrieved chunk (whitespace-collapsed containment) or if the cited chunk_id was not in that requirement’s top 3. Alignment = 100 × aligned / total.",
      ],
    },
  ],
  exampleTitle: "Worked example",
  exampleCaption:
    "Committed fixtures in tests/documents/, gated by tests/backend/test_match_gating.py. All three target privileged-account-management-policy (16 requirements).",
  exampleRows: EXAMPLE_ROWS,
  exampleNote:
    "The floor-only rule (top >= 50) called all three a match. Lead 2.5 is what separates them. Raising the lead to 6.0 through Settings also un-matches fixture 01 (lead 5.7), which is how you know the knob is live.",
};

export const HOW_IT_WORKS: Record<Audience, HowItWorksCopy> = {
  stakeholder: STAKEHOLDER,
  technical: TECHNICAL,
};

export const AUDIENCE_STORAGE_KEY = "stanford-how-it-works-audience";

export function parseAudience(value: string | null): Audience {
  return value === "technical" ? "technical" : "stakeholder";
}
