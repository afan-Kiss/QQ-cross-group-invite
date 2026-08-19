import { Progress } from "@/components/ui/progress";
import { formatNumber, formatPercent } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

export function ProgressPanel() {
  const stats = useInviteStore((s) => s.stats);
  const inviting = useInviteStore((s) => s.inviting);
  const percent =
    stats.total > 0 ? Number(((stats.completed / stats.total) * 100).toFixed(2)) : 0;

  return (
    <div className="animate-fade-up rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold text-[#2f352d]">总体进度</h3>
      <div className="mb-2 flex items-end justify-between">
        <div className="text-[28px] font-semibold text-primary">{percent.toFixed(2)}%</div>
        <div className="text-[13px] text-muted-foreground">
          {formatNumber(stats.completed)} / {formatNumber(stats.total)}
        </div>
      </div>
      <Progress value={percent} className="mb-4 h-3" />
      <div className="grid grid-cols-2 gap-2 text-[13px] sm:grid-cols-3 lg:grid-cols-5">
        <div>成功 <span className="font-medium text-primary">{stats.success}</span></div>
        <div>频繁 <span className="font-medium text-warning">{stats.rate_limited}</span></div>
        <div>失败 <span className="font-medium text-danger">{stats.failed}</span></div>
        <div>等待 <span className="font-medium">{stats.waiting}</span></div>
        <div>已取消 <span className="font-medium">{stats.cancelled}</span></div>
      </div>
      <p className="mt-3 text-[12px] text-muted-foreground">
        {inviting ? stats.message || "邀请运行中" : stats.message || "空闲"}
      </p>
      <p className="mt-1 text-[12px] text-muted-foreground">
        完成率 {formatPercent(stats.completed, stats.total)}
      </p>
    </div>
  );
}
