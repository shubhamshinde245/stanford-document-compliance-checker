import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 1800;

const API_ORIGIN = process.env.API_URL ?? "http://127.0.0.1:8000";
const EVALUATE_TIMEOUT_MS = 30 * 60 * 1000;

export async function POST(request: NextRequest) {
  const body = await request.formData();
  try {
    const response = await fetch(`${API_ORIGIN}/api/evaluate`, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(EVALUATE_TIMEOUT_MS),
    });
    const payload = await response.arrayBuffer();
    return new Response(payload, {
      status: response.status,
      headers: {
        "content-type":
          response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (caught) {
    const timedOut =
      caught instanceof Error &&
      (caught.name === "TimeoutError" || caught.name === "AbortError");
    return Response.json(
      {
        detail: timedOut
          ? "Requirement evaluation timed out. Retry, or pick a policy with fewer extracted requirements."
          : "Could not reach the evaluation API.",
      },
      { status: timedOut ? 504 : 502 },
    );
  }
}
