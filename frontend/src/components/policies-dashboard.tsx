"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { toast } from "react-toastify/unstyled";

import {
  fetchPolicies,
  fetchPolicySafeguards,
  fetchPolicySchedule,
  policyPdfUrl,
  runPolicyScrape,
  savePolicySchedule,
} from "@/lib/api";
import type {
  PolicyCatalog,
  PolicyRecord,
  PolicySafeguard,
  PolicySchedule,
} from "@/lib/types";

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

function formatPacific(iso: string | null): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function padTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
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
  const [schedule, setSchedule] = useState<PolicySchedule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [safeguardsPolicy, setSafeguardsPolicy] = useState<PolicyRecord | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    const toastId = toast.loading("Loading the SANS policy library…");
    Promise.all([fetchPolicies(), fetchPolicySchedule()])
      .then(([catalogData, scheduleData]) => {
        if (cancelled) return;
        setCatalog(catalogData);
        setSchedule(scheduleData);
        if (catalogData.policies.length === 0) {
          toast.update(toastId, {
            render:
              "No policies on disk yet. Check for updates or run make scrape.",
            type: "warning",
            isLoading: false,
            autoClose: 6000,
          });
          return;
        }
        toast.update(toastId, {
          render: `Loaded ${catalogData.policies.length} SANS policies.`,
          type: "success",
          isLoading: false,
          autoClose: 4000,
        });
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const message =
          caught instanceof Error ? caught.message : "Could not load policies.";
        setError(message);
        toast.update(toastId, {
          render: message,
          type: "error",
          isLoading: false,
          autoClose: 6000,
        });
      });
    return () => {
      cancelled = true;
      toast.dismiss(toastId);
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
      <p className="rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
        {error}
      </p>
    );
  }

  if (!catalog || !schedule) {
    return <p className="text-muted">Loading the SANS policy library…</p>;
  }

  return (
    <div className="grid gap-6">
      <RefreshSchedule
        schedule={schedule}
        onSchedule={setSchedule}
        onCatalog={setCatalog}
      />

      {catalog.policies.length === 0 ? (
        <p className="leading-relaxed text-muted">
          No policies yet. Use <strong>Check for updates now</strong> above, or run{" "}
          <code className="font-mono text-sm">make scrape</code>.
        </p>
      ) : (
        <>
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
              label="Last check"
              value={catalog.scraped_at ? catalog.scraped_at.slice(0, 10) : "—"}
              hint={
                catalog.last_check
                  ? `${catalog.last_check.updated} updated · ${catalog.last_check.unchanged} unchanged`
                  : catalog.scraped_at || "Not scraped yet"
              }
            />
          </section>

          <section className="rounded-card border border-line/80 bg-paper p-5 shadow-card">
            <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
              Library
            </p>
            <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
              By category
            </h2>
            <ul className="mt-4 grid list-none gap-2.5 p-0">
              {categories.map((item) => (
                <li
                  key={item.name}
                  className="grid grid-cols-[minmax(0,11rem)_1fr_2rem] items-center gap-3"
                >
                  <span className="truncate text-sm text-muted">{item.name}</span>
                  <span className="h-2.5 overflow-hidden rounded-pill bg-sand">
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
                className="rounded-control border border-line bg-paper px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
              />
            </label>
            <label className="grid gap-1.5 text-sm font-semibold">
              Category
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="rounded-control border border-line bg-paper px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
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
              <PolicyCard
                key={policy.slug}
                policy={policy}
                onViewSafeguards={setSafeguardsPolicy}
              />
            ))}
          </ol>
        </>
      )}

      {safeguardsPolicy ? (
        <SafeguardsDialog
          policy={safeguardsPolicy}
          onClose={() => setSafeguardsPolicy(null)}
        />
      ) : null}
    </div>
  );
}

