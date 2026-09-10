"use client";

import { useEffect, useState } from "react";

import { fetchPolicySafeguards } from "@/lib/api";
import type { PolicySafeguard } from "@/lib/types";

export function SafeguardsDialog({
  slug,
  title,
  onClose,
}: {
  slug: string;
  title: string;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<PolicySafeguard[] | null>(null);
  const [fault, setFault] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setFault(null);
    fetchPolicySafeguards(slug)
      .then((payload) => {
        if (!cancelled) setRows(payload.safeguards);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setFault(
          caught instanceof Error ? caught.message : "Could not load safeguards.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="safeguards-title"
        className="flex max-h-[min(36rem,calc(100vh-2rem))] w-full max-w-3xl flex-col overflow-hidden rounded-card border border-line bg-paper shadow-card"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
              Safeguards
            </p>
            <h3
              id="safeguards-title"
              className="font-serif text-2xl font-semibold tracking-tight"
            >
              {title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-control border border-line px-3 py-1.5 text-sm font-semibold hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 overflow-y-auto px-5 py-4">
          {fault ? (
            <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm text-fail">
              {fault}
            </p>
          ) : null}
          {rows === null && !fault ? (
            <p className="text-sm text-muted">Loading safeguards…</p>
          ) : null}
          {rows && rows.length === 0 ? (
            <p className="text-sm text-muted">
              No safeguards extracted for this policy yet. Run{" "}
              <code className="font-mono text-[0.85em]">make index</code> after
              a scrape.
            </p>
          ) : null}
          {rows && rows.length > 0 ? (
            <ul className="grid list-none gap-0 p-0">
              <li className="grid grid-cols-1 gap-1 border-b border-line py-2 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)] sm:gap-6">
                <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
                  Category
                </p>
                <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
                  Definition
                </p>
              </li>
              {rows.map((row) => (
                <li
                  key={`${row.category}-${row.definition.slice(0, 40)}`}
                  className="grid grid-cols-1 gap-1 border-b border-line/80 py-3 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)] sm:items-start sm:gap-6"
                >
                  <p className="font-semibold text-ink">{row.category}</p>
                  <p className="text-[0.95rem] leading-relaxed text-muted">
                    {row.definition}
                  </p>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}
