"use client";

export function AutomatedPatching() {
  return (
    <div className="col-span-12 lg:col-span-7 flex flex-col h-[500px]">
      {/* Header */}
      <div className="p-4 bg-surface-container-high rounded-t-xl border-t border-x border-glass-border flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[18px]">code_blocks</span>
          <span className="font-mono text-xs font-bold text-primary tracking-widest uppercase">
            Automated Patching
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded font-mono">
            auth_controller.ts
          </span>
          <span className="material-symbols-outlined text-xs text-on-surface-variant">open_in_new</span>
        </div>
      </div>

      {/* Code Panel */}
      <div className="flex-1 glass-panel border-t-0 flex flex-col rounded-b-xl overflow-hidden">
        <div className="flex-1 grid grid-cols-2 overflow-hidden">
          {/* Vulnerable Code */}
          <div className="border-r border-glass-border p-4 font-mono text-xs bg-error-container/5 overflow-y-auto">
            <div className="text-on-surface-variant mb-4 font-mono opacity-50 text-[10px] uppercase tracking-widest">
              Vulnerable (Red)
            </div>
            <div className="space-y-1">
              <div className="text-on-surface-variant/40 whitespace-pre">{"24 | const query = `SELECT * FROM users"}</div>
              <div className="text-on-surface-variant/40 whitespace-pre">{"25 |   WHERE email = '${req.body.email}'"}</div>
              <div className="flex bg-error/20 text-error rounded-sm px-1 py-0.5 whitespace-pre">
                {"26 |   AND password = '${req.body.password}'`;"}
              </div>
              <div className="text-on-surface-variant/40 whitespace-pre">{"27 | const result = await db.execute(query);"}</div>
            </div>
          </div>

          {/* AI Patch */}
          <div className="p-4 font-mono text-xs bg-secondary-container/5 overflow-y-auto">
            <div className="text-on-surface-variant mb-4 font-mono opacity-50 text-[10px] uppercase tracking-widest">
              AI-Generated Patch (Green)
            </div>
            <div className="space-y-1">
              <div className="text-on-surface-variant/40 whitespace-pre">{"24 | const query = `SELECT * FROM users"}</div>
              <div className="text-on-surface-variant/40 whitespace-pre">{"25 |   WHERE email = ? AND password = ?`;"}</div>
              <div className="flex bg-secondary/20 text-secondary rounded-sm px-1 py-0.5 whitespace-pre">
                {"26 | const result = await db.execute(query,"}
              </div>
              <div className="flex bg-secondary/20 text-secondary rounded-sm px-1 py-0.5 whitespace-pre">
                {"27 |   [req.body.email, req.body.password]);"}
              </div>
            </div>
          </div>
        </div>

        {/* Metrics Footer */}
        <div className="p-4 border-t border-glass-border bg-surface-container-low flex justify-between items-center flex-shrink-0">
          <div className="flex gap-6">
            <div>
              <p className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">Confidence</p>
              <p className="text-secondary font-bold text-lg">98.4%</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">Severity</p>
              <p className="text-error font-bold text-lg">CRITICAL</p>
            </div>
          </div>
          <div className="flex gap-3">
            <button className="btn-outline text-[10px]">OPEN GITHUB PR</button>
            <button className="btn-primary text-[10px]">
              APPROVE &amp; MERGE
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
