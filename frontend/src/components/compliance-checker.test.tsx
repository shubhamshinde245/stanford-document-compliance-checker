/**
 * The checker screen.
 *
 * The rule these tests defend: a confidence number is only shown when one
 * policy is clearly ahead of the field. On a no-match the list is names only,
 * because a percentage printed next to a policy title reads as a chosen
 * standard even when the header says otherwise.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CheckSessionProvider } from "@/components/check-session";
import { ComplianceChecker } from "@/components/compliance-checker";
import type { CheckResponse, PolicyMatch } from "@/lib/types";

function match(slug: string, confidence: number): PolicyMatch {
  return {
    slug,
    title: slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    category: "Policy",
    confidence,
    score: confidence / 100,
    snippet: `${slug} snippet`,
    chunk_id: `${slug}:summary`,
    source_url: `https://example.test/${slug}`,
    pdf_url: `https://example.test/${slug}.pdf`,
    pdf_path: null,
    pdf_bytes: null,
    published_on: null,
    summary: `${slug} summary`,
  };
}

function checkResponse(overrides: Partial<CheckResponse> = {}): CheckResponse {
  return {
    filename: "procedure.md",
    model: "text-embedding-ada-002",
    check_id: "check-1",
    matched: true,
    match_threshold: 50,
    match_min_gap: 2.5,
    match_gap: 5.7,
    matches: [match("privileged-account-management-policy", 91.5), match("access-management-policy", 85.8)],
    ...overrides,
  };
}

/** The unrelated fixture: high scores, no lead. */
const NO_MATCH = checkResponse({
  matched: false,
  match_gap: 0.8,
  matches: [match("log-management-policy", 71.6), match("email-management-policy", 70.8)],
});

