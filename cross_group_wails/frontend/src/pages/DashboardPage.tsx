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

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[310px_minmax(0,1fr)_290px]">
        <ConfigPanel />

        <div className="animate-fade-up flex min-h-0 flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as "members" | "progress")}
            className="flex min-h-0 flex-1 flex-col"
          >
            <TabsList className="mb-4 w-full justify-start bg-transparent">
              <TabsTrigger value="members">成员列表</TabsTrigger>
              <TabsTrigger value="progress">邀请进度</TabsTrigger>
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

      <div className="grid shrink-0 grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr_1fr] h-[min(280px,30vh)]">
        <LogPanel />
        <RateLimitPanel />
        <FailedPanel />
      </div>
    </div>
  );
}
