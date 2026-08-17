import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Progress } from "@/components/ui/progress";
import { formatNumber, formatPercent } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

export function InviteProgressTab() {
  const stats = useInviteStore((s) => s.stats);
  const logs = useInviteStore((s) => s.logs);
  const percent =
    stats.total > 0 ? Number(((stats.completed / stats.total) * 100).toFixed(2)) : 0;

  const chartData = useMemo(
    () => [
      {
        time: "��ǰ",
        success: stats.success,
        failed: stats.failed,
        rateLimited: stats.rate_limited,
      },
    ],
    [stats.success, stats.failed, stats.rate_limited],
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {[
          { label: "�ɹ�", value: stats.success, color: "text-primary" },
          { label: "ʧ��", value: stats.failed, color: "text-danger" },
          { label: "Ƶ������", value: stats.rate_limited, color: "text-[#d49a12]" },
          { label: "�ȴ���", value: stats.waiting, color: "text-muted-foreground" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-[12px] border border-border bg-[#fafbf9] p-4"
          >
            <div className="text-[12px] text-muted-foreground">{item.label}</div>
            <div className={`text-[28px] font-semibold ${item.color}`}>
              {formatNumber(item.value)}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-[12px] border border-border bg-[#fafbf9] p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-[14px] font-medium text-[#2f352d]">�ܽ���</div>
          <div className="text-[14px] font-semibold text-primary">
            {formatNumber(stats.completed)} / {formatNumber(stats.total)}��{percent}%��
          </div>
        </div>
        <Progress value={percent} className="h-3" />
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-[12px] border border-border bg-white p-4">
          <h4 className="mb-3 text-[14px] font-semibold text-[#2f352d]">����ͳ��</h4>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eceee9" />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="success" name="�ɹ�" fill="#67B357" radius={[4, 4, 0, 0]} />
                <Bar dataKey="failed" name="ʧ��" fill="#E05252" radius={[4, 4, 0, 0]} />
                <Bar
                  dataKey="rateLimited"
                  name="Ƶ������"
                  fill="#E8A317"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex min-h-0 flex-col rounded-[12px] border border-border bg-white p-4">
          <h4 className="mb-3 text-[14px] font-semibold text-[#2f352d]">��ǰ����</h4>
          <div className="mb-4 space-y-2 text-[13px] text-[#4a5248]">
            <p>
              ���Σ��� {stats.batch.batchNumber} ����{stats.batch.batchDone} /{" "}
              {stats.batch.batchTotal}��
            </p>
            <p>
              ��ǰ��Ա��{stats.current_nickname || "��"} ({stats.current_qq || "��"})
            </p>
            <p>���ʣ�ࣺ{formatNumber(stats.batch.intervalRemainingMs)} ms</p>
            <p>��ɱ�����{formatPercent(stats.completed, stats.total)}</p>
          </div>
          <h4 className="mb-2 text-[14px] font-semibold text-[#2f352d]">�����־</h4>
          <div className="min-h-0 flex-1 overflow-auto rounded-[10px] border border-border bg-[#fafbf9] p-3 font-mono text-[12px] leading-6 text-muted-foreground">
            {logs.length === 0 ? (
              <div>������־</div>
            ) : (
              logs.slice(-8).map((line, i) => <div key={`${line}-${i}`}>{line}</div>)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
