"use client";

const nodes = [
  { id: "NA-WEST", label: "NA-WEST: OPERATIONAL", status: "operational" },
  { id: "EU-CENTRAL", label: "EU-CENTRAL: OPERATIONAL", status: "operational" },
  { id: "AP-SOUTH", label: "AP-SOUTH: DEGRADED", status: "degraded" },
];

export function GlobalMap() {
  return (
    <section className="h-64 glass-panel rounded-xl overflow-hidden relative">
      {/* Dark world map SVG background */}
      <div className="absolute inset-0 opacity-15">
        <svg viewBox="0 0 1440 400" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
          <defs>
            <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#4edea3" stopOpacity="1" />
              <stop offset="100%" stopColor="#4edea3" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="nodeGlowRed" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ffb4ab" stopOpacity="1" />
              <stop offset="100%" stopColor="#ffb4ab" stopOpacity="0" />
            </radialGradient>
          </defs>
          {/* Simplified world outline shapes */}
          <path d="M120 120 Q 200 80 300 100 Q 350 90 400 110 Q 450 130 480 120 L 500 80 Q 540 60 580 90 Q 620 110 650 100 Q 700 80 720 100 L 720 200 Q 680 220 640 210 Q 600 200 560 220 Q 520 240 480 230 Q 440 220 400 240 Q 360 260 320 250 Q 280 240 240 260 Q 200 280 160 260 Q 130 240 120 200 Z" fill="#b9caca" opacity="0.3" />
          <path d="M760 90 Q 820 70 880 100 Q 940 130 960 120 Q 1000 100 1040 110 Q 1080 120 1100 140 Q 1120 160 1080 180 Q 1040 200 1000 190 Q 960 180 920 200 Q 880 220 840 210 Q 800 200 780 180 Q 760 160 760 130 Z" fill="#b9caca" opacity="0.3" />
          <path d="M200 280 Q 240 260 280 280 Q 310 300 300 340 Q 290 380 260 390 Q 230 400 210 380 Q 190 360 200 320 Z" fill="#b9caca" opacity="0.3" />
          <path d="M1100 160 Q 1160 140 1220 170 Q 1280 200 1300 240 Q 1320 280 1280 310 Q 1240 340 1200 330 Q 1160 320 1140 290 Q 1120 260 1110 220 Q 1100 190 1100 160 Z" fill="#b9caca" opacity="0.3" />
          
          {/* Connection lines */}
          <line x1="300" y1="150" x2="860" y2="120" stroke="#00dce5" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.4" />
          <line x1="860" y1="120" x2="1160" y2="220" stroke="#00dce5" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.3" />
          <line x1="300" y1="150" x2="1160" y2="220" stroke="#4edea3" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.2" />
        </svg>
      </div>

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-surface-deep via-surface-deep/50 to-transparent" />

      {/* Animated nodes overlay */}
      <div className="absolute inset-0">
        {/* NA-WEST node */}
        <div className="absolute" style={{ left: "20%", top: "38%" }}>
          <div className="w-3 h-3 rounded-full bg-secondary pulse-emerald" />
        </div>
        {/* EU-CENTRAL node */}
        <div className="absolute" style={{ left: "60%", top: "30%" }}>
          <div className="w-3 h-3 rounded-full bg-secondary pulse-emerald" />
        </div>
        {/* AP-SOUTH node */}
        <div className="absolute" style={{ left: "78%", top: "55%" }}>
          <div className="w-3 h-3 rounded-full bg-error animate-pulse" />
        </div>
      </div>

      {/* Bottom label */}
      <div className="absolute bottom-6 left-6">
        <h4 className="font-mono text-xs text-primary uppercase tracking-widest mb-2">
          Global Node Status
        </h4>
        <div className="flex flex-wrap gap-4">
          {nodes.map((node) => (
            <div key={node.id} className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  node.status === "degraded"
                    ? "bg-error animate-pulse"
                    : "bg-secondary"
                }`}
              />
              <span className="text-[10px] font-mono uppercase tracking-widest">
                {node.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top right label */}
      <div className="absolute top-4 right-4 text-right">
        <span className="text-[10px] font-mono text-on-surface-variant opacity-50 uppercase tracking-widest">
          Infrastructure Map v2.1
        </span>
      </div>
    </section>
  );
}
