import { ReportsDashboard } from "@/components/reports-dashboard";

export default function ReportsPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8">
      <header className="mb-8 pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Archive
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          Saved reports
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          Every completed requirement evaluation is stored on this machine.
          Open a run to review verdicts, quotes, and alignment without
          uploading the document again.
        </p>
      </header>
      <main>
        <ReportsDashboard />
      </main>
    </div>
  );
}
