import { HowItWorks } from "@/components/how-it-works";

export default function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8">
      <header className="mb-8 pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Design map
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          How it works
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          What happens after you run a compliance check, how embeddings are
          matched, and where the two percentages come from. Toggle between a
          stakeholder reading and an engineer reading.
        </p>
      </header>
      <main>
        <HowItWorks />
      </main>
    </div>
  );
}
