"use client";

const metrics = [
  {
    label: "Trace Timeline",
    icon: "timeline",
    content: (
      <div className="h-8 flex items-end gap-0.5">
        {[60, 40, 90, 30, 100, 50, 40, 60].map((h, i) => (
          <div
            key={i}
            className={`flex-1 rounded-t-sm ${i === 4 ? "bg-primary/40" : "bg-secondary/40"}`}
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    ),
    value: "2.4ms avg",
    valueColor: "text-primary",
  },
  {
    label: "Execution Spans",
    icon: "data_usage",
    content: (
      <div className="space-y-2">
        <div className="h-1.5 bg-primary/20 w-full rounded-full overflow-hidden">
          <div className="h-full bg-primary w-[75%] rounded-full" />
        </div>
        <div className="h-1.5 bg-secondary/20 w-full rounded-full overflow-hidden">
          <div className="h-full bg-secondary w-[45%] rounded-full" />
        </div>
      </div>
    ),
    value: "114 Spans Active",
    valueColor: "text-on-surface",
  },
  {
    label: "Latency",
    icon: "speed",
    content: (
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold text-secondary">12ms</span>
        <span className="material-symbols-outlined text-secondary text-[18px]">trending_down</span>
      </div>
    ),
    value: "-4% from baseline",
    valueColor: "text-on-surface-variant",
  },
  {
    label: "Agent Queue",
    icon: "queue",
    content: (
      <div className="flex justify-between items-center">
        <span className="text-2xl font-bold text-primary">0</span>
        <div className="flex gap-1">
          <span className="w-2 h-2 rounded-full bg-secondary" />
          <span className="w-2 h-2 rounded-full bg-secondary opacity-50" />
          <span className="w-2 h-2 rounded-full bg-secondary opacity-20" />
        </div>
      </div>
    ),
    value: "Optimal Load",
    valueColor: "text-on-surface-variant",
  },
];

export function ObservabilityPanels() {
  return (
    <div className="col-span-12 lg:col-span-8">
      <h3 className="font-mono text-xs text-on-surface-variant uppercase tracking-widest mb-4">
        System Observability
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="glass-panel p-4 rounded-xl space-y-2 hover:border-primary/30 transition-colors duration-300">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-symbols-outlined text-on-surface-variant text-[16px]">{m.icon}</span>
              <p className="text-[10px] font-mono text-on-surface-variant uppercase tracking-widest">
                {m.label}
              </p>
            </div>
            {m.content}
            <p className={`text-xs font-mono ${m.valueColor} mt-2`}>{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
