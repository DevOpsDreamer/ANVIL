"use client";

export function AIReasoning() {
  return (
    <div className="col-span-12 lg:col-span-4 space-y-4">
      <h3 className="font-mono text-xs text-on-surface-variant uppercase tracking-widest">
        AI Reasoning Core
      </h3>

      <div className="glass-panel p-5 rounded-xl space-y-4">
        {/* Root Cause */}
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded bg-primary/20 flex items-center justify-center text-primary flex-shrink-0">
            <span className="material-symbols-outlined text-[18px]">psychology</span>
          </div>
          <div>
            <p className="font-mono text-[11px] text-primary uppercase tracking-widest mb-1">
              Root Cause Analysis
            </p>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              The vulnerability stems from improper sanitization of user input
              within the legacy authentication controller. Mitigation requires
              parameterization of SQL queries.
            </p>
          </div>
        </div>

        <div className="h-px bg-glass-border" />

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest mb-2">
              Risk Level
            </p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-surface-container rounded-full overflow-hidden">
                <div className="h-full bg-error w-[90%] rounded-full" />
              </div>
              <span className="text-xs font-mono text-error font-bold">9/10</span>
            </div>
          </div>
          <div>
            <p className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest mb-2">
              Verification
            </p>
            <div className="flex items-center gap-2">
              <span
                className="material-symbols-outlined text-secondary text-[18px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-xs font-mono text-secondary font-bold">COMPLETE</span>
            </div>
          </div>
        </div>

        <div className="h-px bg-glass-border" />

        {/* Exploit Chain Steps */}
        <div>
          <p className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest mb-3">
            Exploit Chain
          </p>
          <ol className="space-y-2">
            {[
              { step: "01", label: "Recon scan via port 8080", done: true },
              { step: "02", label: "Inject payload /v1/user/auth", done: true },
              { step: "03", label: "RCE achieved (sandbox container)", done: true },
              { step: "04", label: "Patch & PR generation", done: false, active: true },
            ].map((s) => (
              <li key={s.step} className="flex items-center gap-3">
                <span
                  className={`font-mono text-[10px] w-5 ${
                    s.done
                      ? "text-secondary"
                      : s.active
                      ? "text-primary animate-pulse"
                      : "text-on-surface-variant/30"
                  }`}
                >
                  {s.step}
                </span>
                <span
                  className={`text-xs ${
                    s.done
                      ? "text-on-surface"
                      : s.active
                      ? "text-primary font-semibold"
                      : "text-on-surface-variant/30"
                  }`}
                >
                  {s.label}
                </span>
                {s.done && (
                  <span
                    className="material-symbols-outlined text-secondary text-[14px] ml-auto"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    check_circle
                  </span>
                )}
                {s.active && (
                  <span className="material-symbols-outlined text-primary text-[14px] ml-auto animate-spin">
                    sync
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