function mockCheck(response: CheckResponse) {
  const spy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderChecker() {
  return render(
    <CheckSessionProvider>
      <ComplianceChecker />
    </CheckSessionProvider>,
  );
}

async function runCheck(response: CheckResponse) {
  const user = userEvent.setup();
  mockCheck(response);
  renderChecker();
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  await user.upload(
    input,
    new File(["procedure text"], "procedure.md", { type: "text/markdown" }),
  );
  await user.click(screen.getByRole("button", { name: /run compliance check/i }));
  await waitFor(() =>
    expect(screen.queryByText(/upload a procedure, then run a check/i)).toBeNull(),
  );
  return user;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Before a check
// ---------------------------------------------------------------------------

describe("initial state", () => {
  it("explains that a score appears only when one policy is clearly ahead", () => {
    renderChecker();
    expect(
      screen.getByText(/only when one policy is clearly ahead/i),
    ).toBeInTheDocument();
  });

  it("cannot run a check before a file is chosen", () => {
    renderChecker();
    expect(
      screen.getByRole("button", { name: /run compliance check/i }),
    ).toBeDisabled();
  });

  it("rejects an unsupported file type without calling the api", async () => {
    const user = userEvent.setup();
    const spy = mockCheck(checkResponse());
    renderChecker();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(input, new File(["x"], "notes.exe", { type: "application/x-msdownload" }));
    expect(
      screen.getByRole("button", { name: /run compliance check/i }),
    ).toBeDisabled();
    expect(spy).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// A match
// ---------------------------------------------------------------------------

describe("when one policy is clearly ahead", () => {
  it("shows the top confidence", async () => {
    await runCheck(checkResponse());
    // Rendered twice by design: once in the score well, once on the list row.
    expect(screen.getAllByText("91.5").length).toBeGreaterThan(0);
    expect(screen.getByText(/match similarity/i)).toBeInTheDocument();
  });

  it("says the number is similarity, not a probability", async () => {
    await runCheck(checkResponse());
    expect(screen.getAllByText(/not a probability/i).length).toBeGreaterThan(0);
  });

  it("labels each confidence circle for screen readers", async () => {
    await runCheck(checkResponse());
    expect(
      screen.getAllByLabelText(/percent confidence/i).length,
    ).toBeGreaterThan(0);
  });

  it("names the matched policy", async () => {
    await runCheck(checkResponse());
    expect(
      screen.getAllByText(/privileged account management policy/i).length,
    ).toBeGreaterThan(0);
  });

  it("enables evaluation", async () => {
    await runCheck(checkResponse());
    expect(
      screen.getByRole("button", { name: /evaluate/i }),
    ).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// No match -- the decision 15 behaviour
// ---------------------------------------------------------------------------

describe("when nothing is clearly ahead", () => {
  it("states that no standard matches", async () => {
    await runCheck(NO_MATCH);
    expect(
      screen.getByText(/no standard in the library matches this document/i),
    ).toBeInTheDocument();
  });

  it("shows no percentage anywhere on the page", async () => {
    await runCheck(NO_MATCH);
    // 71.6 and 70.8 are the real confidences; neither may be rendered.
    expect(screen.queryByText("71.6")).toBeNull();
    expect(screen.queryByText("70.8")).toBeNull();
    expect(screen.queryByText(/7[01]\.\d/)).toBeNull();
  });

  it("renders no confidence circles at all", async () => {
    await runCheck(NO_MATCH);
    expect(screen.queryAllByLabelText(/percent confidence/i)).toHaveLength(0);
  });

  it("still names the nearest policy for reference", async () => {
    await runCheck(NO_MATCH);
    expect(
      screen.getAllByText(/log management policy/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/nearest in the library/i)).toBeInTheDocument();
  });

  it("explains that a score is not a match", async () => {
    await runCheck(NO_MATCH);
    expect(screen.getByText(/a score is not a match/i)).toBeInTheDocument();
  });

  it("says the two leaders were too close to call", async () => {
    await runCheck(NO_MATCH);
    expect(screen.getByText(/too close to call/i)).toBeInTheDocument();
  });

  it("labels the list as names only", async () => {
    await runCheck(NO_MATCH);
    expect(screen.getByText(/names only/i)).toBeInTheDocument();
  });

  it("disables evaluation so a standard cannot be forced", async () => {
    await runCheck(NO_MATCH);
    const evaluate = screen.queryByRole("button", { name: /evaluate/i });
    if (evaluate) {
      expect(evaluate).toBeDisabled();
    }
  });

  it("does not call the evaluate endpoint", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(NO_MATCH), { status: 200 }),
    );
    vi.stubGlobal("fetch", spy);
    await runCheck(NO_MATCH);
    const called = spy.mock.calls.map(([url]) => String(url));
    expect(called.some((url) => url.includes("/api/evaluate"))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Which of the two tests failed
// ---------------------------------------------------------------------------

describe("the reason given for a no-match", () => {
  it("reports a uniformly weak field when the floor failed", async () => {
    await runCheck(
      checkResponse({
        matched: false,
        match_gap: 20,
        matches: [match("a-policy", 30), match("b-policy", 10)],
      }),
    );
    expect(
      screen.getByText(/nothing is similar enough/i),
    ).toBeInTheDocument();
  });

  it("reports a tie when the lead failed", async () => {
    await runCheck(NO_MATCH);
    expect(screen.getByText(/too close to call/i)).toBeInTheDocument();
    expect(screen.queryByText(/nothing is similar enough/i)).toBeNull();
  });

  it("handles a single candidate with no runner-up to compare against", async () => {
    await runCheck(
      checkResponse({
        matched: false,
        match_gap: 20,
        matches: [match("only-policy", 20)],
      }),
    );
    expect(screen.getByText(/nothing is similar enough/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------

describe("when the check fails", () => {
  it("shows the backend message", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Policy index is not built. Run `make index`." }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderChecker();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(
      input,
      new File(["x"], "procedure.md", { type: "text/markdown" }),
    );
    await user.click(screen.getByRole("button", { name: /run compliance check/i }));
    expect(
      await screen.findByText(/policy index is not built/i),
    ).toBeInTheDocument();
  });
});
