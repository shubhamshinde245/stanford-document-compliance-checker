"use client";

import { useEffect, useState } from "react";

import {
  AUDIENCE_LABEL,
  AUDIENCE_STORAGE_KEY,
  HOW_IT_WORKS,
  parseAudience,
  type Audience,
} from "@/lib/how-it-works-copy";

const CARD = "rounded-card border border-line/80 bg-paper p-5 shadow-card";

export function HowItWorks() {
  const [audience, setAudience] = useState<Audience>("stakeholder");

  useEffect(() => {
    setAudience(parseAudience(window.localStorage.getItem(AUDIENCE_STORAGE_KEY)));
  }, []);

  function choose(next: Audience) {
    setAudience(next);
    window.localStorage.setItem(AUDIENCE_STORAGE_KEY, next);
  }

  const copy = HOW_IT_WORKS[audience];

  return (
    <section className={`${CARD} grid gap-6`} aria-labelledby="how-it-works-title">
      <div className="grid gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 max-w-2xl">
            <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
              {copy.kicker}
            </p>
            <h2
              id="how-it-works-title"
              className="font-serif text-[1.55rem] font-semibold tracking-tight"
            >
              {copy.title}
            </h2>
          </div>
          <div
            className="flex shrink-0 flex-wrap gap-2"
            role="group"
            aria-label="Choose a reading level"
          >
            {(["stakeholder", "technical"] as const).map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={audience === id}
                onClick={() => choose(id)}
                className={`cursor-pointer rounded-pill px-3 py-1.5 text-sm font-semibold ${
                  audience === id
                    ? "bg-cardinal text-paper"
                    : "border border-line bg-paper text-ink hover:border-ink"
                }`}
              >
                {AUDIENCE_LABEL[id]}
              </button>
            ))}
          </div>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-muted">{copy.intro}</p>
      </div>

      <div>
        <p className="mb-2 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          {copy.flowLabel}
        </p>
        <ol className="flex list-none flex-wrap items-center gap-2 p-0">
          {copy.flowSteps.map((step, index) => (
            <li key={step.label} className="flex items-center gap-2">
              {index > 0 ? (
                <span aria-hidden="true" className="text-muted">
                  →
                </span>
              ) : null}
              <span className="rounded-pill border border-line bg-sand/60 px-3 py-1.5 text-sm font-semibold">
                {step.label}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="grid gap-5">
        {copy.sections.map((section) => (
          <article key={section.id} className="grid gap-2">
            <h3 className="font-serif text-[1.2rem] font-semibold tracking-tight">
              {section.title}
            </h3>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph} className="text-sm leading-relaxed text-muted">
                {paragraph}
              </p>
            ))}
            {section.bullets ? (
              <ul className="grid list-disc gap-1.5 pl-5 text-sm leading-relaxed text-muted">
                {section.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            ) : null}
            {section.formula ? (
              <pre className="overflow-auto rounded-control border border-line bg-sand/60 px-3.5 py-3 font-mono text-xs leading-relaxed">
                {section.formula}
              </pre>
            ) : null}
          </article>
        ))}
      </div>

      <div className="grid gap-3">
        <div>
          <h3 className="font-serif text-[1.2rem] font-semibold tracking-tight">
            {copy.exampleTitle}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            {copy.exampleCaption}
          </p>
        </div>
        <div className="overflow-x-auto rounded-control border border-line">
          <table className="min-w-full border-collapse text-left text-sm">
            <caption className="sr-only">
              Match scores for three example documents
            </caption>
            <thead className="bg-sand/60">
              <tr>
                <th className="px-3 py-2 font-semibold">Document</th>
                <th className="px-3 py-2 font-semibold">Top</th>
                <th className="px-3 py-2 font-semibold">Runner-up</th>
                <th className="px-3 py-2 font-semibold">Lead</th>
                <th className="px-3 py-2 font-semibold">Gate</th>
                <th className="px-3 py-2 font-semibold">Then</th>
              </tr>
            </thead>
            <tbody>
              {copy.exampleRows.map((row) => (
                <tr key={row.document} className="border-t border-line">
                  <td className="px-3 py-2">{row.document}</td>
                  <td className="px-3 py-2 font-mono">{row.top}</td>
                  <td className="px-3 py-2 font-mono">{row.runnerUp}</td>
                  <td className="px-3 py-2 font-mono">{row.lead}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-pill px-2 py-0.5 text-xs font-semibold ${
                        row.gate === "match"
                          ? "bg-pass/15 text-pass"
                          : "bg-warn/15 text-warn"
                      }`}
                    >
                      {row.gate === "match" ? "match" : "no-match"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted">{row.then}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-relaxed text-muted">{copy.exampleNote}</p>
      </div>
    </section>
  );
}
