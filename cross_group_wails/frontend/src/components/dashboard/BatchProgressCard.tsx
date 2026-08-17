import { Progress } from "@/components/ui/progress";
import { useInviteStore } from "@/store/useInviteStore";

export function BatchProgressCard() {
  const batch = useInviteStore((s) => s.stats.batch);
  const inviting = useInviteStore((s) => s.inviting);
  const percent =
    batch.batchTotal > 0
      ? Number(((batch.batchDone / batch.batchTotal) * 100).toFixed(2))
      : 0;
  const remainingSec = (batch.intervalRemainingMs || 0) / 1000;

  return (
    <div className="animate-fade-up rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold text-[#2f352d]">
        当前批次进度（第 {batch.batchNumber} / {batch.totalBatches || "\u2014"} 批）
      </h3>

      <div className="mb-3 flex items-end justify-between">
        <div className="text-[24px] font-semibold leading-none text-[#2f352d]">
          {batch.batchDone}{" "}
          <span className="text-[16px] font-normal text-muted-foreground">
            / {batch.batchTotal}
          </span>
        </div>
        <div className="text-[16px] font-semibold text-primary">{percent.toFixed(2)}%</div>
      </div>

      <Progress value={percent} className="mb-4 h-2.5" />

      <div className="space-y-2 text-[13px]">
        <p className="text-[#4a5248]">
          当前成员：
          <span className="font-medium text-[#2f352d]">
            {batch.currentNickname || "\u2014"} ({batch.currentQq || "\u2014"})
          </span>
        </p>
        <p className="text-muted-foreground">
          下一次邀请：
          <span className="font-medium text-[#2f352d]">
            {inviting && remainingSec > 0
              ? `${remainingSec.toFixed(1)} 秒`
              : inviting
                ? "进行中"
                : "0"}
          </span>
        </p>
      </div>
    </div>
  );
}
