import { Progress } from "@/components/ui/progress";
import { formatNumber, formatPercent } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

const breakdown = [
  { key: "waiting", label: "�ȴ���", color: "bg-[#b8bfb3]" },
  { key: "inviting", label: "������", color: "bg-[#8fa0b8]" },
  { key: "rate_limited", label: "Ƶ�����ƣ������ԣ�", color: "bg-[#e8a317]" },
  { key: "success", label: "����ɹ�", color: "bg-primary" },
  { key: "failed", label: "����ʧ��", color: "bg-danger" },
] as const;

export function ProgressPanel() {
  const stats = useInviteStore((s) => s.stats);
  const percent =
    stats.total > 0 ? Number(((stats.completed / stats.total) * 100).toFixed(2)) : 0;

  return (
    <div className="animate-fade-up rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold text-[#2f352d]">�������</h3>

      <div className="mb-3 flex items-end justify-between">
        <div className="text-[28px] font-semibold leading-none text-[#2f352d]">
          {formatNumber(stats.completed)}{" "}
          <span className="text-[18px] font-normal text-muted-foreground">
            / {formatNumber(stats.total)}
          </span>
        </div>
        <div className="text-[18px] font-semibold text-primary">{percent.toFixed(2)}%</div>
      </div>

      <Progress value={percent} className="mb-5 h-3" />

      <div className="space-y-3">
        {breakdown.map((item) => {
          const value = stats[item.key];
          return (
            <div key={item.key} className="flex items-center justify-between text-[13px]">
              <div className="flex items-center gap-2 text-[#4a5248]">
                <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
                {item.label}
              </div>
              <div className="text-muted-foreground">
                <span className="mr-3 font-medium text-[#2f352d]">{formatNumber(value)}</span>
                {formatPercent(value, stats.total)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
