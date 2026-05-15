import { Sidebar } from "@/components/ui/Sidebar";
import { TopNav } from "@/components/ui/TopNav";

function StubPage({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopNav />
        <main className="mt-16 overflow-y-auto h-full px-6 py-8 flex items-center justify-center">
          <div className="text-center space-y-4">
            <span className="material-symbols-outlined text-6xl text-on-surface-variant opacity-30">{icon}</span>
            <h1 className="text-2xl font-bold text-primary">{title}</h1>
            <p className="text-on-surface-variant">{desc}</p>
          </div>
        </main>
      </div>
    </>
  );
}

export default function AgentsPage() {
  return <StubPage icon="smart_toy" title="Agents" desc="Coming soon — agent management panel." />;
}
