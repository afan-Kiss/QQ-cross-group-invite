import { useEffect, useState } from "react";
import { ArrowLeft, Square } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useNavigationStore } from "@/store/useNavigationStore";
import { formatDateTime, formatNumber } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { PersistedTask } from "@/lib/types";

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
  const startRaw = task?.startTime ?? Number(remote?.started_at || 0);
  const startTime = startRaw > 1e12 ? startRaw : startRaw * 1000;
  const endRaw = task?.endTime ?? Number(remote?.finished_at || 0);
  const endTime = endRaw ? (endRaw > 1e12 ? endRaw : endRaw * 1000) : 0;
  const isRunning = status === "running" || status === "preparing" || status === "stopping";
  const completed = isRunning ? stats.completed : success + frequent + failed;
  const pct = total > 0 ? (completed / total) * 100 : 0;
  const durationMs = endTime && startTime ? endTime - startTime : isRunning && startTime ? Date.now() - startTime : 0;
  const timeline = task?.timeline || remote?.timeline || [];

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
              任务 {id}
              <span className="ml-2 text-[14px] text-primary">{statusText(status)}</span>
            </h2>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {source} → {target}
            </p>
          </div>
        </div>
        {inviting && isRunning && (
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

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "总人数", value: total },
          { label: "成功", value: isRunning ? stats.success : success },
          { label: "频繁", value: isRunning ? stats.rate_limited : frequent },
          { label: "失败", value: isRunning ? stats.failed : failed },
        ].map((c) => (
          <div key={c.label} className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
            <div className="text-[12px] text-muted-foreground">{c.label}</div>
            <div className="mt-1 text-[22px] font-semibold">{formatNumber(c.value)}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-4 text-[15px] font-semibold">整体进度</h3>
          <div className="mb-2 flex justify-between text-[13px]">
            <span>
              {completed} / {total}
            </span>
            <span>{pct.toFixed(2)}%</span>
          </div>
          <Progress value={pct} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-[13px] text-muted-foreground">
            <div>开始时间：{formatDateTime(startTime / 1000)}</div>
            <div>结束时间：{endTime ? formatDateTime(endTime / 1000) : "—"}</div>
            <div>总耗时：{durationMs > 0 ? `${(durationMs / 1000).toFixed(1)} 秒` : "—"}</div>
            <div>当前成员：{isRunning ? stats.current_nickname || "—" : "—"}</div>
          </div>
          {(task?.errorMessage || remote?.error_message) && (
            <p className="mt-3 text-[13px] text-danger">
              {task?.errorMessage || remote?.error_message}
            </p>
          )}
        </div>

        <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-4 text-[15px] font-semibold">时间线</h3>
          <ul className="space-y-3 text-[13px]">
            {timeline.length === 0 ? (
              <li className="text-muted-foreground">暂无事件</li>
            ) : (
              timeline.map((ev, i) => (
                <li key={`${ev.at}-${i}`} className="flex gap-2">
                  <span className="text-primary">●</span>
                  <span>
                    <span className="text-muted-foreground">{formatDateTime(ev.at)} </span>
                    {eventLabel(ev.event)}
                    {ev.detail ? ` - ${ev.detail}` : ""}
                  </span>
                </li>
              ))
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
    preparing: "准备中",
    stopping: "正在停止",
  };
  return map[s] ?? s;
}

function eventLabel(event: string) {
  const map: Record<string, string> = {
    created: "任务创建",
    members_loaded: "成员加载",
    started: "任务开始",
    batch_start: "批次开始",
    rate_limited: "频繁",
    failed: "失败",
    stopped: "任务停止",
    completed: "任务完成",
    error: "任务异常",
  };
  return map[event] ?? event;
}
