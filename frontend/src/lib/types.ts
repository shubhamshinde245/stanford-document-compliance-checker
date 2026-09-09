export type PolicyMatch = {
  slug: string;
  title: string;
  category: string;
  confidence: number;
  score: number;
  snippet: string;
  chunk_id: string;
  source_url: string;
};

export type CheckResponse = {
  filename: string;
  model: string;
  matches: PolicyMatch[];
};

export type PolicyRecord = {
  slug: string;
  title: string;
  category: string;
  kind: string;
  published_on: string | null;
  source_url: string;
  pdf_path: string | null;
  pdf_bytes: number | null;
  summary: string;
  purpose: string;
  scope: string;
  scraped_at: string;
  error: string | null;
  index_error: string | null;
  refresh_status: string | null;
  previous_published_on: string | null;
};

export type ScrapeCheck = {
  checked_at: string;
  added: number;
  updated: number;
  unchanged: number;
  kept: number;
  failed: number;
};

export type PolicyCatalog = {
  source_url: string;
  showing_text: string;
  listed: number;
  total: number;
  scraped_at: string;
  last_check: ScrapeCheck | null;
  policies: PolicyRecord[];
};

export type PolicySchedule = {
  enabled: boolean;
  hour: number;
  minute: number;
  timezone: string;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_summary: string | null;
  next_run_at: string | null;
  running: boolean;
};

export type LLMProvider = "stanford" | "openai" | "anthropic";
export type LLMEffort = "none" | "low" | "medium" | "high";
export type LLMModelKind = "chat" | "embedding" | "other";

export type LLMModelInfo = {
  id: string;
  kind: LLMModelKind;
  owned_by: string;
};

export type LLMProviderStatus = {
  stanford: boolean;
  openai: boolean;
  anthropic: boolean;
  ollama: boolean;
};

export type OutputColumn = {
  name: string;
  description: string;
};

export type LLMSettings = {
  provider: LLMProvider;
  chat_model: string;
  embedding_model: string;
  reasoning_effort: LLMEffort;
  output_columns: OutputColumn[];
  locked_columns: string[];
  configured: LLMProviderStatus;
};

export type OutputSchemaPreview = {
  system_prompt: string;
  json_schema: Record<string, unknown>;
  verdicts: string[];
};

export type LLMChatResponse = {
  model: string;
  content: string;
  reasoning_effort: LLMEffort | null;
};

export type LLMEmbedResponse = {
  model: string;
  dimensions: number;
  preview: number[];
};
