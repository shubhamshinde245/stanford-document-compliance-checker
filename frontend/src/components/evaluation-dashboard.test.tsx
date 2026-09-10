/**
 * The evaluation report.
 *
 * What matters here is that every verdict stays traceable: the counts add up to
 * the rows, the filters do not hide or invent findings, and a row shows the
 * quote it was decided from.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EvaluationDashboard } from "@/components/evaluation-dashboard";
import type {
  EvaluateFinding,
  EvaluateResponse,
  EvaluateVerdict,
} from "@/lib/types";

function finding(
  id: string,
  verdict: EvaluateVerdict,
  overrides: Partial<EvaluateFinding> = {},
): EvaluateFinding {
  return {
    requirement_id: id,
    definition: `Definition for ${id}.`,
    verdict,
    requirement_quote: `The standard says ${id}.`,
    evidence_quote: verdict === "missing" ? "" : `The procedure says ${id}.`,
    rationale: `Because of ${id}.`,
    sources:
      verdict === "missing"
        ? []
        : [{ chunk_id: `doc:p1:c${id}`, quote: `quote ${id}` }],
    ...overrides,
  };
}

const ROWS = [
  finding("R1", "aligned"),
  finding("R2", "aligned"),
  finding("R3", "contradicted"),
  finding("R4", "missing"),
  finding("R5", "flagged"),
];

function report(overrides: Partial<EvaluateResponse> = {}): EvaluateResponse {
  return {
    slug: "privileged-account-management-policy",
    title: "Privileged Account Management Policy",
    category: "Policy",
    source_url: "https://example.test/policy",
    pdf_url: "https://example.test/policy.pdf",
    model: "gpt-5.6-sol",
    reasoning_effort: "high",
    score: 40,
    counts: { aligned: 2, contradicted: 1, missing: 1, flagged: 1 },
    rows: ROWS,
    report_id: "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    ...overrides,
  };
}

function renderReport(overrides: Partial<EvaluateResponse> = {}) {
  return render(<EvaluationDashboard report={report(overrides)} />);
}

// ---------------------------------------------------------------------------
// Header and totals
// ---------------------------------------------------------------------------

describe("header", () => {
  it("names the policy that was evaluated", () => {
    renderReport();
    expect(
      screen.getByRole("heading", { name: /privileged account management policy/i }),
    ).toBeInTheDocument();
  });

  it("states the model and effort the verdicts came from", () => {
    renderReport();
    expect(screen.getByText(/gpt-5\.6-sol at high effort/i)).toBeInTheDocument();
  });

  it("states how many requirements were judged", () => {
    renderReport();
    expect(screen.getByText(/5 requirements/i)).toBeInTheDocument();
  });

  it("links to the source pdf", () => {
    renderReport();
    expect(screen.getByRole("link", { name: /open pdf/i })).toHaveAttribute(
      "href",
      "https://example.test/policy.pdf",
    );
  });

  it("falls back to the local pdf route when the policy has no url", () => {
    renderReport({ pdf_url: "" });
    expect(screen.getByRole("link", { name: /open pdf/i })).toHaveAttribute(
      "href",
      "/api/policies/privileged-account-management-policy/pdf",
    );
  });
});

describe("totals", () => {
  it("shows the alignment score to one decimal", () => {
    renderReport({ score: 40 });
    expect(screen.getByText("40.0")).toBeInTheDocument();
  });

  it("shows a count for each verdict", () => {
    renderReport();
    for (const label of ["Aligned", "Contradicted", "Missing", "Flagged"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("renders every row by default", () => {
    renderReport();
    expect(screen.getAllByRole("listitem")).toHaveLength(ROWS.length);
  });
});

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

describe("filters", () => {
  it("counts each verdict on its filter button", () => {
    renderReport();
    expect(screen.getByRole("button", { name: "All 5" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aligned 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Missing 1" })).toBeInTheDocument();
  });

  it("narrows the list to one verdict", async () => {
    const user = userEvent.setup();
    renderReport();
    await user.click(screen.getByRole("button", { name: "Aligned 2" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("restores every row when All is chosen again", async () => {
    const user = userEvent.setup();
    renderReport();
    await user.click(screen.getByRole("button", { name: "Contradicted 1" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "All 5" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(ROWS.length);
  });

  it("shows nothing for a verdict with no findings", async () => {
    const user = userEvent.setup();
    render(
      <EvaluationDashboard
        report={report({
          rows: [finding("R1", "aligned")],
          counts: { aligned: 1, contradicted: 0, missing: 0, flagged: 0 },
        })}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Flagged 0" }));
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Findings
// ---------------------------------------------------------------------------

describe("a finding", () => {
  it("shows the requirement id and its verdict", () => {
    renderReport();
    const [row] = screen.getAllByRole("listitem");
    expect(within(row).getAllByText(/R1/).length).toBeGreaterThan(0);
    expect(within(row).getByText(/^aligned$/i)).toBeInTheDocument();
  });

  it("shows both quotes so the verdict can be traced", () => {
    renderReport();
    expect(screen.getByText(/the standard says R1\./i)).toBeInTheDocument();
    expect(screen.getByText(/the procedure says R1\./i)).toBeInTheDocument();
  });

  it("shows the rationale", () => {
    renderReport();
    expect(screen.getByText(/because of R1\./i)).toBeInTheDocument();
  });

  it("renders a missing row without inventing evidence", async () => {
    const user = userEvent.setup();
    renderReport();
    await user.click(screen.getByRole("button", { name: "Missing 1" }));
    const [row] = screen.getAllByRole("listitem");
    expect(within(row).queryByText(/the procedure says R4\./i)).toBeNull();
  });

  it("handles an empty report without crashing", () => {
    render(
      <EvaluationDashboard
        report={report({
          rows: [],
          score: 0,
          counts: { aligned: 0, contradicted: 0, missing: 0, flagged: 0 },
        })}
      />,
    );
    expect(screen.getByRole("button", { name: "All 0" })).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});
