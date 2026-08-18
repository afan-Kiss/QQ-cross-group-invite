import { useEffect, useState } from "react";
import { ArrowLeft, Square } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useNavigationStore } from "@/store/useNavigationStore";
import { formatDateTime, formatNumber, formatTimelineText, toEpochMs } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { PersistedTask } from "@/lib/types";

const statusLabel: Record<string, string> = {
  running: "运行中",
  preparing: "运行中",
  stopping: "运行中",
  stopped: "已停止",
  completed: "已完成",
  error: "异常",
  interrupted: "异常中断",
};

export function TaskDetailPage() {
  const taskId = useNavigationStore((s) => s.taskId);
  const backToTasks = useNavigationStore((s) => s.backToTasks);
  const getTask = useInviteStore((s) => s.getTask);
  const stats = useInviteStore((s) => s.stats);
  const stopInvite = useInviteStore((s) => s.stopInvite);
  const inviting = useInviteStore((s) => s.inviting);
  const [remote, setRemote] = useState<PersistedTask | null>(null);

  const task = taskId ? getTask(taskId) : undefined;

  useEffect(() => {
    if (!taskId) return;
    void api.getTask(taskId).then(setRemote).catch(() => setRemote(null));
  }, [taskId]);

  if (!task && !remote) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">任务不存在</p>
      </div>
    );
  }

  const id = task?.id || String(remote?.id || "");
  const status = task?.status || String(remote?.status || "");
  const total = task?.total ?? Number(remote?.total || 0);
  const success = task?.success ?? Number(remote?.success || 0);
  const frequent = task?.frequent ?? Number(remote?.rate_limited || 0);
  const failed = task?.failed ?? Number(remote?.failed || 0);
  const source = task?.sourceGroup ?? String(remote?.source_group_id || "");
  const target = task?.targetGroup ?? String(remote?.target_group_id || "");
  const startTime = toEpochMs(task?.startTime ?? Number(remote?.started_at || 0));
  const endTime = toEpochMs(task?.endTime ?? Number(remote?.finished_at || 0));
  const isLive = Boolean(taskId && stats.task_id && taskId === stats.task_id && (stats.running || inviting));
  const completed = isLive ? stats.completed : success + frequent + failed;
  const pct = total > 0 ? (completed / total) * 100 : 0;
  const durationMs = endTime && startTime ? endTime - startTime : isLive && startTime ? Date.now() - startTime : 0;
  const timeline = task?.timeline || remote?.timeline || [];

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button type="button" onClick={backToTasks} className="rounded-[8px] p-2 hover:bg-[#f7faf5]" title="返回列表">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h2 className="text-[20px] font-semibold text-[#242824]">
              任务 {id}
              <span className="ml-2 text-[14px] text-primary">{statusLabel[status] || status}</span>
            </h2>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {source} → {target}
            </p>
          </div>
        </div>
        {isLive && (
          <button
            type="button"
            onClick={() => void stopInvite(id)}
            className="flex items-center gap-2 rounded-[10px] bg-[#fdeeee] px-4 py-2 text-[13px] text-danger hover:bg-danger/10"
          >
            <Square className="h-4 w-4" />
            停止任务
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "总人数", value: total },
          { label: "成功", value: isLive ? stats.success : success },
          { label: "频繁", value: isLive ? stats.rate_limited : frequent },
          { label: "失败", value: isLive ? stats.failed : failed },
        ].map((c) => (
          <div key={c.label} className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
            <div className="text-[12px] text-muted-foreground">{c.label}</div>
            <div className="mt-1 text-[22px] font-semibold">{formatNumber(c.value)}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <div className="mb-2 flex justify-between text-[13px]">
            <span>进度</span>
            <span>{formatNumber(completed)} / {formatNumber(total)} ({pct.toFixed(1)}%)</span>
          </div>
          <Progress value={pct} />
          <div className="mt-4 space-y-1 text-[13px] text-muted-foreground">
            <div>开始时间：{formatDateTime(startTime)}</div>
            <div>结束时间：{endTime ? formatDateTime(endTime) : "—"}</div>
            <div>耗时：{durationMs ? `${(durationMs / 1000).toFixed(1)} 秒` : "—"}</div>
            {!isLive && <div className="text-[12px]">这是已经结束的任务，显示当时保存下来的结果</div>}
          </div>
        </div>
        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 text-[14px] font-semibold">事件时间线</h3>
          <div className="max-h-[280px] space-y-2 overflow-auto text-[12px]">
            {timeline.length === 0 ? (
              <p className="text-muted-foreground">暂无事件</p>
            ) : (
              timeline.map((ev, idx) => (
                <div key={`${ev.at}-${idx}`} className="border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">{formatDateTime(ev.at)} </span>
                  <span>{formatTimelineText(ev.event, ev.detail)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
