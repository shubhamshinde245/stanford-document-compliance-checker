import type {
  CheckResponse,
  LLMChatResponse,
  LLMEmbedResponse,
  LLMEffort,
  LLMModelInfo,
  LLMProvider,
  LLMSettings,
  OutputColumn,
  OutputSchemaPreview,
  PolicyCatalog,
  PolicySchedule,
} from "./types";

async function readDetail(response: Response, fallback: string): Promise<string> {
  const error = await response.json().catch(() => null);
  return error && typeof error.detail === "string" ? error.detail : fallback;
}

export async function checkDocument(file: File): Promise<CheckResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/check", {
    method: "POST",
    body,
  });

  if (!response.ok) {
    throw new Error(await readDetail(response, "Compliance check failed."));
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

export async function fetchPolicySchedule(): Promise<PolicySchedule> {
  const response = await fetch("/api/policies/schedule", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load the refresh schedule.");
  }
  return response.json();
}

export async function savePolicySchedule(payload: {
  enabled: boolean;
  hour: number;
  minute: number;
}): Promise<PolicySchedule> {
  const response = await fetch("/api/policies/schedule", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Could not save the refresh schedule.");
  }
  return response.json();
}

export async function runPolicyScrape(): Promise<PolicyCatalog> {
  const response = await fetch("/api/policies/scrape", { method: "POST" });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail =
      error && typeof error.detail === "string"
        ? error.detail
        : "Policy refresh failed.";
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchLlmSettings(): Promise<LLMSettings> {
  const response = await fetch("/api/llm/settings", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Could not load model settings."));
  }
  return response.json();
}

export async function fetchOutputSchema(): Promise<OutputSchemaPreview> {
  const response = await fetch("/api/llm/output-schema", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Could not load the output schema."));
  }
  return response.json();
}

export async function saveLlmSettings(payload: {
  provider: LLMProvider;
  chat_model: string;
  embedding_model: string;
  reasoning_effort: LLMEffort;
  output_columns: OutputColumn[];
}): Promise<LLMSettings> {
  const response = await fetch("/api/llm/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Could not save model settings."));
  }
  return response.json();
}

export async function fetchLlmModels(): Promise<LLMModelInfo[]> {
  const response = await fetch("/api/llm/models", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Could not load available models."));
  }
  return response.json();
}

export async function testLlmChat(payload: {
  prompt: string;
  model?: string;
  reasoning_effort?: LLMEffort;
}): Promise<LLMChatResponse> {
  const response = await fetch("/api/llm/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Chat test failed."));
  }
  return response.json();
}

export async function testLlmEmbeddings(payload: {
  input: string;
  model?: string;
}): Promise<LLMEmbedResponse> {
  const response = await fetch("/api/llm/embeddings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readDetail(response, "Embedding test failed."));
  }
  return response.json();
}
