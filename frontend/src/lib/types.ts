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
