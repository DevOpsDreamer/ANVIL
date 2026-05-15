"use client";

import Link from "next/link";

export function TopNav() {
  return (
    <header className="fixed top-0 right-0 left-0 md:left-64 z-50 h-16 bg-surface-container/50 backdrop-blur-xl border-b border-glass-border shadow-2xl flex justify-between items-center px-gutter">
      {/* Left */}
      <div className="flex items-center gap-8">
        <span className="font-mono text-xs tracking-widest text-primary uppercase">
          Omium
        </span>
        <nav className="hidden sm:flex gap-6">
          <Link
            href="/"
            className="text-base text-primary font-bold border-b-2 border-primary py-5"
          >
            Workflow Status
          </Link>
        </nav>
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        <button
          title="Sensors"
          className="text-on-surface-variant hover:text-primary transition-all"
        >
          <span className="material-symbols-outlined">sensors</span>
        </button>
        <button
          title="Tethering"
          className="text-on-surface-variant hover:text-primary transition-all"
        >
          <span className="material-symbols-outlined">wifi_tethering</span>
        </button>
        <button
          title="Notifications"
          className="text-on-surface-variant hover:text-primary transition-all relative"
        >
          <span className="material-symbols-outlined">notifications</span>
          <span className="absolute top-0 right-0 w-2 h-2 bg-secondary rounded-full" />
        </button>
        <div className="h-8 w-8 rounded-full overflow-hidden border border-glass-border bg-surface-container-high flex items-center justify-center">
          <span className="material-symbols-outlined text-sm text-on-surface-variant">person</span>
        </div>
      </div>
    </header>
  );
}
