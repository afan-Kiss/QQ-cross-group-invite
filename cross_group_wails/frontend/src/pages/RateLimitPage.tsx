import { ShieldAlert } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";

export function RateLimitPage() {
  const rateLimitList = useInviteStore((s) => s.rateLimitList);
  const configData = useInviteStore((s) => s.config);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayCount = rateLimitList.filter((r) => r.at >= today.getTime()).length;
  const last = rateLimitList[0];

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div>
        <h2 className="text-[20px] font-semibold text-[#242824]">???????</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          ???????????????????
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "???????", value: todayCount },
          { label: "?????", value: rateLimitList.length },
          { label: "??????", value: rateLimitList.length },
          { label: "??????", value: last ? new Date(last.at).toLocaleTimeString("zh-CN") : "??" },
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
          <p className="text-[15px] font-medium">???????????</p>
          <p className="mt-1 text-[13px] text-muted-foreground">????????§Õ????????????????</p>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-[16px] border border-border bg-white shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#f9faf8]">
              <tr className="border-b border-border text-[13px] text-muted-foreground">
                <th className="px-4 py-3">QQ??</th>
                <th className="px-4 py-3">???</th>
                <th className="px-4 py-3">????</th>
                <th className="px-4 py-3">????</th>
                <th className="px-4 py-3">???????</th>
                <th className="px-4 py-3">??</th>
                <th className="px-4 py-3">???</th>
              </tr>
            </thead>
            <tbody>
              {rateLimitList.map((r) => (
                <tr key={`${r.qq}-${r.at}`} className="border-b border-border/70 hover:bg-[#f7faf5]">
                  <td className="px-4 py-3 font-mono text-[13px]">{r.qq}</td>
                  <td className="px-4 py-3">{r.nickname}</td>
                  <td className="px-4 py-3">{configData.source_group_id}</td>
                  <td className="px-4 py-3">{configData.target_group_id}</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">
                    {new Date(r.at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-3 text-warning">?????</td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">{r.reason ?? "??"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