function RefreshSchedule({
  schedule,
  onSchedule,
  onCatalog,
}: {
  schedule: PolicySchedule;
  onSchedule: (value: PolicySchedule) => void;
  onCatalog: (value: PolicyCatalog) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [enabled, setEnabled] = useState(schedule.enabled);
  const [time, setTime] = useState(padTime(schedule.hour, schedule.minute));
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [fault, setFault] = useState<string | null>(null);

  useEffect(() => {
    setEnabled(schedule.enabled);
    setTime(padTime(schedule.hour, schedule.minute));
  }, [schedule.enabled, schedule.hour, schedule.minute]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    const [hourText, minuteText] = time.split(":");
    const hour = Number(hourText);
    const minute = Number(minuteText);
    if (!Number.isInteger(hour) || !Number.isInteger(minute)) {
      const invalid = "Choose a valid time.";
      setFault(invalid);
      toast.warning(invalid);
      return;
    }
    setSaving(true);
    setFault(null);
    setMessage(null);
    const toastId = toast.loading("Saving the daily refresh schedule…");
    try {
      const next = await savePolicySchedule({ enabled, hour, minute });
      onSchedule(next);
      const saved = next.enabled
        ? `Saved. Next check ${formatPacific(next.next_run_at)} Pacific.`
        : "Saved. Daily refresh is off.";
      setMessage(saved);
      toast.update(toastId, {
        render: saved,
        type: "success",
        isLoading: false,
        autoClose: 4500,
      });
    } catch (caught: unknown) {
      const failed =
        caught instanceof Error ? caught.message : "Could not save schedule.";
      setFault(failed);
      toast.update(toastId, {
        render: failed,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setSaving(false);
    }
  }

  async function onCheckNow() {
    setChecking(true);
    setFault(null);
    setMessage(null);
    const toastId = toast.loading("Checking SANS for policy updates…");
    try {
      const catalog = await runPolicyScrape();
      onCatalog(catalog);
      const next = await fetchPolicySchedule();
      onSchedule(next);
      const check = catalog.last_check;
      const done = check
        ? `Checked. ${check.updated} updated, ${check.unchanged} unchanged, ${check.added} added.`
        : "Check finished.";
      setMessage(done);
      toast.update(toastId, {
        render: done,
        type: "success",
        isLoading: false,
        autoClose: 5000,
      });
    } catch (caught: unknown) {
      const failed =
        caught instanceof Error ? caught.message : "Refresh failed.";
      setFault(failed);
      toast.update(toastId, {
        render: failed,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="rounded-card border border-line/80 bg-paper p-5 shadow-card">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full cursor-pointer items-start justify-between gap-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
      >
        <div>
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Refresh
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Daily date check
          </h2>
        </div>
        <span className="mt-1 shrink-0 text-sm font-semibold text-muted">
          {expanded ? "Hide" : "Show"}
        </span>
      </button>

      {expanded ? (
        <>
      <p className="mt-2 max-w-2xl text-[0.95rem] leading-relaxed text-muted">
        Each day at this Pacific Time, the library listing is compared to stored
        published dates. PDFs are downloaded only when a date changed, a policy
        is new, or a file is missing.
      </p>

      <form
        className="mt-4 grid gap-4 sm:grid-cols-[auto_auto_1fr] sm:items-end"
        onSubmit={(event) => void onSave(event)}
      >
        <label className="grid gap-1.5 text-sm font-semibold">
          Time
          <input
            type="time"
            value={time}
            onChange={(event) => setTime(event.target.value)}
            className="rounded-control border border-line bg-paper px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal"
          />
        </label>
        <label className="flex items-center gap-2 pb-3 text-sm font-semibold">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            className="size-4 accent-cardinal"
          />
          Run daily
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={saving || checking}
            className="cursor-pointer rounded-control border border-line bg-transparent px-4 py-2.5 font-semibold hover:border-ink disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
          >
            {saving ? "Saving…" : "Save schedule"}
          </button>
          <button
            type="button"
            disabled={checking || saving}
            onClick={() => void onCheckNow()}
            className="cursor-pointer rounded-control bg-cardinal px-4 py-2.5 font-semibold text-paper hover:bg-cardinal-dark disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal"
          >
            {checking ? "Checking…" : "Check for updates now"}
          </button>
        </div>
      </form>

      <dl className="mt-4 grid gap-2 text-sm text-muted sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-ink">Timezone</dt>
          <dd>Pacific Time (America/Los_Angeles)</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Next run</dt>
          <dd>
            {schedule.enabled
              ? `${formatPacific(schedule.next_run_at)} Pacific`
              : "Disabled"}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Last run</dt>
          <dd>
            {schedule.last_run_at
              ? `${formatPacific(schedule.last_run_at)} Pacific`
              : "Not run yet"}
            {schedule.last_run_status ? ` · ${schedule.last_run_status}` : ""}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Last result</dt>
          <dd>{schedule.last_run_summary || "—"}</dd>
        </div>
      </dl>

      {message ? <p className="mt-3 text-sm text-pass">{message}</p> : null}
      {fault ? <p className="mt-3 text-sm text-fail">{fault}</p> : null}
        </>
      ) : null}
    </section>
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
    <div className="rounded-card border border-line/80 bg-paper px-4 py-4 shadow-card">
      <p className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-cardinal">
        {label}
      </p>
      <p className="mt-1 font-serif text-4xl font-semibold leading-none">{value}</p>
      <p className="mt-2 text-sm text-muted">{hint}</p>
    </div>
  );
}

function statusLabel(status: string | null): string | null {
  if (status === "updated") return "Updated";
  if (status === "added") return "New";
  return null;
}

function PolicyCard({
  policy,
  onViewSafeguards,
}: {
  policy: PolicyRecord;
  onViewSafeguards: (policy: PolicyRecord) => void;
}) {
  const badge = statusLabel(policy.refresh_status);
  return (
    <li className="grid gap-3 rounded-card border border-line/80 bg-paper p-5 shadow-card">
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
          onClick={() => toast.info(`Opening source for “${policy.title}”.`)}
        >
          Source URL
        </a>
        {policy.source_url || policy.pdf_path ? (
          <a
            href={policy.source_url || policyPdfUrl(policy.slug)}
            target="_blank"
            rel="noreferrer"
            className="text-cardinal underline-offset-2 hover:underline"
            onClick={() =>
              toast.info(`Opening SANS page: ${policy.title}`)
            }
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
    </li>
  );
}

function SafeguardsDialog({
  policy,
  onClose,
}: {
  policy: PolicyRecord;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<PolicySafeguard[] | null>(null);
  const [fault, setFault] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setFault(null);
    fetchPolicySafeguards(policy.slug)
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
  }, [policy.slug]);

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
              {policy.title}
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
