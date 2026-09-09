"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Checker", description: "Upload a document" },
  { href: "/policies", label: "Policies", description: "SANS library" },
] as const;

type AppSidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={`flex shrink-0 flex-col border-r border-line bg-paper/90 pb-16 transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div
        className={`flex items-start border-b border-line ${
          collapsed ? "flex-col gap-2 px-2 py-3" : "gap-2 px-3 py-4"
        }`}
      >
        {!collapsed ? (
          <div className="min-w-0 flex-1">
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-cardinal">
              Stanford
            </p>
            <p className="mt-1 font-serif text-lg font-semibold leading-tight tracking-tight">
              Compliance
            </p>
          </div>
        ) : (
          <span className="mx-auto font-serif text-lg font-semibold text-cardinal">
            S
          </span>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="cursor-pointer rounded-sm px-2 py-1 text-sm font-semibold text-muted hover:bg-sand hover:text-ink"
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-2" aria-label="Primary">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              className={`rounded-sm px-3 py-2.5 no-underline transition-colors ${
                active
                  ? "bg-cardinal/10 text-cardinal"
                  : "text-ink hover:bg-sand"
              } ${collapsed ? "text-center" : ""}`}
            >
              <span className="block text-sm font-semibold">
                {collapsed ? item.label.slice(0, 1) : item.label}
              </span>
              {!collapsed ? (
                <span className="mt-0.5 block text-xs text-muted">
                  {item.description}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
