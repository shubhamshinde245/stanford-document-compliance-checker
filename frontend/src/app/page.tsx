import { ComplianceChecker } from "@/components/compliance-checker";

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8">
      <header className="mb-8 pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Stanford University
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          Document Compliance Checker
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          Parse HTML with Beautiful Soup and flag gaps in language, headings,
          alternative text, identity, copyright, and accessibility contact.
        </p>
      </header>
      <main>
        <ComplianceChecker />
      </main>
    </div>
  );
}
