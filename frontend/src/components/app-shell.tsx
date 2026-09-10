"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { CheckSessionProvider } from "@/components/check-session";
import { ToastProvider } from "@/components/toast-provider";

const STORAGE_KEY = "sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "1") {
      setCollapsed(true);
    }
  }, []);

  function onToggle() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <CheckSessionProvider>
    <div className="flex h-full gap-3 overflow-hidden p-3">
      <AppSidebar collapsed={collapsed} onToggle={onToggle} />
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto rounded-shell bg-paper/55">
        {children}
      </div>
      <ToastProvider />
    </div>
    </CheckSessionProvider>
  );
}
