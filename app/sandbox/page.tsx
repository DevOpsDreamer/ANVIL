import { Sidebar } from "@/components/ui/Sidebar";
import { TopNav } from "@/components/ui/TopNav";

export default function SandboxPage() {
  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopNav />
        <main className="mt-16 overflow-y-auto h-full px-6 py-8 flex items-center justify-center">
          <div className="text-center space-y-4">
            <span className="material-symbols-outlined text-6xl text-on-surface-variant opacity-30">biotech</span>
            <h1 className="text-2xl font-bold text-primary">Sandbox</h1>
            <p className="text-on-surface-variant">Coming soon — isolated exploit sandbox environment.</p>
          </div>
        </main>
      </div>
    </>
  );
}
