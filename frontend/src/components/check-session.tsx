"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { CheckResponse, PolicyMatch } from "@/lib/types";

type CheckSessionValue = {
  report: CheckResponse | null;
  selectedSlug: string | null;
  evaluating: boolean;
  topMatches: PolicyMatch[];
  setReport: (report: CheckResponse | null) => void;
  setSelectedSlug: (slug: string) => void;
  setEvaluating: (value: boolean) => void;
};

const CheckSessionContext = createContext<CheckSessionValue | null>(null);

export function CheckSessionProvider({ children }: { children: ReactNode }) {
  const [report, setReportState] = useState<CheckResponse | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);

  const setReport = useCallback((next: CheckResponse | null) => {
    setReportState(next);
    setSelectedSlug(next?.matches[0]?.slug ?? null);
    setEvaluating(false);
  }, []);

  const value = useMemo<CheckSessionValue>(
    () => ({
      report,
      selectedSlug,
      evaluating,
      topMatches: report?.matches.slice(0, 5) ?? [],
      setReport,
      setSelectedSlug,
      setEvaluating,
    }),
    [report, selectedSlug, evaluating, setReport],
  );

  return (
    <CheckSessionContext.Provider value={value}>
      {children}
    </CheckSessionContext.Provider>
  );
}

export function useCheckSession(): CheckSessionValue {
  const value = useContext(CheckSessionContext);
  if (!value) {
    throw new Error("useCheckSession must be used within CheckSessionProvider.");
  }
  return value;
}
