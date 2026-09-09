"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";

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
    <div className="flex min-h-full">
      <AppSidebar collapsed={collapsed} onToggle={onToggle} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
