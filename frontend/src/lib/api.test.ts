/**
 * API client.
 *
 * Most of what is worth testing here is `readDetail`: the backend sends a JSON
 * `detail` string, but a Next rewrite timeout or a proxy error sends HTML or
 * nothing. The toast the reviewer reads comes straight out of this function, so
 * a 504 must not surface as a wall of HTML.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  checkDocument,
  deleteSavedReport,
  evaluateDocument,
  fetchPolicySafeguards,
  fetchReport,
  fetchReports,
  policyPdfUrl,
  saveLlmSettings,
} from "./api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function textResponse(body: string, status: number) {
  return new Response(body, { status });
}

function mockFetch(response: Response) {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

const FILE = new File(["procedure text"], "procedure.md", {
  type: "text/markdown",
});

beforeEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Error detail
// ---------------------------------------------------------------------------

describe("error messages", () => {
  it("surfaces the backend detail string", async () => {
    mockFetch(jsonResponse({ detail: "No standard matches this document." }, 409));
    await expect(checkDocument(FILE)).rejects.toThrow(
      "No standard matches this document.",
    );
  });

  it("falls back for a 5xx so a stack trace never reaches the toast", async () => {
    mockFetch(textResponse("<html>500 Internal Server Error</html>", 500));
    await expect(checkDocument(FILE)).rejects.toThrow("Compliance check failed.");
  });

  it("passes through a non-JSON 4xx body", async () => {
    mockFetch(textResponse("Request Entity Too Large", 413));
    await expect(checkDocument(FILE)).rejects.toThrow("Request Entity Too Large");
  });

  it("falls back when the body is empty", async () => {
    mockFetch(textResponse("", 400));
    await expect(checkDocument(FILE)).rejects.toThrow("Compliance check failed.");
  });

  it("falls back when detail is present but blank", async () => {
    mockFetch(jsonResponse({ detail: "   " }, 400));
    await expect(checkDocument(FILE)).rejects.toThrow("Compliance check failed.");
  });

  it("falls back when detail is not a string", async () => {
    mockFetch(jsonResponse({ detail: { msg: "nested" } }, 422));
    await expect(checkDocument(FILE)).rejects.toThrow("Compliance check failed.");
  });

  it("tells the reviewer a slow evaluation may have timed out", async () => {
    mockFetch(textResponse("<html>504 Gateway Timeout</html>", 504));
    await expect(evaluateDocument(FILE, "a-policy", "check-1")).rejects.toThrow(
      /retry if the proxy timed out/,
    );
  });
});

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

describe("check and evaluate", () => {
  it("posts the file as multipart form data", async () => {
    const spy = mockFetch(jsonResponse({ matched: true }));
    await checkDocument(FILE);
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/check");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBe(FILE);
  });

  it("sends slug and check_id alongside the file", async () => {
    const spy = mockFetch(jsonResponse({ slug: "a-policy" }));
    await evaluateDocument(FILE, "a-policy", "check-123");
    const body = spy.mock.calls[0][1].body as FormData;
    expect(body.get("slug")).toBe("a-policy");
    expect(body.get("check_id")).toBe("check-123");
  });

  it("returns the parsed body on success", async () => {
    mockFetch(jsonResponse({ matched: false, match_gap: 0.8 }));
    await expect(checkDocument(FILE)).resolves.toEqual({
      matched: false,
      match_gap: 0.8,
    });
  });
});

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

describe("reports", () => {
  it("reads the listing without caching", async () => {
    const spy = mockFetch(jsonResponse({ reports: [] }));
    await fetchReports();
    expect(spy).toHaveBeenCalledWith("/api/reports", { cache: "no-store" });
  });

  it("encodes the id into the path", async () => {
    const spy = mockFetch(jsonResponse({ id: "x" }));
    await fetchReport("a/b?c=d");
    expect(spy.mock.calls[0][0]).toBe("/api/reports/a%2Fb%3Fc%3Dd");
  });

  it("deletes with the DELETE verb", async () => {
    const spy = mockFetch(new Response(null, { status: 200 }));
    await deleteSavedReport("abc");
    expect(spy.mock.calls[0][1]).toEqual({ method: "DELETE" });
  });

  it("reports a failed delete", async () => {
    mockFetch(jsonResponse({ detail: "Report not found." }, 404));
    await expect(deleteSavedReport("abc")).rejects.toThrow("Report not found.");
  });
});

// ---------------------------------------------------------------------------
// Policies and settings
// ---------------------------------------------------------------------------

describe("policies and settings", () => {
  it("encodes a slug into the pdf url", () => {
    expect(policyPdfUrl("a b/c")).toBe("/api/policies/a%20b%2Fc/pdf");
  });

  it("encodes a slug into the safeguards url", async () => {
    const spy = mockFetch(jsonResponse({ safeguards: [] }));
    await fetchPolicySafeguards("../etc");
    expect(spy.mock.calls[0][0]).toBe("/api/policies/..%2Fetc/safeguards");
  });

  it("sends settings as JSON with the match rule included", async () => {
    const spy = mockFetch(jsonResponse({ provider: "stanford" }));
    await saveLlmSettings({
      provider: "stanford",
      chat_model: "gpt-5.6-sol",
      embedding_model: "text-embedding-ada-002",
      reasoning_effort: "medium",
      match_min_confidence: 50,
      match_min_gap: 2.5,
      output_columns: [],
    });
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/llm/settings");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toMatchObject({
      match_min_confidence: 50,
      match_min_gap: 2.5,
    });
  });

  it("surfaces a rejected settings save", async () => {
    mockFetch(
      jsonResponse({ detail: "match min gap must be between 0 and 100." }, 400),
    );
    await expect(
      saveLlmSettings({
        provider: "stanford",
        chat_model: "gpt-5.6-sol",
        embedding_model: "text-embedding-ada-002",
        reasoning_effort: "medium",
        match_min_confidence: 50,
        match_min_gap: 500,
        output_columns: [],
      }),
    ).rejects.toThrow("match min gap must be between 0 and 100.");
  });
});
