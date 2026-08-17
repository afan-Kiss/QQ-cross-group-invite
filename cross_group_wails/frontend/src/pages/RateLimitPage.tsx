import { ShieldAlert, Copy, Eye, RotateCcw } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { formatDateTime, formatTime, toEpochMs } from "@/lib/utils";
import { toast } from "@/store/useToastStore";
import type { RateLimitRecord } from "@/lib/types";

async function copyText(text: string, label: string) {
  await navigator.clipboard.writeText(text);
  toast("success", `已复制${label}`);
}

export function RateLimitPage() {
  const rateLimitList = useInviteStore((s) => s.rateLimitList);
  const clearRateLimits = useInviteStore((s) => s.clearRateLimits);
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);
  const requeueMember = useInviteStore((s) => s.requeueMember);
  const getMember = useInviteStore((s) => s.getMember);

  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayMs = todayStart.getTime();
  const todayCount = rateLimitList.filter((r) => toEpochMs(r.at) >= todayMs).length;
  const sorted = [...rateLimitList].sort((a, b) => toEpochMs(b.at) - toEpochMs(a.at));
  const last = sorted[0];

  const canRequeue = (r: RateLimitRecord) => {
    const m = getMember(r.qq);
    return !!m && (m.status === "failed" || m.status === "rate_limited");
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[20px] font-semibold text-[#242824]">频繁限制</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            查看触发频率限制的成员记录
          </p>
        </div>
        {rateLimitList.length > 0 && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm("确定清空频繁记录？")) void clearRateLimits();
            }}
            className="rounded-[10px] border border-border px-3 py-1.5 text-[13px] text-muted-foreground hover:bg-[#f7faf5]"
          >
            清空记录
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "今日频繁", value: todayCount },
          { label: "总频繁", value: rateLimitList.length },
          { label: "待处理", value: rateLimitList.length },
          { label: "最近一次", value: last ? formatTime(last.at) : "—" },
        ].map((c) => (
          <div key={c.label} className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
            <div className="text-[12px] text-muted-foreground">{c.label}</div>
            <div className="mt-1 text-[18px] font-semibold truncate">{c.value}</div>
          </div>
        ))}
      </div>

      {rateLimitList.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center rounded-[16px] border border-border bg-white p-8 shadow-[var(--shadow-card)]">
          <ShieldAlert className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-[15px] font-medium">暂无频繁限制</p>
          <p className="mt-1 text-[13px] text-muted-foreground">邀请过程中触发的限制将记录在此</p>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-[16px] border border-border bg-white shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#f9faf8]">
              <tr className="border-b border-border text-[13px] text-muted-foreground">
                <th className="px-4 py-3">QQ号</th>
                <th className="px-4 py-3">昵称</th>
                <th className="px-4 py-3">来源群</th>
                <th className="px-4 py-3">目标群</th>
                <th className="px-4 py-3">触发时间</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">备注</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={`${r.qq}-${r.at}-${r.task_id ?? ""}`} className="border-b border-border/70 hover:bg-[#f7faf5]">
                  <td className="px-4 py-3 font-mono text-[13px]">{r.qq}</td>
                  <td className="px-4 py-3">{r.nickname}</td>
                  <td className="px-4 py-3">{r.source_group_id || "—"}</td>
                  <td className="px-4 py-3">{r.target_group_id || "—"}</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">{formatDateTime(r.at)}</td>
                  <td className="px-4 py-3 text-warning">待冷却</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">{r.reason ?? "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button type="button" className="rounded p-1 hover:bg-[#eef1eb]" title="复制QQ" onClick={() => void copyText(String(r.qq), "QQ")}>
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="rounded p-1 hover:bg-[#eef1eb] disabled:opacity-40"
                        title="查看"
                        disabled={!getMember(r.qq)}
                        onClick={() => setDetailMemberQq(r.qq)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="rounded p-1 hover:bg-[#eef1eb] disabled:opacity-40"
                        title="重新入队"
                        disabled={!canRequeue(r)}
                        onClick={() => requeueMember(r.qq)}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
