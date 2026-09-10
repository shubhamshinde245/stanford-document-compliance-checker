"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EvaluationDashboard } from "@/components/evaluation-dashboard";
import { fetchReport } from "@/lib/api";
import type { SavedReport } from "@/lib/types";

const CARD = "rounded-card border border-line/80 bg-paper p-5 shadow-card";

export default function SavedReportPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [report, setReport] = useState<SavedReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await fetchReport(id);
        if (!cancelled) {
          setReport(next);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Could not load that report.",
          );
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8">
      <header className="mb-8 pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Archive
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          {report?.title ?? "Saved report"}
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          {report
            ? `${report.filename} · ${formatWhen(report.created_at)}`
            : "Loading a previously saved evaluation."}
        </p>
        <p className="mt-4">
          <Link
            href="/reports"
            className="text-sm font-semibold text-cardinal underline-offset-2 hover:underline"
          >
            Back to saved reports
          </Link>
        </p>
      </header>
      <main className="grid gap-6">
        {error ? (
          <p className="rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
            {error}
          </p>
        ) : null}
        {!report && !error ? (
          <p className="text-muted">Loading saved report…</p>
        ) : null}
        {report && report.matches.length > 0 ? (
          <section className={CARD}>
            <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
              Ranked at check time
            </p>
            <ol className="mt-3 grid list-none gap-2 p-0">
              {report.matches.map((item) => (
                <li
                  key={item.slug}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="min-w-0 font-semibold">{item.title}</span>
                  <span className="shrink-0 text-muted">
                    {item.confidence.toFixed(1)}%
                  </span>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
        {report ? <EvaluationDashboard report={report.evaluation} /> : null}
      </main>
    </div>
  );
}

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
