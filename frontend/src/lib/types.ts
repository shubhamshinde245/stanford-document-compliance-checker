export type Severity = "pass" | "fail" | "warn";

export type Finding = {
  id: string;
  title: string;
  severity: Severity;
  message: string;
  details: string | null;
};

export type CheckSummary = {
  passed: number;
  failed: number;
  warnings: number;
  score: number;
};

export type CheckResponse = {
  filename: string;
  summary: CheckSummary;
  findings: Finding[];
};

export type RuleInfo = {
  id: string;
  title: string;
  description: string;
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
  scraped_at: string;
  error: string | null;
};

export type PolicyCatalog = {
  source_url: string;
  showing_text: string;
  listed: number;
  total: number;
  scraped_at: string;
  policies: PolicyRecord[];
};
