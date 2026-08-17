import { Button } from "@/components/ui/button";
import { useInviteStore } from "@/store/useInviteStore";

export function FailedPanel() {
  const list = useInviteStore((s) => s.failedList);
  const clearFailed = useInviteStore((s) => s.clearFailed);
  const count = useInviteStore((s) => s.stats.failed);

  return (
    <div className="animate-fade-up flex h-full min-h-[220px] flex-col rounded-[16px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[15px] font-semibold text-[#2f352d]">����ʧ�ܣ�{count} �ˣ�</h3>
        <Button variant="ghost" size="sm" onClick={clearFailed}>
          ���
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="pb-2 font-medium">QQ��</th>
              <th className="pb-2 font-medium">�ǳ�</th>
              <th className="pb-2 font-medium">ʧ��ԭ��</th>
              <th className="pb-2 font-medium">����</th>
            </tr>
          </thead>
          <tbody>
            {list.slice(0, 5).map((item) => (
              <tr key={item.qq} className="border-b border-border/60 hover:bg-[#f7f9f5]">
                <td className="py-2 font-mono">{item.qq}</td>
                <td className="py-2">{item.nickname}</td>
                <td className="max-w-[120px] truncate py-2 text-muted-foreground">
                  {item.reason}
                </td>
                <td className="py-2">
                  <button className="text-danger hover:underline">����</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2 flex items-center justify-between text-[12px] text-muted-foreground">
        <span>�� {count} ��</span>
        <button className="text-primary hover:underline">�鿴����</button>
      </div>
    </div>
  );
}
