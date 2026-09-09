import type { CheckResponse, PolicyCatalog, RuleInfo } from "./types";

export async function fetchRules(): Promise<RuleInfo[]> {
  const response = await fetch("/api/rules", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load compliance rules.");
  }
  return response.json();
}

export async function checkDocument(
  html: string,
  filename: string,
): Promise<CheckResponse> {
  const response = await fetch("/api/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ html, filename }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail =
      error && typeof error.detail === "string"
        ? error.detail
        : "Compliance check failed.";
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchPolicies(): Promise<PolicyCatalog> {
  const response = await fetch("/api/policies", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load the SANS policy catalog.");
  }
  return response.json();
}

export function policyPdfUrl(slug: string): string {
  return `/api/policies/${encodeURIComponent(slug)}/pdf`;
}
