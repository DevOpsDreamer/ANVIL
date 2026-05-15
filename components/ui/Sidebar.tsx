"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Mission Control", icon: "dashboard", fill: true },
  { href: "/workflows", label: "Workflows", icon: "account_tree" },
  { href: "/agents", label: "Agents", icon: "smart_toy" },
  { href: "/sandbox", label: "Sandbox", icon: "biotech" },
  { href: "/traces", label: "Traces", icon: "timeline" },
  { href: "/vulnerabilities", label: "Vulnerabilities", icon: "security" },
  { href: "/prs", label: "PRs", icon: "merge_type" },
  { href: "/metrics", label: "Metrics", icon: "monitoring" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 h-full pt-20 pb-2 bg-surface-container-low/40 backdrop-blur-2xl border-r border-glass-border sticky left-0 top-0 z-50 flex-shrink-0">
        <div className="px-6 mb-10">
          <h1 className="text-2xl font-bold text-primary tracking-tighter leading-none">Omium</h1>
          <p className="font-mono text-xs text-on-surface-variant opacity-60 tracking-widest uppercase mt-0.5">
            Mission Control
          </p>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={isActive ? "nav-link-active group" : "nav-link group"}
              >
                <span
                  className="material-symbols-outlined text-[20px] transition-transform group-hover:translate-x-0.5"
                  style={
                    isActive && item.fill
                      ? { fontVariationSettings: "'FILL' 1" }
                      : {}
                  }
                >
                  {item.icon}
                </span>
                <span className="font-mono text-xs tracking-widest uppercase">
                  {item.label}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-glass-border">
          <Link href="/settings" className="nav-link group">
            <span className="material-symbols-outlined text-[20px] group-hover:rotate-90 transition-transform duration-300">
              settings
            </span>
            <span className="font-mono text-xs tracking-widest uppercase">Settings</span>
          </Link>
        </div>
      </aside>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 w-full h-16 bg-surface-container/80 backdrop-blur-xl border-t border-glass-border flex justify-around items-center z-50">
        <Link href="/" className={pathname === "/" ? "text-primary flex flex-col items-center" : "text-on-surface-variant flex flex-col items-center"}>
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>dashboard</span>
          <span className="text-[10px] font-mono">Mission</span>
        </Link>
        <Link href="/workflows" className="text-on-surface-variant flex flex-col items-center">
          <span className="material-symbols-outlined">account_tree</span>
          <span className="text-[10px] font-mono">Flows</span>
        </Link>
        <div className="bg-primary p-3 rounded-full -mt-10 shadow-[0_0_20px_rgba(0,220,229,0.5)]">
          <span className="material-symbols-outlined text-surface-deep">bolt</span>
        </div>
        <Link href="/vulnerabilities" className="text-on-surface-variant flex flex-col items-center">
          <span className="material-symbols-outlined">security</span>
          <span className="text-[10px] font-mono">Vuln</span>
        </Link>
        <Link href="/settings" className="text-on-surface-variant flex flex-col items-center">
          <span className="material-symbols-outlined">settings</span>
          <span className="text-[10px] font-mono">Config</span>
        </Link>
      </nav>
    </>
  );
}
