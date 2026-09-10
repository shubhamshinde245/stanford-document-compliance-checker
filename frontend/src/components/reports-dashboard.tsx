"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "react-toastify/unstyled";

import { deleteSavedReport, fetchReports } from "@/lib/api";
import type { SavedReportSummary } from "@/lib/types";

const CARD = "rounded-card border border-line/80 bg-paper p-5 shadow-card";
const SECONDARY_BUTTON =
  "cursor-pointer rounded-control border border-line px-3 py-2 text-sm font-semibold hover:border-ink disabled:cursor-not-allowed disabled:opacity-55";

export function ReportsDashboard() {
  const [reports, setReports] = useState<SavedReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const payload = await fetchReports();
      setReports(payload.reports);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Could not load saved reports.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onDelete(id: string, title: string) {
    if (!window.confirm(`Delete the saved report for ${title}?`)) {
      return;
    }
    setDeletingId(id);
    try {
      await deleteSavedReport(id);
      setReports((current) => current.filter((item) => item.id !== id));
      toast.success("Report deleted.");
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : "Could not delete that report.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <p className="text-muted">Loading saved reports…</p>;
  }

  if (error) {
    return (
      <p className="rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
        {error}
      </p>
    );
  }

  if (reports.length === 0) {
    return (
      <section className={CARD}>
        <p className="leading-relaxed text-muted">
          No saved evaluations yet. Run a check on Checker, then Evaluate
          requirements. Finished reports are stored on this machine under
          data/reports.
        </p>
      </section>
    );
  }

  return (
    <ol className="grid list-none gap-3 p-0">
      {reports.map((item) => (
        <li key={item.id} className={CARD}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
                {formatWhen(item.created_at)}
              </p>
              <h2 className="mt-1 font-serif text-[1.35rem] font-semibold tracking-tight">
                {item.title}
              </h2>
              <p className="mt-1 text-sm text-muted">
                {item.filename}
                {item.category ? ` · ${item.category}` : ""}
              </p>
            </div>
            <p
              className={`font-serif text-4xl font-semibold leading-none ${scoreTone(
                item.score,
              )}`}
            >
              {item.score.toFixed(1)}
              <span className="text-xl">%</span>
            </p>
          </div>
          <p className="mt-3 text-sm text-muted">
            {item.counts.aligned} aligned · {item.counts.contradicted}{" "}
            contradicted · {item.counts.missing} missing · {item.counts.flagged}{" "}
            flagged
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={`/reports/${item.id}`}
              className="cursor-pointer rounded-control bg-cardinal px-4 py-2.5 text-sm font-semibold text-paper no-underline hover:bg-cardinal-dark"
            >
              Open
            </Link>
            <button
              type="button"
              className={SECONDARY_BUTTON}
              disabled={deletingId === item.id}
              onClick={() => void onDelete(item.id, item.title)}
            >
              {deletingId === item.id ? "Deleting…" : "Delete"}
            </button>
          </div>
        </li>
      ))}
    </ol>
  );
}

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function scoreTone(score: number): string {
  if (score >= 70) return "text-pass";
  if (score >= 40) return "text-warn";
  return "text-fail";
}
