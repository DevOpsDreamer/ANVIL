import { Sidebar } from "@/components/ui/Sidebar";
import { TopNav } from "@/components/ui/TopNav";
import { HeroSection } from "@/components/dashboard/HeroSection";
import { AgentLogs } from "@/components/dashboard/AgentLogs";
import { AutomatedPatching } from "@/components/dashboard/AutomatedPatching";
import { AIReasoning } from "@/components/dashboard/AIReasoning";
import { ObservabilityPanels } from "@/components/dashboard/ObservabilityPanels";
import { GlobalMap } from "@/components/dashboard/GlobalMap";

export default function DashboardPage() {
  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopNav />
        <main
          className="mt-16 overflow-y-auto h-full px-6 py-8 space-y-8"
          style={{
            background:
              "radial-gradient(ellipse at top right, rgba(233,254,255,0.05) 0%, transparent 50%)",
          }}
        >
          {/* Hero: Petri Net Visualization */}
          <HeroSection />

          {/* Bento: Logs + Code */}
          <section className="grid grid-cols-12 gap-6">
            <AgentLogs />
            <AutomatedPatching />
          </section>

          {/* AI Reasoning + Observability */}
          <section className="grid grid-cols-12 gap-6">
            <AIReasoning />
            <ObservabilityPanels />
          </section>

          {/* Global Map */}
          <GlobalMap />
        </main>
      </div>
    </>
  );
}
