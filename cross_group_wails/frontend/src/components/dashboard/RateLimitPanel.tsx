import { Button } from "@/components/ui/button";
import { useInviteStore } from "@/store/useInviteStore";
import { formatTime } from "@/lib/utils";
import { toast } from "@/store/useToastStore";

export function RateLimitPanel() {
  const list = useInviteStore((s) => s.rateLimitList);
  const clearRateLimits = useInviteStore((s) => s.clearRateLimits);
  const requeueMember = useInviteStore((s) => s.requeueMember);
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);

  return (
    <div className="flex h-full min-h-[220px] flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[15px] font-semibold text-[#2f352d]">频繁限制</h3>
        <Button variant="secondary" size="sm" onClick={() => void clearRateLimits()}>
          清空
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {list.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">暂无频繁记录</p>
        ) : (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pb-2">QQ</th>
                <th className="pb-2">昵称</th>
                <th className="pb-2">时间</th>
                <th className="pb-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {list.map((item) => (
                <tr key={`${item.qq}-${item.at}`} className="border-t border-border/60">
                  <td className="py-2 font-mono">{item.qq}</td>
                  <td className="py-2">{item.nickname}</td>
                  <td className="py-2">{formatTime(item.at)}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={async () => {
                          await navigator.clipboard.writeText(String(item.qq));
                          toast("success", "已复制QQ");
                        }}
                      >
                        复制QQ
                      </button>
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => setDetailMemberQq(item.qq)}
                      >
                        查看成员
                      </button>
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => requeueMember(item.qq)}
                      >
                        重新邀请
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
