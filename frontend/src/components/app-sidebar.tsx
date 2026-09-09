"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    href: "/",
    label: "Checker",
    description: "Upload a document",
    icon: CheckerIcon,
  },
  {
    href: "/policies",
    label: "Policies",
    description: "SANS library",
    icon: PoliciesIcon,
  },
] as const;

type AppSidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={`flex h-full shrink-0 flex-col overflow-hidden rounded-shell bg-[#8C1515] pb-6 text-white transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
      style={{ backgroundColor: "#8C1515" }}
    >
      <div
        className={`flex items-start ${
          collapsed ? "flex-col gap-2 px-2 py-3" : "gap-2 px-4 py-5"
        }`}
      >
        {!collapsed ? (
          <div className="min-w-0 flex-1">
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-white/70">
              Stanford
            </p>
            <p className="mt-1 font-serif text-lg font-semibold leading-tight tracking-tight">
              Compliance
            </p>
          </div>
        ) : (
          <span className="mx-auto flex h-9 w-9 items-center justify-center rounded-t-[1.15rem] rounded-b-[0.4rem] bg-white font-serif text-lg font-semibold text-cardinal">
            S
          </span>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="cursor-pointer rounded-control px-2 py-1 text-sm font-semibold text-white/75 hover:bg-white/10 hover:text-white"
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2" aria-label="Primary">
        {NAV.map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            description={item.description}
            icon={item.icon}
            collapsed={collapsed}
            active={
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`)
            }
          />
        ))}
      </nav>
      <div className="mt-auto px-2 pt-3">
        <NavLink
          href="/settings"
          label="Settings"
          description="Models and effort"
          icon={SettingsIcon}
          collapsed={collapsed}
          active={pathname === "/settings" || pathname.startsWith("/settings/")}
        />
      </div>
    </aside>
  );
}

function NavLink({
  href,
  label,
  description,
  icon: Icon,
  collapsed,
  active,
}: {
  href: string;
  label: string;
  description: string;
  icon: (props: { className?: string }) => ReactNode;
  collapsed: boolean;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      title={label}
      className={`flex items-center gap-3 no-underline transition-colors ${
        collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
      } rounded-control ${
        active
          ? "bg-white/15 text-white"
          : "text-white/80 hover:bg-white/10 hover:text-white"
      }`}
    >
      <Icon className="size-4 shrink-0" />
      {!collapsed ? (
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{label}</span>
          <span className="mt-0.5 block text-xs text-white/65">
            {description}
          </span>
        </span>
      ) : (
        <span className="sr-only">{label}</span>
      )}
    </Link>
  );
}

function CheckerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 4.5h6.2L18.5 9v10.5A1.5 1.5 0 0 1 17 21H8a1.5 1.5 0 0 1-1.5-1.5V6A1.5 1.5 0 0 1 8 4.5Z" />
      <path d="M14.2 4.5V9h4.3" />
      <path d="M8.8 13.2 10.6 15l3.6-4" />
    </svg>
  );
}

function PoliciesIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6.5 5.5h11A1.5 1.5 0 0 1 19 7v12.5H7.5A2.5 2.5 0 0 1 5 17V7a1.5 1.5 0 0 1 1.5-1.5Z" />
      <path d="M5 17a2.5 2.5 0 0 1 2.5-2.5H19" />
      <path d="M9 9h6M9 12.5h4" />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3.1" />
      <path d="M12 3.6v1.8M12 18.6v1.8M4.9 6.5l1.3 1.3M17.8 16.2l1.3 1.3M3.6 12h1.8M18.6 12h1.8M4.9 17.5l1.3-1.3M17.8 7.8l1.3-1.3" />
    </svg>
  );
}
