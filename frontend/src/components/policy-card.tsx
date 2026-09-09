"use client";

import { toast } from "react-toastify/unstyled";

import { policyPdfUrl } from "@/lib/api";

export type PolicyCardPolicy = {
  slug: string;
  title: string;
  category: string;
  source_url: string;
  pdf_url?: string | null;
  pdf_path?: string | null;
  pdf_bytes?: number | null;
  published_on?: string | null;
  previous_published_on?: string | null;
  summary?: string;
  error?: string | null;
  refresh_status?: string | null;
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Unknown date";
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function statusLabel(status: string | null | undefined): string | null {
  if (status === "updated") return "Updated";
  if (status === "added") return "New";
  return null;
}

function confidenceTone(confidence: number) {
  if (confidence >= 70) return "bg-pass/12 text-pass";
  if (confidence >= 40) return "bg-warn/15 text-warn";
  return "bg-fail/12 text-fail";
}

export function PolicyCard({
  policy,
  confidence,
  onViewSafeguards,
}: {
  policy: PolicyCardPolicy;
  confidence?: number;
  onViewSafeguards: (policy: PolicyCardPolicy) => void;
}) {
  const badge = statusLabel(policy.refresh_status);
  const pdfHref = policy.pdf_url || (policy.pdf_path ? policyPdfUrl(policy.slug) : "");
  const scored = confidence != null;

  return (
    <li
      className={`grid gap-3 rounded-card border border-line/80 bg-paper p-5 shadow-card ${
        scored
          ? "sm:grid-cols-[auto_minmax(0,1fr)] sm:items-start"
          : ""
      }`}
    >
      {scored ? (
        <span
          className={`mt-0.5 self-start rounded-pill px-2.5 py-0.5 text-[0.68rem] font-extrabold uppercase tracking-[0.12em] ${confidenceTone(confidence)}`}
        >
          {confidence.toFixed(1)}%
        </span>
      ) : null}
      <div className="grid min-w-0 gap-3">
        <div>
          <p className="flex flex-wrap items-center gap-2 text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
            {policy.category || "Uncategorized"}
            {badge ? (
              <span className="rounded-pill bg-cardinal/10 px-2 py-0.5 text-[0.65rem] tracking-[0.08em] text-cardinal">
                {badge}
              </span>
            ) : null}
          </p>
          <h3 className="mt-1 font-serif text-xl font-semibold leading-tight tracking-tight">
            {policy.source_url ? (
              <a
                href={policy.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-ink underline decoration-line underline-offset-2 hover:text-cardinal"
              >
                {policy.title}
              </a>
            ) : (
              policy.title
            )}
          </h3>
          <p className="mt-1 text-sm text-muted">
            Published {formatDate(policy.published_on)}
            {policy.previous_published_on &&
            policy.previous_published_on !== policy.published_on
              ? ` (was ${formatDate(policy.previous_published_on)})`
              : ""}
            {policy.pdf_bytes ? ` · ${formatBytes(policy.pdf_bytes)}` : ""}
          </p>
        </div>
        {policy.summary ? (
          <p className="text-[0.95rem] leading-relaxed text-muted">
            {policy.summary}
          </p>
        ) : null}
        {policy.error ? (
          <p className="text-sm text-fail">{policy.error}</p>
        ) : null}
        <div className="flex flex-wrap gap-3 text-sm font-semibold">
          <a
            href={policy.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-cardinal underline-offset-2 hover:underline"
            onClick={() => toast.info(`Opening source for “${policy.title}”.`)}
          >
            Source URL
          </a>
          {pdfHref ? (
            <a
              href={pdfHref}
              target="_blank"
              rel="noreferrer"
              className="text-cardinal underline-offset-2 hover:underline"
              onClick={() => toast.info(`Opening PDF: ${policy.title}`)}
            >
              Open PDF
            </a>
          ) : (
            <span className="text-muted">PDF unavailable</span>
          )}
          <button
            type="button"
            onClick={() => onViewSafeguards(policy)}
            className="cursor-pointer text-cardinal underline-offset-2 hover:underline"
          >
            View safeguards
          </button>
        </div>
      </div>
    </li>
  );
}
