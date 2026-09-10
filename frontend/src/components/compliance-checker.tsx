"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { toast } from "react-toastify/unstyled";

import { useCheckSession } from "@/components/check-session";
import { EvaluationDashboard } from "@/components/evaluation-dashboard";
import { checkDocument, evaluateDocument } from "@/lib/api";
import type { CheckResponse, EvaluateResponse } from "@/lib/types";

const CHECK_TOAST_ID = "document-check";
const EVAL_TOAST_ID = "document-evaluate";
const ACCEPT = ".pdf,.txt,.md,.html,.htm,.docx";
const ALLOWED = /\.(pdf|txt|md|html|htm|docx)$/i;
const MAX_BYTES = 12 * 1024 * 1024;

const CARD =
  "rounded-card border border-line/80 bg-paper p-5 shadow-card";
const PRIMARY_BUTTON =
  "cursor-pointer rounded-control bg-cardinal px-4 py-2.5 font-semibold text-paper hover:bg-cardinal-dark disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal";

export function ComplianceChecker() {
  const {
    report,
    selectedSlug,
    evaluating,
    setReport,
    setEvaluating,
    registerEvaluate,
  } = useCheckSession();
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluateResponse | null>(null);

  const canCheck = Boolean(file) && !isChecking;

  async function runCheck() {
    if (!file) return;
    setIsChecking(true);
    setError(null);
    setEvaluation(null);
    toast.loading("Ranking the document against SANS policies…", {
      toastId: CHECK_TOAST_ID,
    });
    try {
      const response = await checkDocument(file);
      setReport(response);
      toast.update(CHECK_TOAST_ID, {
        render: checkCompleteMessage(response),
        type: response.matched ? "success" : "warning",
        isLoading: false,
        autoClose: 5000,
      });
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Something went wrong.";
      setReport(null);
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

  const runEvaluate = useCallback(async () => {
    if (!file || !report || !selectedSlug) return;
    if (!report.matched) return;
    setEvaluating(true);
    toast.loading(
      "Evaluating requirements with gpt-5.6-sol at high effort. Large policies can take several minutes…",
      {
        toastId: EVAL_TOAST_ID,
      },
    );
    try {
      const response = await evaluateDocument(
        file,
        selectedSlug,
        report.check_id,
      );
      setEvaluation(response);
      toast.update(EVAL_TOAST_ID, {
        render: `Evaluated ${response.rows.length} requirements against ${response.title}. Alignment ${response.score.toFixed(1)}%.`,
        type: "success",
        isLoading: false,
        autoClose: 6000,
      });
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Evaluation failed.";
      toast.update(EVAL_TOAST_ID, {
        render: message,
        type: "error",
        isLoading: false,
        autoClose: 7000,
      });
    } finally {
      setEvaluating(false);
    }
  }, [file, report, selectedSlug, setEvaluating]);

  const previousSlug = useRef<string | null>(null);

  useEffect(() => {
    if (previousSlug.current && previousSlug.current !== selectedSlug) {
      setEvaluation(null);
    }
    previousSlug.current = selectedSlug;
  }, [selectedSlug]);

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
    setReport(null);
    setEvaluation(null);
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
    <div className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-2">
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
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
                Report
              </p>
              <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
                Findings
              </h2>
            </div>
            <ConfidenceHint />
          </div>

          {error ? (
            <p className="mb-4 rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
              {error}
            </p>
          ) : null}

          {!report && !error ? (
            <p className="leading-relaxed text-muted">
              Upload a procedure, then run a check. The backend ranks it against
              Purpose and Scope summaries. If a standard matches, evaluate its
              extracted requirements from this report.
            </p>
          ) : null}

          {report ? <ScoreWell report={report} /> : null}
        </section>
      </div>

      {report ? (
        <RankedPolicies
          evaluating={evaluating || isChecking}
          onEvaluate={() => void runEvaluate()}
        />
      ) : null}

      {evaluation ? <EvaluationDashboard report={evaluation} /> : null}
    </div>
  );
}

function ScoreWell({ report }: { report: CheckResponse }) {
  if (!report.matched) {
    return (
      <div className="rounded-control bg-warn/10 px-4 py-4 text-warn">
        <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em]">
          No match
        </p>
        <p className="mt-2 font-serif text-2xl leading-tight text-ink">
          No standard in the library matches this document.
        </p>
        <p className="mt-2 text-sm text-muted">
          Nearest policies are listed below for reference. They are not a match,
          so evaluation is disabled.
        </p>
      </div>
    );
  }

  const top = report.matches[0];
  const tone = confidenceTone(top?.confidence ?? 0);
  return (
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
  );
}

