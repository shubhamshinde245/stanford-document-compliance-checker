/**
 * The saved-reports list.
 *
 * Deleting is destructive and irreversible, so the confirm prompt and the
 * "only remove what the server actually deleted" behaviour are the parts worth
 * pinning down.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportsDashboard } from "@/components/reports-dashboard";
import type { SavedReportSummary } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function summary(overrides: Partial<SavedReportSummary> = {}): SavedReportSummary {
  return {
    id: "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    created_at: "2026-09-01T12:00:00+00:00",
    filename: "procedure.md",
    check_id: "check-1",
    slug: "privileged-account-management-policy",
    title: "Privileged Account Management Policy",
    category: "Policy",
    score: 62.5,
    counts: { aligned: 5, contradicted: 2, missing: 1, flagged: 0 },
    ...overrides,
  };
}

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  const spy = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(handler(String(url), init)),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function listResponse(reports: SavedReportSummary[]) {
  return new Response(JSON.stringify({ reports }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

async function renderList(reports: SavedReportSummary[]) {
  mockFetch(() => listResponse(reports));
  render(<ReportsDashboard />);
  await waitFor(() =>
    expect(screen.queryByText(/loading saved reports/i)).toBeNull(),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Loading and empty states
// ---------------------------------------------------------------------------

describe("states", () => {
  it("shows a loading line first", () => {
    mockFetch(() => listResponse([]));
    render(<ReportsDashboard />);
    expect(screen.getByText(/loading saved reports/i)).toBeInTheDocument();
  });

  it("explains where reports come from when there are none", async () => {
    await renderList([]);
    expect(screen.getByText(/no saved evaluations yet/i)).toBeInTheDocument();
    expect(screen.getByText(/data\/reports/i)).toBeInTheDocument();
  });

  it("shows the backend message when loading fails", async () => {
    mockFetch(
      () =>
        new Response(JSON.stringify({ detail: "Could not read the reports directory." }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
    );
    render(<ReportsDashboard />);
    expect(
      await screen.findByText(/could not read the reports directory/i),
    ).toBeInTheDocument();
  });

  it("falls back to its own wording when the failure is not json", async () => {
    mockFetch(() => new Response("<html>502 Bad Gateway</html>", { status: 502 }));
    render(<ReportsDashboard />);
    expect(
      await screen.findByText(/could not load saved reports/i),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// The list
// ---------------------------------------------------------------------------

describe("the list", () => {
  it("shows one entry per saved report", async () => {
    await renderList([
      summary({ id: "a", title: "First Policy" }),
      summary({ id: "b", title: "Second Policy" }),
    ]);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows the score to one decimal", async () => {
    await renderList([summary({ score: 62.5 })]);
    expect(screen.getByText("62.5")).toBeInTheDocument();
  });

  it("shows the verdict tally", async () => {
    await renderList([summary()]);
    expect(screen.getByText(/5 aligned/)).toBeInTheDocument();
    expect(screen.getByText(/2 contradicted/)).toBeInTheDocument();
  });

  it("shows the uploaded filename", async () => {
    await renderList([summary({ filename: "quarterly-review.md" })]);
    expect(screen.getByText(/quarterly-review\.md/)).toBeInTheDocument();
  });

  it("links each report to its detail page", async () => {
    await renderList([summary({ id: "abc-123" })]);
    expect(screen.getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/reports/abc-123",
    );
  });

  it("falls back to the raw timestamp when it cannot be parsed", async () => {
    await renderList([summary({ created_at: "not-a-date" })]);
    expect(screen.getByText("not-a-date")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Deleting
// ---------------------------------------------------------------------------

describe("deleting", () => {
  it("asks before deleting", async () => {
    const user = userEvent.setup();
    const confirm = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirm);
    const spy = mockFetch(() => listResponse([summary()]));
    render(<ReportsDashboard />);
    await waitFor(() => screen.getByRole("button", { name: /delete/i }));

    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining("Privileged Account Management Policy"),
    );
    expect(
      spy.mock.calls.some(([, init]) => (init as RequestInit)?.method === "DELETE"),
    ).toBe(false);
  });

  it("keeps the report when the prompt is dismissed", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(false));
    mockFetch(() => listResponse([summary()]));
    render(<ReportsDashboard />);
    await waitFor(() => screen.getByRole("button", { name: /delete/i }));

    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("removes the row once the server confirms", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    mockFetch((url, init) =>
      init?.method === "DELETE"
        ? new Response(JSON.stringify({ status: "deleted" }), { status: 200 })
        : listResponse([summary({ id: "a", title: "First" }), summary({ id: "b", title: "Second" })]),
    );
    render(<ReportsDashboard />);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));

    await user.click(screen.getAllByRole("button", { name: /delete/i })[0]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(1));
    expect(screen.getByRole("heading", { name: "Second" })).toBeInTheDocument();
  });

  it("keeps the row when the delete fails", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    mockFetch((url, init) =>
      init?.method === "DELETE"
        ? new Response(JSON.stringify({ detail: "Report not found." }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          })
        : listResponse([summary()]),
    );
    render(<ReportsDashboard />);
    await waitFor(() => screen.getByRole("button", { name: /delete/i }));

    await user.click(screen.getByRole("button", { name: /delete/i }));
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(1));
  });

  it("sends the delete to the report's own id", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    const spy = mockFetch((url, init) =>
      init?.method === "DELETE"
        ? new Response(null, { status: 200 })
        : listResponse([summary({ id: "abc-123" })]),
    );
    render(<ReportsDashboard />);
    await waitFor(() => screen.getByRole("button", { name: /delete/i }));

    await user.click(screen.getByRole("button", { name: /delete/i }));
    await waitFor(() =>
      expect(
        spy.mock.calls.some(([url]) => String(url) === "/api/reports/abc-123"),
      ).toBe(true),
    );
  });
});
