import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useNavigationStore } from "@/store/useNavigationStore";
import { formatDateTime, formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

const statusLabel = {
  running: "运行中",
  preparing: "运行中",
  stopping: "运行中",
  stopped: "已停止",
  completed: "已完成",
  error: "异常",
  interrupted: "异常中断",
} as const;

const statusColor = {
  running: "text-primary bg-primary-light",
  preparing: "text-primary bg-primary-light",
  stopping: "text-primary bg-primary-light",
  stopped: "text-muted-foreground bg-[#f7faf5]",
  completed: "text-[#5c8fd8] bg-[#eef4fc]",
  error: "text-danger bg-danger-light",
  interrupted: "text-danger bg-danger-light",
} as const;

type Filter = "all" | "running" | "completed" | "stopped" | "error";

export function TasksPage() {
  const tasks = useInviteStore((s) => s.tasks);
  const loadTasks = useInviteStore((s) => s.loadTasks);
  const stopInvite = useInviteStore((s) => s.stopInvite);
  const currentTaskId = useInviteStore((s) => s.currentTaskId);
  const inviting = useInviteStore((s) => s.inviting);
  const stats = useInviteStore((s) => s.stats);
  const openTaskDetail = useNavigationStore((s) => s.openTaskDetail);
  const navigate = useNavigationStore((s) => s.navigate);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  const filtered = tasks.filter((t) => {
    if (filter === "all") return true;
    if (filter === "running") return ["running", "preparing", "stopping"].includes(t.status);
    if (filter === "error") return t.status === "error" || t.status === "interrupted";
    return t.status === filter;
  });

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[20px] font-semibold text-[#242824]">邀请任务</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">查看当前与历史邀请任务</p>
        </div>
        <button
          type="button"
          onClick={() => navigate("dashboard")}
          className="flex items-center gap-2 rounded-[10px] bg-primary px-4 py-2 text-[13px] font-medium text-white hover:bg-primary-hover"
        >
          <Plus className="h-4 w-4" />
          新建任务
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["all", "全部"],
            ["running", "运行中"],
            ["completed", "已完成"],
            ["stopped", "已停止"],
            ["error", "异常"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setFilter(k)}
            className={cn(
              "rounded-[8px] px-3 py-1.5 text-[13px]",
              filter === k ? "bg-primary text-white" : "bg-[#f7faf5] text-muted-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center rounded-[16px] border border-border bg-white p-8 shadow-[var(--shadow-card)]">
          <p className="text-[15px] font-medium text-[#242824]">暂无邀请任务</p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            在控制台配置并启动邀请后，任务将显示在这里
          </p>
          <button
            type="button"
            onClick={() => navigate("dashboard")}
            className="mt-4 rounded-[10px] bg-primary px-4 py-2 text-[13px] text-white hover:bg-primary-hover"
          >
            前往控制台
          </button>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-[16px] border border-border bg-white shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#f9faf8]">
              <tr className="border-b border-border text-[13px] text-muted-foreground">
                <th className="px-4 py-3">任务ID</th>
                <th className="px-4 py-3">来源群</th>
                <th className="px-4 py-3">目标群</th>
                <th className="px-4 py-3">开始时间</th>
                <th className="px-4 py-3">结束时间</th>
                <th className="px-4 py-3">总人数</th>
                <th className="px-4 py-3">成功</th>
                <th className="px-4 py-3">频繁</th>
                <th className="px-4 py-3">失败</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const isActiveRunning =
                  inviting &&
                  (stats.task_id === t.id || currentTaskId === t.id) &&
                  stats.task_id === t.id &&
                  ["running", "preparing", "stopping"].includes(t.status);
                return (
                  <tr
                    key={t.id}
                    className="cursor-pointer border-b border-border/70 transition-colors hover:bg-[#f7faf5]"
                    onClick={() => openTaskDetail(t.id)}
                  >
                    <td className="px-4 py-3 font-mono text-[12px]">{t.id}</td>
                    <td className="px-4 py-3">{t.sourceGroup}</td>
                    <td className="px-4 py-3">{t.targetGroup}</td>
                    <td className="px-4 py-3">{formatDateTime(t.startTime)}</td>
                    <td className="px-4 py-3">{t.endTime ? formatDateTime(t.endTime) : "—"}</td>
                    <td className="px-4 py-3">{formatNumber(t.total)}</td>
                    <td className="px-4 py-3 text-primary">{formatNumber(t.success)}</td>
                    <td className="px-4 py-3 text-warning">{formatNumber(t.frequent)}</td>
                    <td className="px-4 py-3 text-danger">{formatNumber(t.failed)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[12px]",
                          statusColor[t.status as keyof typeof statusColor] || statusColor.completed,
                        )}
                      >
                        {statusLabel[t.status as keyof typeof statusLabel] || t.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isActiveRunning && (
                        <button
                          type="button"
                          className="text-[13px] text-danger hover:underline"
                          onClick={(e) => {
                            e.stopPropagation();
                            void stopInvite(t.id);
                          }}
                        >
                          停止
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
