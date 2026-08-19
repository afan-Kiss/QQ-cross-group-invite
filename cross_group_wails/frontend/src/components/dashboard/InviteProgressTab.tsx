import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Progress } from "@/components/ui/progress";
import { cn, formatNumber, formatTime } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

export function InviteProgressTab() {
  const stats = useInviteStore((s) => s.stats);
  const inviting = useInviteStore((s) => s.inviting);
  const rateSeries = useInviteStore((s) => s.rateSeries);
  const [range, setRange] = useState<"1m" | "5m">("1m");

  const percent =
    stats.total > 0 ? Number(((stats.completed / stats.total) * 100).toFixed(2)) : 0;

  const chartData = useMemo(() => {
    const now = Date.now() / 1000;
    const windowSec = range === "1m" ? 60 : 300;
    const points = (rateSeries.length ? rateSeries : stats.rate_series || [])
      .filter((p) => p.timestamp >= now - windowSec)
      .map((p) => ({
        time: formatTime(p.timestamp),
        success: p.success,
        failed: p.failed,
        rateLimited: p.rate_limited,
        total: p.total,
        timestamp: p.timestamp,
      }));
    return points;
  }, [rateSeries, stats.rate_series, range]);

  const remainingSec = (stats.batch.intervalRemainingMs || 0) / 1000;

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-[#242824]">
            {inviting ? "任务运行中" : "邀请进度"}
          </h3>
          {inviting && (
            <p className="text-[13px] text-muted-foreground">
              当前批次：{stats.batch.batchNumber} / {stats.batch.totalBatches || "—"}
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
          <span className="text-[13px] font-medium">邀请速率</span>
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
        <div className="h-[160px]">
          {chartData.length === 0 ? (
            <div className="flex h-full items-center justify-center text-[13px] text-muted-foreground">
              暂无运行数据
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e8e1" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#6b726a" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="#6b726a" />
                <Tooltip
                  contentStyle={{ fontSize: 12 }}
                  formatter={(value, name) => {
                    const label =
                      name === "success"
                        ? "成功"
                        : name === "failed"
                          ? "失败"
                          : name === "rateLimited"
                            ? "频繁"
                            : "总处理量";
                    return [value as number, label];
                  }}
                />
                <Legend
                  formatter={(v) =>
                    v === "success"
                      ? "成功"
                      : v === "failed"
                        ? "失败"
                        : v === "rateLimited"
                          ? "频繁"
                          : "总处理量"
                  }
                />
                <Area type="monotone" dataKey="success" stroke="#65ad57" fill="#eaf5e7" strokeWidth={2} />
                <Area type="monotone" dataKey="failed" stroke="#d9534f" fill="#fdeceb" strokeWidth={1} />
                <Area type="monotone" dataKey="rateLimited" stroke="#d49a12" fill="#fff6e5" strokeWidth={1} />
                <Area type="monotone" dataKey="total" stroke="#6b7a8f" fill="transparent" strokeWidth={1} />
              </AreaChart>
            </ResponsiveContainer>
          )}
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
            {inviting
              ? remainingSec > 0
                ? `下一次邀请：${remainingSec.toFixed(1)} 秒`
                : "正在邀请..."
              : "等待中"}
          </div>
        </div>
        <div className="rounded-[12px] border border-border bg-[#fafbf9] p-4">
          <div className="text-[12px] text-muted-foreground">
            当前批次 #{stats.batch.batchNumber || 0}
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
          <div className="mt-2 flex flex-wrap gap-4 text-[12px]">
            <span className="text-primary">成功 {stats.success}</span>
            <span className="text-warning">频繁 {stats.rate_limited}</span>
            <span className="text-danger">失败 {stats.failed}</span>
            <span className="text-muted-foreground">等待 {stats.waiting}</span>
            <span className="text-muted-foreground">已取消 {stats.cancelled}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
