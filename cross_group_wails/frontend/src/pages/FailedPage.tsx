import { CircleX, Copy, Eye, RotateCcw } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { formatDateTime, toEpochMs } from "@/lib/utils";
import { toast } from "@/store/useToastStore";
import type { FailedRecord } from "@/lib/types";

function reasonColor(reason: string) {
  if (/权限|permission/i.test(reason)) return "text-[#6b7a8a]";
  if (/token/i.test(reason)) return "text-warning";
  if (/风控|频繁|limit/i.test(reason)) return "text-[#d4785a]";
  if (/系统|system/i.test(reason)) return "text-danger";
  return "text-muted-foreground";
}

async function copyText(text: string, label: string) {
  await navigator.clipboard.writeText(text);
  toast("success", `已复制${label}`);
}

export function FailedPage() {
  const failedList = useInviteStore((s) => s.failedList);
  const clearFailed = useInviteStore((s) => s.clearFailed);
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);
  const requeueMember = useInviteStore((s) => s.requeueMember);
  const getMember = useInviteStore((s) => s.getMember);

  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayMs = todayStart.getTime();
  const todayCount = failedList.filter((r) => toEpochMs(r.at) >= todayMs).length;
  const permCount = failedList.filter((r) => /权限/i.test(r.reason)).length;
  const tokenCount = failedList.filter((r) => /token|邀请信息/i.test(r.reason)).length;
  const otherCount = failedList.length - permCount - tokenCount;

  const canRequeue = (r: FailedRecord) => {
    const m = getMember(r.qq);
    return !!m && (m.status === "failed" || m.status === "rate_limited");
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[20px] font-semibold text-[#242824]">邀请失败</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            查看邀请失败及异常信息
          </p>
        </div>
        {failedList.length > 0 && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm("确定清空失败记录？")) void clearFailed();
            }}
            className="rounded-[10px] border border-border px-3 py-1.5 text-[13px] text-muted-foreground hover:bg-[#f7faf5]"
          >
            清空记录
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "今日失败", value: todayCount },
          { label: "权限问题", value: permCount },
          { label: "邀请信息", value: tokenCount },
          { label: "其他错误", value: otherCount },
        ].map((c) => (
          <div key={c.label} className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
            <div className="text-[12px] text-muted-foreground">{c.label}</div>
            <div className="mt-1 text-[22px] font-semibold">{c.value}</div>
          </div>
        ))}
      </div>

      {failedList.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center rounded-[16px] border border-border bg-white p-8 shadow-[var(--shadow-card)]">
          <CircleX className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-[15px] font-medium">暂无邀请失败记录</p>
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
                <th className="px-4 py-3">失败时间</th>
                <th className="px-4 py-3">失败原因</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {failedList.map((r) => (
                <tr key={`${r.qq}-${r.at}-${r.task_id ?? ""}`} className="border-b border-border/70 hover:bg-[#f7faf5]">
                  <td className="px-4 py-3 font-mono text-[13px]">{r.qq}</td>
                  <td className="px-4 py-3">{r.nickname}</td>
                  <td className="px-4 py-3">{r.source_group_id || "—"}</td>
                  <td className="px-4 py-3">{r.target_group_id || "—"}</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">{formatDateTime(r.at)}</td>
                  <td className={`px-4 py-3 text-[13px] ${reasonColor(r.reason)}`}>{r.reason}</td>
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
