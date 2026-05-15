"use client";

const LOG_ENTRIES = [
  {
    time: "14:20:01",
    tag: "[SYSTEM]",
    tagColor: "text-secondary",
    message: (
      <>
        Webhook received from{" "}
        <span className="text-primary-fixed-dim font-mono">GitHub::PROD_API</span>
      </>
    ),
  },
  {
    time: "14:20:05",
    tag: "[SCANNER]",
    tagColor: "text-secondary",
    message: "Initializing codebase heuristic traversal...",
  },
  {
    time: "14:21:12",
    tag: "[VULNERABILITY]",
    tagColor: "text-error font-bold",
    message: (
      <span className="text-error">
        Critical: SQL Injection path detected in{" "}
        <code className="bg-error/10 px-1 rounded">/v1/user/auth</code>
      </span>
    ),
    highlight: false,
  },
  {
    time: "14:22:45",
    tag: "[EXPLOIT]",
    tagColor: "text-primary",
    message: "Attempting automated sandbox breach...",
  },
  {
    time: "14:23:10",
    tag: "[SUCCESS]",
    tagColor: "text-error",
    message: "Exploit successful. Remote Code Execution achieved in isolated container.",
    highlight: true,
  },
  {
    time: "14:25:01",
    tag: "[PATCH]",
    tagColor: "text-secondary",
    message: "Generating semantic patch for remediation...",
  },
  {
    time: "14:26:30",
    tag: "[GIT]",
    tagColor: "text-secondary",
    message: (
      <>
        Drafting Pull Request to{" "}
        <span className="text-primary font-mono">main</span> branch...
      </>
    ),
  },
];

export function AgentLogs() {
  return (
    <div className="col-span-12 lg:col-span-5 flex flex-col h-[500px]">
      {/* Header */}
      <div className="p-4 bg-surface-container-high rounded-t-xl border-t border-x border-glass-border flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[18px]">terminal</span>
          <span className="font-mono text-xs font-bold text-primary tracking-widest uppercase">
            Agent Execution Logs
          </span>
        </div>
        <span className="text-[10px] text-on-surface-variant font-mono animate-pulse">
          STREAMING...
        </span>
      </div>

      {/* Log Body */}
      <div className="flex-1 glass-panel border-t-0 p-6 overflow-hidden relative rounded-b-xl">
        <div className="font-mono text-sm space-y-3">
          {LOG_ENTRIES.map((entry, i) => (
            <div
              key={i}
              className={`flex gap-3 text-xs ${
                entry.highlight
                  ? "p-2 bg-error-container/20 border-l-2 border-error rounded-sm -mx-2 pl-3"
                  : ""
              }`}
            >
              <span className="text-on-surface-variant/40 flex-shrink-0 w-16">
                {entry.time}
              </span>
              <span className={`flex-shrink-0 ${entry.tagColor}`}>{entry.tag}</span>
              <span className="text-on-surface leading-relaxed">{entry.message}</span>
            </div>
          ))}
        </div>

        {/* Fade overlay */}
        <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-surface-deep to-transparent pointer-events-none" />
      </div>
    </div>
  );
}
