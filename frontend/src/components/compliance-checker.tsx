"use client";

import { useState } from "react";
import { toast } from "react-toastify/unstyled";

import { checkDocument } from "@/lib/api";
import { SAMPLE_FILENAME, SAMPLE_HTML } from "@/lib/sample-document";
import type { CheckResponse, Finding, Severity } from "@/lib/types";

const CHECK_TOAST_ID = "document-check";
const HTML_FILE = /\.(html|htm|txt)$/i;

const scoreTone: Record<Severity, string> = {
  pass: "border-pass text-pass",
  warn: "border-warn text-warn",
  fail: "border-fail text-fail",
};

const markTone: Record<Severity, string> = {
  pass: "text-pass",
  warn: "text-warn",
  fail: "text-fail",
};

export function ComplianceChecker() {
  const [html, setHtml] = useState("");
  const [filename, setFilename] = useState("document.html");
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const canCheck = html.trim().length > 0 && !isChecking;

  async function runCheck() {
    setIsChecking(true);
    setError(null);
    toast.loading("Checking document against Stanford rules…", {
      toastId: CHECK_TOAST_ID,
    });
    try {
      const response = await checkDocument(html, filename);
      setResult(response);
      toast.update(CHECK_TOAST_ID, {
        render: checkCompleteMessage(response),
        type: toastTypeFor(response),
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

  function loadSample() {
    setHtml(SAMPLE_HTML);
    setFilename(SAMPLE_FILENAME);
    setResult(null);
    setError(null);
    toast.info("Sample draft loaded. Run a check to score it.");
  }

  async function onFile(file: File | undefined) {
    if (!file) {
      toast.warning("No file selected.");
      return;
    }
    if (!HTML_FILE.test(file.name)) {
      toast.error("Please choose an HTML or text file.");
      return;
    }
    let text: string;
    try {
      text = await file.text();
    } catch {
      toast.error(`Could not read ${file.name}.`);
      return;
    }
    if (!text.trim()) {
      toast.warning(`${file.name} is empty. Paste HTML or pick another file.`);
      return;
    }
    setHtml(text);
    setFilename(file.name);
    setResult(null);
    setError(null);
    toast.success(`Loaded ${file.name}. Ready to run a compliance check.`);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
      <section className="rounded-sm border border-line bg-paper p-5 shadow-[0_18px_40px_rgba(46,45,41,0.06)]">
        <div className="mb-4">
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Source
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Document
          </h2>
        </div>

        <label className="grid cursor-pointer gap-0.5 border border-dashed border-[#c4b8a4] bg-cardinal/5 p-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-solid focus-within:outline-cardinal">
          <input
            type="file"
            accept=".html,.htm,.txt,text/html"
            className="sr-only"
            onChange={(event) => void onFile(event.target.files?.[0])}
          />
          <span className="font-semibold">Drop an HTML file or click to upload</span>
          <span className="text-sm text-muted">{filename}</span>
        </label>

        <label className="mt-4 grid gap-1.5 text-sm font-semibold">
          HTML
          <textarea
            value={html}
            onChange={(event) => setHtml(event.target.value)}
            placeholder="Paste a Stanford HTML document…"
            spellCheck={false}
            className="min-h-70 w-full resize-y border border-line bg-[#fffdf8] p-3.5 font-mono text-xs leading-relaxed text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
          />
        </label>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="cursor-pointer border border-line bg-transparent px-4 py-2.5 font-semibold hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
            onClick={loadSample}
          >
            Load sample draft
          </button>
          <button
            type="button"
            className="cursor-pointer bg-cardinal px-4 py-2.5 font-semibold text-[#fffdf8] hover:bg-cardinal-dark disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
            disabled={!canCheck}
            onClick={() => void runCheck()}
          >
            {isChecking ? "Checking…" : "Run compliance check"}
          </button>
        </div>
      </section>

      <section className="rounded-sm border border-line bg-paper p-5 shadow-[0_18px_40px_rgba(46,45,41,0.06)]">
        <div className="mb-4">
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Report
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Findings
          </h2>
        </div>

        {error ? (
          <p className="mb-4 bg-[#f8e8e8] px-3.5 py-3 leading-relaxed text-fail">
            {error}
          </p>
        ) : null}

        {!result && !error ? (
          <p className="leading-relaxed text-muted">
            Upload or paste a document, then run a check. The backend parses the HTML
            with Beautiful Soup and scores Stanford identity, accessibility, and
            structure rules.
          </p>
        ) : null}

        {result ? <Results report={result} /> : null}
      </section>
    </div>
  );
}

function Results({ report }: { report: CheckResponse }) {
  const tone: Severity =
    report.summary.failed > 0 ? "fail" : report.summary.warnings > 0 ? "warn" : "pass";

  return (
    <div className="grid gap-4">
      <div className={`border-l-4 bg-[#fffdf8] px-4 py-4 ${scoreTone[tone]}`}>
        <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em]">
          Compliance score
        </p>
        <p className="font-serif text-6xl leading-none">{report.summary.score}</p>
        <p className="mb-3.5 text-sm text-muted">{report.filename}</p>
        <dl className="grid grid-cols-3 gap-3">
          <div>
            <dt className="text-xs text-muted">Passed</dt>
            <dd className="mt-0.5 text-xl font-bold text-ink">{report.summary.passed}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Warnings</dt>
            <dd className="mt-0.5 text-xl font-bold text-ink">{report.summary.warnings}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Failed</dt>
            <dd className="mt-0.5 text-xl font-bold text-ink">{report.summary.failed}</dd>
          </div>
        </dl>
      </div>

      <ol className="grid list-none gap-2.5 p-0">
        {report.findings.map((finding) => (
          <FindingRow key={finding.id} finding={finding} />
        ))}
      </ol>
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <li className="grid grid-cols-1 gap-1 border-t border-line py-3 sm:grid-cols-[3.4rem_minmax(0,1fr)] sm:gap-3">
      <span
        className={`mt-0.5 self-start text-[0.72rem] font-extrabold uppercase tracking-[0.12em] ${markTone[finding.severity]}`}
      >
        {labelFor(finding.severity)}
      </span>
      <div>
        <p className="font-bold">{finding.title}</p>
        <p className="mt-1 text-[0.95rem] leading-snug text-muted">{finding.message}</p>
        {finding.details ? (
          <p className="mt-1 text-[0.95rem] leading-snug text-muted">{finding.details}</p>
        ) : null}
      </div>
    </li>
  );
}

function labelFor(severity: Severity) {
  if (severity === "pass") return "Pass";
  if (severity === "warn") return "Warn";
  return "Fail";
}

function toastTypeFor(report: CheckResponse): "success" | "warning" | "error" {
  if (report.summary.failed > 0) return "error";
  if (report.summary.warnings > 0) return "warning";
  return "success";
}

function checkCompleteMessage(report: CheckResponse): string {
  const { score, failed, warnings, passed } = report.summary;
  if (failed > 0) {
    return `Check complete for ${report.filename}. Score ${score} — ${failed} failed, ${warnings} warnings.`;
  }
  if (warnings > 0) {
    return `Check complete for ${report.filename}. Score ${score} with ${warnings} warnings.`;
  }
  return `Check complete for ${report.filename}. Score ${score} — all ${passed} rules passed.`;
}
