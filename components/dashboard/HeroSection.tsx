"use client";

export function HeroSection() {
  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
      {/* Left: Text */}
      <div className="space-y-4">
        <div className="inline-flex items-center gap-2 bg-secondary/10 px-3 py-1 rounded-full border border-secondary/20">
          <span className="w-2 h-2 bg-secondary rounded-full pulse-emerald" />
          <span className="text-xs font-mono text-secondary uppercase tracking-widest">
            Live Autonomous Session
          </span>
        </div>
        <h2 className="text-5xl lg:text-6xl font-bold text-primary leading-none tracking-tight">
          Autonomous Security Orchestration
        </h2>
        <p className="text-on-surface-variant max-w-md leading-relaxed">
          Omium is currently executing a multi-stage exploit chain verification
          across production clusters. Observe AI reasoning and real-time
          patching in action.
        </p>
      </div>

      {/* Right: Petri Net Visualization */}
      <div className="h-[400px] glass-panel rounded-xl overflow-hidden relative w-full">
        <div className="absolute inset-0 p-8 flex items-center justify-center">
          <svg viewBox="0 0 800 300" className="w-full h-full">
            <defs>
              <linearGradient id="pathGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#4edea3" />
                <stop offset="100%" stopColor="#00dce5" />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Connection Lines */}
            <path
              d="M100 150 Q 175 80 250 100"
              fill="none"
              stroke="url(#pathGradient)"
              strokeWidth="1.5"
              strokeDasharray="8 4"
              opacity="0.5"
            />
            <path
              d="M250 100 Q 325 120 400 150"
              fill="none"
              stroke="url(#pathGradient)"
              strokeWidth="1.5"
              strokeDasharray="8 4"
              opacity="0.5"
            />
            <path
              d="M400 150 Q 475 175 550 200"
              fill="none"
              stroke="url(#pathGradient)"
              strokeWidth="2"
              strokeDasharray="8 4"
              opacity="0.8"
            />
            <path
              d="M550 200 Q 625 175 700 150"
              fill="none"
              stroke="#b9caca"
              strokeWidth="1"
              strokeDasharray="6 4"
              opacity="0.3"
            />

            {/* Recon Node */}
            <circle cx="100" cy="150" r="12" fill="#1d2026" stroke="#4edea3" strokeWidth="2" />
            <circle cx="100" cy="150" r="6" fill="#4edea3" opacity="0.4" />
            <text x="100" y="178" textAnchor="middle" fill="#4edea3" fontSize="10" fontFamily="JetBrains Mono" letterSpacing="0.05em">RECON</text>

            {/* Exploit Node */}
            <circle cx="250" cy="100" r="12" fill="#1d2026" stroke="#00dce5" strokeWidth="2" />
            <circle cx="250" cy="100" r="6" fill="#00dce5" opacity="0.4" />
            <text x="250" y="128" textAnchor="middle" fill="#00dce5" fontSize="10" fontFamily="JetBrains Mono" letterSpacing="0.05em">EXPLOIT</text>

            {/* Verify Node */}
            <circle cx="400" cy="150" r="12" fill="#1d2026" stroke="#4edea3" strokeWidth="2" />
            <circle cx="400" cy="150" r="6" fill="#4edea3" opacity="0.4" />
            <text x="400" y="178" textAnchor="middle" fill="#4edea3" fontSize="10" fontFamily="JetBrains Mono" letterSpacing="0.05em">VERIFY</text>

            {/* Patching Node (ACTIVE — glowing) */}
            <circle cx="550" cy="200" r="16" fill="#00dce5" filter="url(#glow)">
              <animate attributeName="r" values="14;18;14" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.8;1;0.8" dur="2s" repeatCount="indefinite" />
            </circle>
            <text x="550" y="228" textAnchor="middle" fill="#e9feff" fontSize="10" fontFamily="JetBrains Mono" fontWeight="600" letterSpacing="0.05em">PATCHING</text>

            {/* PR Node (Pending) */}
            <circle cx="700" cy="150" r="12" fill="#1d2026" stroke="#b9caca" strokeWidth="1.5" opacity="0.5" />
            <text x="700" y="178" textAnchor="middle" fill="#b9caca" fontSize="10" fontFamily="JetBrains Mono" letterSpacing="0.05em" opacity="0.5">PR</text>
          </svg>
        </div>

        {/* Overlay label */}
        <div className="absolute top-4 right-4 text-right">
          <div className="font-mono text-[10px] text-on-surface-variant opacity-50 uppercase tracking-widest">
            Agent Cluster
          </div>
          <div className="text-primary font-mono text-sm">OMEGA-7 // ACTIVE</div>
        </div>

        {/* Scan line animation */}
        <div className="scan-line-anim" />
      </div>
    </section>
  );
}
