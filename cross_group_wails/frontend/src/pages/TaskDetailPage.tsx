import { ArrowLeft, Square } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useNavigationStore } from "@/store/useNavigationStore";
import { formatNumber } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

export function TaskDetailPage() {
  const taskId = useNavigationStore((s) => s.taskId);
  const backToTasks = useNavigationStore((s) => s.backToTasks);
  const getTask = useInviteStore((s) => s.getTask);
  const stats = useInviteStore((s) => s.stats);
  const stopInvite = useInviteStore((s) => s.stopInvite);
  const inviting = useInviteStore((s) => s.inviting);

  const task = taskId ? getTask(taskId) : undefined;

  if (!task) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">任务不存在</p>
      </div>
    );
  }

  const pct = task.total > 0 ? (stats.completed / task.total) * 100 : 0;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={backToTasks}
            className="rounded-[8px] p-2 hover:bg-[#f7faf5]"
            title="返回列表"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h2 className="text-[20px] font-semibold text-[#242824]">
              任务 #{task.id}
              <span className="ml-2 text-[14px] text-primary">
                {task.status === "running" ? "运行中" : statusText(task.status)}
              </span>
            </h2>
          </div>
        </div>
        {inviting && task.status === "running" && (
          <button
            type="button"
            onClick={() => void stopInvite()}
            className="flex items-center gap-2 rounded-[10px] bg-[#fdeeee] px-4 py-2 text-[13px] text-danger hover:bg-danger/10"
          >
            <Square className="h-4 w-4" />
            停止任务
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: "总数", value: task.total },
          { label: "完成", value: stats.completed },
          { label: "成功", value: stats.success },
          { label: "频繁", value: stats.rate_limited },
          { label: "失败", value: stats.failed },
        ].map((c) => (
          <div key={c.label} className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
            <div className="text-[12px] text-muted-foreground">{c.label}</div>
            <div className="mt-1 text-[22px] font-semibold">{formatNumber(c.value)}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-4 text-[15px] font-semibold">整体进度</h3>
          <div className="mb-2 flex justify-between text-[13px]">
            <span>{stats.completed} / {task.total}</span>
            <span>{pct.toFixed(2)}%</span>
          </div>
          <Progress value={pct} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-[13px] text-muted-foreground">
            <div>开始时间：{new Date(task.startTime).toLocaleString("zh-CN")}</div>
            <div>来源群：{task.sourceGroup}</div>
            <div>目标群：{task.targetGroup}</div>
            <div>当前成员：{stats.current_nickname || "—"}</div>
          </div>
        </div>

        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-4 text-[15px] font-semibold">时间线</h3>
          <ul className="space-y-3 text-[13px]">
            <li className="flex gap-2">
              <span className="text-muted-foreground">●</span>
              <span>任务创建</span>
            </li>
            {stats.completed > 0 && (
              <li className="flex gap-2">
                <span className="text-primary">●</span>
                <span>已处理 {stats.completed} 人</span>
              </li>
            )}
            {stats.rate_limited > 0 && (
              <li className="flex gap-2">
                <span className="text-warning">●</span>
                <span>遇到频繁限制 ({stats.rate_limited})</span>
              </li>
            )}
            {task.status === "stopped" && (
              <li className="flex gap-2">
                <span className="text-danger">●</span>
                <span>任务停止</span>
              </li>
            )}
            {task.status === "completed" && (
              <li className="flex gap-2">
                <span className="text-primary">●</span>
                <span>任务完成</span>
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

function statusText(s: string) {
  const map: Record<string, string> = {
    stopped: "已停止",
    completed: "已完成",
    error: "异常",
    running: "运行中",
  };
  return map[s] ?? s;
}
