"use client";

import { useState, type DragEvent } from "react";
import { toast } from "react-toastify/unstyled";

import { checkDocument, policyPdfUrl } from "@/lib/api";
import type { CheckResponse, PolicyMatch } from "@/lib/types";

const CHECK_TOAST_ID = "document-check";
const ACCEPT = ".pdf,.txt,.md,.html,.htm,.docx";
const ALLOWED = /\.(pdf|txt|md|html|htm|docx)$/i;
const MAX_BYTES = 12 * 1024 * 1024;

const CARD =
  "rounded-card border border-line/80 bg-paper p-5 shadow-card";
const PRIMARY_BUTTON =
  "cursor-pointer rounded-control bg-cardinal px-4 py-2.5 font-semibold text-paper hover:bg-cardinal-dark disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal";

export function ComplianceChecker() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const canCheck = Boolean(file) && !isChecking;

  async function runCheck() {
    if (!file) return;
    setIsChecking(true);
    setError(null);
    toast.loading("Ranking the document against SANS policies…", {
      toastId: CHECK_TOAST_ID,
    });
    try {
      const response = await checkDocument(file);
      setResult(response);
      toast.update(CHECK_TOAST_ID, {
        render: checkCompleteMessage(response),
        type: "success",
        isLoading: false,
        autoClose: 5000,
      });
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Something went wrong.";
      setResult(null);
      setError(message);
      toast.update(CHECK_TOAST_ID, {
        render: message,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setIsChecking(false);
    }
  }

  function acceptFile(next: File | undefined) {
    if (!next) {
      toast.warning("No file selected.");
      return;
    }
    if (!ALLOWED.test(next.name)) {
      toast.error("Upload a PDF, DOCX, HTML, Markdown, or text file.");
      return;
    }
    if (next.size > MAX_BYTES) {
      toast.error("File is larger than 12 MB.");
      return;
    }
    setFile(next);
    setResult(null);
    setError(null);
    toast.success(`Selected ${next.name}. Ready to run a compliance check.`);
  }

  function onDragOver(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(true);
  }

  function onDragLeave(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    acceptFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
      <section className={CARD}>
        <div className="mb-4">
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Source
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Document
          </h2>
        </div>

        <label
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={`grid cursor-pointer gap-0.5 rounded-control border border-dashed p-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-solid focus-within:outline-cardinal ${
            dragOver
              ? "border-cardinal bg-cardinal/10"
              : "border-line bg-cardinal/5"
          }`}
        >
          <input
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(event) => {
              acceptFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <span className="font-semibold">
            Drop a procedure here or click to upload
          </span>
          <span className="text-sm text-muted">
            {file
              ? file.name
              : "PDF, DOCX, HTML, Markdown, or text · up to 12 MB"}
          </span>
        </label>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className={PRIMARY_BUTTON}
            disabled={!canCheck}
            onClick={() => void runCheck()}
          >
            {isChecking ? "Checking…" : "Run compliance check"}
          </button>
        </div>
      </section>

      <section className={CARD}>
        <div className="mb-4">
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Report
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Findings
          </h2>
        </div>

        {error ? (
          <p className="mb-4 rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
            {error}
          </p>
        ) : null}

        {!result && !error ? (
          <p className="leading-relaxed text-muted">
            Upload a procedure, then run a check. The backend embeds the document
            and ranks it against each policy&apos;s Purpose and Scope summary.
            This pass does not issue aligned or contradicted verdicts.
          </p>
        ) : null}

        {result ? <Results report={result} /> : null}
      </section>
    </div>
  );
}

function Results({ report }: { report: CheckResponse }) {
  const [expanded, setExpanded] = useState(false);
  const top = report.matches[0];
  const tone = confidenceTone(top?.confidence ?? 0);
  const visible = expanded ? report.matches : report.matches.slice(0, 5);
  const remaining = Math.max(report.matches.length - 5, 0);

  return (
    <div className="grid gap-4">
      <div className={`rounded-control px-4 py-4 ${tone.well}`}>
        <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em]">
          Top match confidence
        </p>
        <p className="font-serif text-6xl leading-none text-ink">
          {top ? top.confidence.toFixed(1) : "—"}
        </p>
        <p className="mt-2 text-sm text-muted">{report.filename}</p>
        {top ? (
          <p className="mt-1 text-sm text-muted">
            {top.title}
            {top.category ? ` · ${top.category}` : ""}
          </p>
        ) : (
          <p className="mt-1 text-sm text-muted">No policy matches returned.</p>
        )}
      </div>

      <ol className="grid list-none gap-2.5 p-0">
        {visible.map((match) => (
          <MatchRow key={match.slug} match={match} />
        ))}
      </ol>

      {remaining > 0 ? (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="cursor-pointer rounded-control border border-line px-4 py-2.5 text-sm font-semibold hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
        >
          {expanded
            ? "Show top 5"
            : `Show all ${report.matches.length} policies`}
        </button>
      ) : null}
    </div>
  );
}

function MatchRow({ match }: { match: PolicyMatch }) {
  const tone = confidenceTone(match.confidence);
  return (
    <li className="grid grid-cols-1 gap-2 border-t border-line py-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-start sm:gap-3">
      <span
        className={`mt-0.5 self-start rounded-pill px-2.5 py-0.5 text-[0.68rem] font-extrabold uppercase tracking-[0.12em] ${tone.pill}`}
      >
        {match.confidence.toFixed(1)}%
      </span>
      <div>
        <a
          href={policyPdfUrl(match.slug)}
          target="_blank"
          rel="noreferrer"
          className="font-bold text-ink underline decoration-line underline-offset-2 hover:text-cardinal"
        >
          {match.title}
        </a>
        {match.category ? (
          <p className="mt-0.5 text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
            {match.category}
          </p>
        ) : null}
        <p className="mt-1 text-[0.95rem] leading-snug text-muted">
          {match.snippet}
        </p>
      </div>
    </li>
  );
}

function confidenceTone(confidence: number) {
  if (confidence >= 70) {
    return {
      well: "bg-pass/10 text-pass",
      pill: "bg-pass/12 text-pass",
    };
  }
  if (confidence >= 40) {
    return {
      well: "bg-warn/10 text-warn",
      pill: "bg-warn/15 text-warn",
    };
  }
  return {
    well: "bg-fail/10 text-fail",
    pill: "bg-fail/12 text-fail",
  };
}

function checkCompleteMessage(report: CheckResponse): string {
  const top = report.matches[0];
  if (!top) {
    return `Check complete for ${report.filename}. No policy matches.`;
  }
  return `Check complete for ${report.filename}. Top match ${top.title} at ${top.confidence.toFixed(1)}%.`;
}
