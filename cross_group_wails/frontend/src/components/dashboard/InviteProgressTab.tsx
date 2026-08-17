import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Progress } from "@/components/ui/progress";
import { cn, formatNumber } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

export function InviteProgressTab() {
  const stats = useInviteStore((s) => s.stats);
  const inviting = useInviteStore((s) => s.inviting);
  const [range, setRange] = useState<"1m" | "5m">("1m");

  const percent =
    stats.total > 0 ? Number(((stats.completed / stats.total) * 100).toFixed(2)) : 0;

  const chartData = useMemo(() => {
    const points = range === "1m" ? 12 : 30;
    const base = stats.success;
    return Array.from({ length: points }, (_, i) => ({
      time: range === "1m" ? `${60 - i * 5}s` : `${5 - Math.floor(i / 6)}m`,
      count: Math.max(0, base - (points - i) * 2 + Math.floor(Math.random() * 3)),
    }));
  }, [stats.success, range]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-[#242824]">
            {inviting ? "任务运行中" : "邀请进度"}
          </h3>
          {inviting && (
            <p className="text-[13px] text-muted-foreground">
              当前批次：{stats.batch.batchNumber}
            </p>
          )}
        </div>
        <div className="text-right">
          <div className="text-[13px] text-muted-foreground">
            {formatNumber(stats.completed)} / {formatNumber(stats.total)}
          </div>
          <div className="text-[20px] font-semibold text-primary">{percent.toFixed(2)}%</div>
        </div>
      </div>

      <Progress value={percent} className="h-3" />

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-medium">每分钟邀请数</span>
          <div className="flex gap-1">
            {(["1m", "5m"] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={cn(
                  "rounded-[8px] px-2.5 py-1 text-[12px]",
                  range === r ? "bg-primary text-white" : "text-muted-foreground hover:bg-[#f7faf5]",
                )}
              >
                {r === "1m" ? "1分钟" : "5分钟"}
              </button>
            ))}
          </div>
        </div>
        <div className="h-[140px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e8e1" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#6b726a" />
              <YAxis tick={{ fontSize: 11 }} stroke="#6b726a" />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#65ad57" fill="#eaf5e7" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-[12px] border border-border bg-[#fafbf9] p-4">
          <div className="text-[12px] text-muted-foreground">当前成员</div>
          <div className="mt-2 text-[15px] font-semibold">{stats.current_nickname || "—"}</div>
          <div className="mt-1 font-mono text-[13px] text-muted-foreground">
            {stats.current_qq || "—"}
          </div>
          <div className="mt-2 text-[12px] text-primary">
            {inviting ? "正在邀请..." : "等待中"}
          </div>
        </div>
        <div className="rounded-[12px] border border-border bg-[#fafbf9] p-4">
          <div className="text-[12px] text-muted-foreground">
            当前批次 #{stats.batch.batchNumber}
          </div>
          <div className="mt-2 text-[15px] font-semibold">
            {stats.batch.batchDone} / {stats.batch.batchTotal}
          </div>
          <Progress
            value={
              stats.batch.batchTotal > 0
                ? (stats.batch.batchDone / stats.batch.batchTotal) * 100
                : 0
            }
            className="mt-3 h-2"
          />
          <div className="mt-2 flex gap-4 text-[12px]">
            <span className="text-primary">成功 {stats.success}</span>
            <span className="text-warning">频繁 {stats.rate_limited}</span>
            <span className="text-danger">失败 {stats.failed}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