function RankedPolicies({
  evaluating,
  onEvaluate,
}: {
  evaluating: boolean;
  onEvaluate: () => void;
}) {
  const { report, topMatches, selectedSlug, setSelectedSlug } = useCheckSession();
  if (!report || topMatches.length === 0) return null;

  const matched = report.matched;
  const selected =
    topMatches.find((item) => item.slug === selectedSlug) ?? topMatches[0];
  const canEvaluate = Boolean(matched && selected && !evaluating);

  return (
    <section className={CARD}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Ranked policies
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Top 5 matches
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Confidence is cosine similarity to each policy&apos;s Purpose and
            Scope summary. Select a row, then evaluate its extracted
            requirements.
          </p>
        </div>
        {matched ? (
          <button
            type="button"
            className={PRIMARY_BUTTON}
            disabled={!canEvaluate}
            onClick={onEvaluate}
          >
            {evaluating ? "Evaluating…" : "Evaluate requirements"}
          </button>
        ) : null}
      </div>

      <ol className="grid list-none gap-2 p-0">
        {topMatches.map((item, index) => {
          const active = item.slug === selected.slug;
          return (
            <li key={item.slug}>
              <button
                type="button"
                onClick={() => setSelectedSlug(item.slug)}
                className={`flex w-full cursor-pointer items-start gap-3 rounded-control border px-3.5 py-3 text-left ${
                  active
                    ? "border-cardinal bg-cardinal/10"
                    : "border-line/80 bg-canvas/40 hover:border-cardinal/40"
                }`}
              >
                <span className="mt-0.5 w-6 shrink-0 text-sm font-semibold text-muted">
                  {index + 1}
                </span>
                <span
                  className={`shrink-0 rounded-pill px-2.5 py-1 text-[0.72rem] font-extrabold tracking-[0.08em] ${confidencePill(
                    item.confidence,
                  )}`}
                >
                  {item.confidence.toFixed(1)}%
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{item.title}</span>
                  {item.category ? (
                    <span className="mt-0.5 block text-sm text-muted">
                      {item.category}
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function ConfidenceHint() {
  return (
    <details className="relative shrink-0">
      <summary
        className="grid h-9 w-9 cursor-pointer list-none place-items-center rounded-control text-muted hover:bg-cardinal/10 hover:text-cardinal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal [&::-webkit-details-marker]:hidden"
        aria-label="How confidence is calculated"
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 10.5v6" />
          <circle cx="12" cy="7.25" r="0.85" fill="currentColor" stroke="none" />
        </svg>
      </summary>
      <div
        role="note"
        className="absolute right-0 z-10 mt-2 w-72 rounded-control border border-line bg-paper p-3.5 text-sm leading-relaxed text-muted shadow-card"
      >
        Confidence is cosine similarity between the uploaded procedure and each
        policy&apos;s Purpose and Scope summary, shown as a percentage. A match
        requires at least 50%. Evaluation then judges each extracted safeguard
        with gpt-5.6-sol at high effort.
      </div>
    </details>
  );
}

function confidenceTone(confidence: number) {
  if (confidence >= 70) {
    return { well: "bg-pass/10 text-pass" };
  }
  if (confidence >= 40) {
    return { well: "bg-warn/10 text-warn" };
  }
  return { well: "bg-fail/10 text-fail" };
}

function confidencePill(confidence: number) {
  if (confidence >= 70) {
    return "bg-pass/15 text-pass";
  }
  if (confidence >= 40) {
    return "bg-warn/15 text-warn";
  }
  return "bg-fail/15 text-fail";
}

function checkCompleteMessage(report: CheckResponse): string {
  const top = report.matches[0];
  if (!report.matched || !top) {
    return `No standard in the library matches ${report.filename}.`;
  }
  return `Check complete for ${report.filename}. Top match ${top.title} at ${top.confidence.toFixed(1)}%.`;
}
