import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInviteStore } from "@/store/useInviteStore";
import { BatchProgressCard } from "@/components/dashboard/BatchProgressCard";
import { ConfigPanel } from "@/components/dashboard/ConfigPanel";
import { FailedPanel } from "@/components/dashboard/FailedPanel";
import { InviteProgressTab } from "@/components/dashboard/InviteProgressTab";
import { LogPanel } from "@/components/dashboard/LogPanel";
import { MemberTable } from "@/components/dashboard/MemberTable";
import { ProgressPanel } from "@/components/dashboard/ProgressPanel";
import { RateLimitPanel } from "@/components/dashboard/RateLimitPanel";
import { SummaryCards } from "@/components/dashboard/SummaryCards";

export function DashboardPage() {
  const activeTab = useInviteStore((s) => s.activeTab);
  const setActiveTab = useInviteStore((s) => s.setActiveTab);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-hidden">
      <SummaryCards />

      <div className="grid min-h-0 flex-1 grid-cols-[310px_minmax(0,1fr)_290px] gap-4 overflow-hidden">
        <ConfigPanel />

        <div className="animate-fade-up flex min-h-0 flex-col overflow-hidden rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as "members" | "progress")}
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
          >
            <TabsList className="mb-4 w-full shrink-0 justify-start bg-transparent">
              <TabsTrigger value="members">成员列表</TabsTrigger>
              <TabsTrigger value="progress">邀请进度</TabsTrigger>
            </TabsList>
            <TabsContent value="members" className="mt-0 min-h-0 flex-1 overflow-hidden data-[state=inactive]:hidden">
              <MemberTable />
            </TabsContent>
            <TabsContent value="progress" className="mt-0 min-h-0 flex-1 overflow-hidden data-[state=inactive]:hidden">
              <InviteProgressTab />
            </TabsContent>
          </Tabs>
        </div>

        <div className="flex min-h-0 flex-col gap-4 overflow-auto">
          <ProgressPanel />
          <BatchProgressCard />
        </div>
      </div>

      <div className="grid h-[220px] shrink-0 grid-cols-[2fr_1fr_1fr] gap-4 overflow-hidden">
        <LogPanel />
        <RateLimitPanel />
        <FailedPanel />
      </div>
    </div>
  );
}
