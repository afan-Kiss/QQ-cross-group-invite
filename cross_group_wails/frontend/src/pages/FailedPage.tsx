import { CircleX } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";

function reasonColor(reason: string) {
  if (/权限|permission/i.test(reason)) return "text-[#6b7a8a]";
  if (/token/i.test(reason)) return "text-warning";
  if (/风控|频繁|limit/i.test(reason)) return "text-[#d4785a]";
  if (/系统|system/i.test(reason)) return "text-danger";
  return "text-muted-foreground";
}

export function FailedPage() {
  const failedList = useInviteStore((s) => s.failedList);
  const config = useInviteStore((s) => s.config);
  const clearFailed = useInviteStore((s) => s.clearFailed);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayCount = failedList.filter((r) => r.at >= today.getTime()).length;
  const permCount = failedList.filter((r) => /权限/i.test(r.reason)).length;
  const tokenCount = failedList.filter((r) => /token/i.test(r.reason)).length;
  const otherCount = failedList.length - permCount - tokenCount;

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
              if (window.confirm("确定清空失败记录？")) clearFailed();
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
          { label: "Token问题", value: tokenCount },
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
                <th className="px-4 py-3">目标群</th>
                <th className="px-4 py-3">失败时间</th>
                <th className="px-4 py-3">失败原因</th>
              </tr>
            </thead>
            <tbody>
              {failedList.map((r) => (
                <tr key={`${r.qq}-${r.at}`} className="border-b border-border/70 hover:bg-[#f7faf5]">
                  <td className="px-4 py-3 font-mono text-[13px]">{r.qq}</td>
                  <td className="px-4 py-3">{r.nickname}</td>
                  <td className="px-4 py-3">{config.target_group_id}</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">
                    {new Date(r.at).toLocaleString("zh-CN")}
                  </td>
                  <td className={`px-4 py-3 text-[13px] ${reasonColor(r.reason)}`}>{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
