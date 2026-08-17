import { Progress } from "@/components/ui/progress";
import { formatNumber } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

export function BatchProgressCard() {
  const batch = useInviteStore((s) => s.stats.batch);
  const percent =
    batch.batchTotal > 0
      ? Number(((batch.batchDone / batch.batchTotal) * 100).toFixed(2))
      : 0;

  return (
    <div className="animate-fade-up rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold text-[#2f352d]">
        ��ǰ���ν��ȣ��� {batch.batchNumber} ����
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
          �������룺
          <span className="font-medium text-[#2f352d]">
            {batch.currentNickname} ({batch.currentQq})
          </span>
        </p>
        <p className="text-muted-foreground">
          ���ʣ�ࣺ
          <span className="font-medium text-[#2f352d]">
            {formatNumber(batch.intervalRemainingMs)} ms
          </span>
        </p>
      </div>
    </div>
  );
}
