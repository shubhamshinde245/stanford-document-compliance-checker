import { PoliciesDashboard } from "@/components/policies-dashboard";

export default function PoliciesPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10">
      <header className="mb-8 border-b border-line pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Standards library
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          SANS policy templates
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          Official CRF / SANS cybersecurity policy templates, scraped from the
          public library with source URL, published date, and a local PDF for
          each document. Dates are checked daily at 8:00 AM Pacific unless you
          reschedule that job here.
        </p>
      </header>
      <main>
        <PoliciesDashboard />
      </main>
    </div>
  );
}
