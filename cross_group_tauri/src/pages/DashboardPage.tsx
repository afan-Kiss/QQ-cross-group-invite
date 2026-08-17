import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BootstrapOverlay } from "@/components/BootstrapOverlay";
import { usePollingStatus } from "@/hooks/usePollingStatus";
import { useBootstrap } from "@/hooks/useBootstrap";
import { useInviteStore } from "@/store/useInviteStore";
import { AppTitleBar } from "@/components/window/AppTitleBar";
import { BatchProgressCard } from "@/components/dashboard/BatchProgressCard";
import { ConfigPanel } from "@/components/dashboard/ConfigPanel";
import { FailedPanel } from "@/components/dashboard/FailedPanel";
import { InviteProgressTab } from "@/components/dashboard/InviteProgressTab";
import { LogPanel } from "@/components/dashboard/LogPanel";
import { MemberTable } from "@/components/dashboard/MemberTable";
import { ProgressPanel } from "@/components/dashboard/ProgressPanel";
import { RateLimitPanel } from "@/components/dashboard/RateLimitPanel";
import { StatusBar } from "@/components/dashboard/StatusBar";
import { SummaryCards } from "@/components/dashboard/SummaryCards";

export function DashboardPage() {
  useBootstrap();
  usePollingStatus();
  const activeTab = useInviteStore((s) => s.activeTab);
  const setActiveTab = useInviteStore((s) => s.setActiveTab);

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-[12px] border border-border bg-page-bg shadow-[0_8px_32px_rgba(28,36,24,0.08)]">
      <BootstrapOverlay />
      <AppTitleBar />

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden p-4">
        <SummaryCards />

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)_300px]">
          <ConfigPanel />

          <div className="animate-fade-up flex min-h-0 flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
            <Tabs
              value={activeTab}
              onValueChange={(v) => setActiveTab(v as "members" | "progress")}
              className="flex min-h-0 flex-1 flex-col"
            >
              <TabsList className="mb-4 w-full justify-start bg-transparent">
                <TabsTrigger value="members">��Ա�б�</TabsTrigger>
                <TabsTrigger value="progress">�������</TabsTrigger>
              </TabsList>
              <TabsContent value="members" className="min-h-0 flex-1">
                <MemberTable />
              </TabsContent>
              <TabsContent value="progress" className="min-h-0 flex-1">
                <InviteProgressTab />
              </TabsContent>
            </Tabs>
          </div>

          <div className="flex min-h-0 flex-col gap-4">
            <ProgressPanel />
            <BatchProgressCard />
          </div>
        </div>

        <div className="grid shrink-0 grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1fr]">
          <LogPanel />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <RateLimitPanel />
            <FailedPanel />
          </div>
        </div>
      </div>

      <StatusBar />
    </div>
  );
}
