"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchPolicies, policyPdfUrl } from "@/lib/api";
import type { PolicyCatalog, PolicyRecord } from "@/lib/types";

function formatDate(iso: string | null): string {
  if (!iso) return "Unknown date";
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatBytes(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function categoryCounts(policies: PolicyRecord[]): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const policy of policies) {
    const name = policy.category || "Uncategorized";
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function PoliciesDashboard() {
  const [catalog, setCatalog] = useState<PolicyCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  useEffect(() => {
    let cancelled = false;
    fetchPolicies()
      .then((data) => {
        if (!cancelled) {
          setCatalog(data);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(
            caught instanceof Error ? caught.message : "Could not load policies.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const categories = useMemo(
    () => (catalog ? categoryCounts(catalog.policies) : []),
    [catalog],
  );
  const maxCount = Math.max(1, ...categories.map((item) => item.count));
  const availablePdfs = catalog?.policies.filter((item) => item.pdf_path).length ?? 0;

  const filtered = useMemo(() => {
    if (!catalog) return [];
    const needle = query.trim().toLowerCase();
    return catalog.policies.filter((policy) => {
      if (category !== "all" && (policy.category || "Uncategorized") !== category) {
        return false;
      }
      if (!needle) return true;
      return (
        policy.title.toLowerCase().includes(needle) ||
        policy.summary.toLowerCase().includes(needle) ||
        policy.category.toLowerCase().includes(needle)
      );
    });
  }, [catalog, query, category]);

  if (error) {
    return (
      <p className="bg-[#f8e8e8] px-3.5 py-3 leading-relaxed text-fail">{error}</p>
    );
  }

  if (!catalog) {
    return <p className="text-muted">Loading the SANS policy library…</p>;
  }

  if (catalog.policies.length === 0) {
    return (
      <p className="leading-relaxed text-muted">
        No policies yet. Run <code className="font-mono text-sm">make scrape</code>{" "}
        to download the official SANS / CRF templates.
      </p>
    );
  }

  return (
    <div className="grid gap-6">
      <section className="grid gap-3 sm:grid-cols-3">
        <Stat
          label="Policies"
          value={String(catalog.policies.length)}
          hint={catalog.showing_text || `${catalog.listed} of ${catalog.total}`}
        />
        <Stat
          label="PDFs on disk"
          value={String(availablePdfs)}
          hint={`${catalog.policies.length - availablePdfs} missing`}
        />
        <Stat
          label="Last scrape"
          value={catalog.scraped_at ? catalog.scraped_at.slice(0, 10) : "—"}
          hint={catalog.scraped_at || "Not scraped yet"}
        />
      </section>

      <section className="rounded-sm border border-line bg-paper p-5">
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Library
        </p>
        <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
          By category
        </h2>
        <ul className="mt-4 grid list-none gap-2.5 p-0">
          {categories.map((item) => (
            <li key={item.name} className="grid grid-cols-[minmax(0,11rem)_1fr_2rem] items-center gap-3">
              <span className="truncate text-sm text-muted">{item.name}</span>
              <span className="h-2.5 overflow-hidden rounded-sm bg-sand">
                <span
                  className="block h-full bg-cardinal"
                  style={{ width: `${(item.count / maxCount) * 100}%` }}
                />
              </span>
              <span className="text-right text-sm font-semibold">{item.count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <label className="grid gap-1.5 text-sm font-semibold">
          Search
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Title, category, or summary"
            className="border border-line bg-[#fffdf8] px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-semibold">
          Category
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="border border-line bg-[#fffdf8] px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
          >
            <option value="all">All categories</option>
            {categories.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <p className="text-sm text-muted">
        Showing {filtered.length} of {catalog.policies.length} policies.
      </p>

      <ol className="grid list-none gap-4 p-0 md:grid-cols-2">
        {filtered.map((policy) => (
          <PolicyCard key={policy.slug} policy={policy} />
        ))}
      </ol>
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-sm border border-line bg-paper px-4 py-4">
      <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
        {label}
      </p>
      <p className="mt-1 font-serif text-4xl font-semibold leading-none">{value}</p>
      <p className="mt-2 text-sm text-muted">{hint}</p>
    </div>
  );
}

function PolicyCard({ policy }: { policy: PolicyRecord }) {
  return (
    <li className="grid gap-3 rounded-sm border border-line bg-paper p-5">
      <div>
        <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
          {policy.category || "Uncategorized"}
        </p>
        <h3 className="mt-1 font-serif text-xl font-semibold leading-tight tracking-tight">
          {policy.title}
        </h3>
        <p className="mt-1 text-sm text-muted">
          Published {formatDate(policy.published_on)}
          {policy.pdf_bytes ? ` · ${formatBytes(policy.pdf_bytes)}` : ""}
        </p>
      </div>
      {policy.summary ? (
        <p className="text-[0.95rem] leading-relaxed text-muted">{policy.summary}</p>
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
        >
          Source URL
        </a>
        {policy.pdf_path ? (
          <a
            href={policyPdfUrl(policy.slug)}
            target="_blank"
            rel="noreferrer"
            className="text-cardinal underline-offset-2 hover:underline"
          >
            Open PDF
          </a>
        ) : (
          <span className="text-muted">PDF unavailable</span>
        )}
      </div>
    </li>
  );
}
