"use client";

import { useState } from "react";

import { policyPdfUrl } from "@/lib/api";
import type {
  EvaluateFinding,
  EvaluateResponse,
  EvaluateVerdict,
} from "@/lib/types";

const CARD =
  "rounded-card border border-line/80 bg-paper p-5 shadow-card";

const FILTERS: { id: "all" | EvaluateVerdict; label: string }[] = [
  { id: "all", label: "All" },
  { id: "aligned", label: "Aligned" },
  { id: "contradicted", label: "Contradicted" },
  { id: "missing", label: "Missing" },
  { id: "flagged", label: "Flagged" },
];

export function EvaluationDashboard({ report }: { report: EvaluateResponse }) {
  const [filter, setFilter] = useState<"all" | EvaluateVerdict>("all");
  const rows =
    filter === "all"
      ? report.rows
      : report.rows.filter((row) => row.verdict === filter);
  const pdfHref = report.pdf_url || (report.slug ? policyPdfUrl(report.slug) : "");

  return (
    <div className="grid gap-4">
      <section className={CARD}>
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Evaluation
        </p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
              {report.title}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {report.category ? `${report.category} · ` : ""}
              {report.rows.length} requirements · {report.model} at{" "}
              {report.reasoning_effort} effort
            </p>
          </div>
          {pdfHref ? (
            <a
              href={pdfHref}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-semibold text-cardinal underline-offset-2 hover:underline"
            >
              Open PDF
            </a>
          ) : null}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat
          label="Alignment"
          value={report.score.toFixed(1)}
          hint="Percent aligned"
          tone="ink"
          large
        />
        <Stat
          label="Aligned"
          value={String(report.counts.aligned)}
          hint="Satisfied"
          tone="pass"
        />
        <Stat
          label="Contradicted"
          value={String(report.counts.contradicted)}
          hint="Conflicts"
          tone="fail"
        />
        <Stat
          label="Missing"
          value={String(report.counts.missing)}
          hint="Not addressed"
          tone="fail"
        />
        <Stat
          label="Flagged"
          value={String(report.counts.flagged)}
          hint="Needs review"
          tone="warn"
        />
      </section>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setFilter(item.id)}
            className={`cursor-pointer rounded-pill px-3 py-1.5 text-sm font-semibold ${
              filter === item.id
                ? "bg-cardinal text-paper"
                : "border border-line bg-paper text-ink hover:border-ink"
            }`}
          >
            {item.label}
            {item.id === "all"
              ? ` ${report.rows.length}`
              : ` ${report.counts[item.id]}`}
          </button>
        ))}
      </div>

      <ol className="grid list-none gap-3 p-0">
        {rows.map((row) => (
          <FindingCard key={row.requirement_id} row={row} />
        ))}
      </ol>
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
  tone,
  large,
}: {
  label: string;
  value: string;
  hint: string;
  tone: "ink" | "pass" | "fail" | "warn";
  large?: boolean;
}) {
  const color =
    tone === "pass"
      ? "text-pass"
      : tone === "fail"
        ? "text-fail"
        : tone === "warn"
          ? "text-warn"
          : "text-ink";
  return (
    <div className={CARD}>
      <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
        {label}
      </p>
      <p
        className={`mt-1 font-serif font-semibold leading-none ${color} ${
          large ? "text-5xl" : "text-4xl"
        }`}
      >
        {value}
        {large ? <span className="text-2xl">%</span> : null}
      </p>
      <p className="mt-2 text-sm text-muted">{hint}</p>
    </div>
  );
}

function FindingCard({ row }: { row: EvaluateFinding }) {
  const tone = verdictTone(row.verdict);
  return (
    <li className={`${CARD} grid gap-3`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
            {row.requirement_id}
          </p>
          {row.definition ? (
            <p className="mt-1 text-[0.95rem] leading-relaxed text-ink">
              {row.definition}
            </p>
          ) : null}
        </div>
        <span
          className={`shrink-0 rounded-pill px-2.5 py-0.5 text-[0.68rem] font-extrabold uppercase tracking-[0.12em] ${tone}`}
        >
          {row.verdict}
        </span>
      </div>
      <div className="grid gap-2">
        <QuoteBlock label="Requirement" text={row.requirement_quote} />
        {row.verdict === "missing" && !row.evidence_quote ? (
          <p className="text-sm text-muted">
            No supporting passage was found in the uploaded document.
          </p>
        ) : (
          <QuoteBlock label="Evidence" text={row.evidence_quote} />
        )}
        {row.rationale ? (
          <p className="text-sm leading-relaxed text-muted">{row.rationale}</p>
        ) : null}
        {row.sources.length > 0 ? (
          <p className="text-xs text-muted">
            Chunks: {row.sources.map((item) => item.chunk_id).join(", ")}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function QuoteBlock({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <figure className="rounded-control border border-line/80 bg-sand/60 px-3.5 py-3">
      <figcaption className="text-[0.68rem] font-bold uppercase tracking-[0.14em] text-cardinal">
        {label}
      </figcaption>
      <blockquote className="mt-1 text-[0.95rem] leading-relaxed text-ink">
        {text}
      </blockquote>
    </figure>
  );
}

function verdictTone(verdict: EvaluateVerdict): string {
  if (verdict === "aligned") return "bg-pass/12 text-pass";
  if (verdict === "flagged") return "bg-warn/15 text-warn";
  return "bg-fail/12 text-fail";
}
