import { useEffect, useRef, useState } from "react";
import { FileText, Download, Trash2 } from "lucide-react";
import { LOG_LEVEL_LABELS, LOG_MODULE_LABELS, type LogLevel, useLogStore } from "@/store/useLogStore";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";
import { cn } from "@/lib/utils";
import { wailsBridge } from "@/lib/wails-bridge";
import { toast } from "@/store/useToastStore";

const levelColors = {
  INFO: "bg-[#eef4fc] text-[#5c8fd8]",
  SUCCESS: "bg-primary-light text-primary",
  WARN: "bg-warning-light text-warning",
  ERROR: "bg-danger-light text-danger",
} as const;

const FILTERS: Array<{ v: string; l: string }> = [
  { v: "all", l: "全部" },
  { v: "INFO", l: LOG_LEVEL_LABELS.INFO },
  { v: "SUCCESS", l: LOG_LEVEL_LABELS.SUCCESS },
  { v: "WARN", l: LOG_LEVEL_LABELS.WARN },
  { v: "ERROR", l: LOG_LEVEL_LABELS.ERROR },
];

export function LogsPage() {
  const entries = useLogStore((s) => s.entries);
  const autoScroll = useLogStore((s) => s.autoScroll);
  const setAutoScroll = useLogStore((s) => s.setAutoScroll);
  const clearLogs = useInviteStore((s) => s.clearLogs);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = entries.filter((e) => {
    if (filter !== "all" && e.level !== filter) return false;
    if (search && !e.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered, autoScroll]);

  const lastError = [...entries].reverse().find((e) => e.level === "ERROR")?.message ?? "—";

  const exportLogs = async () => {
    const text = filtered
      .map(
        (e) =>
          `${e.time} ${LOG_LEVEL_LABELS[e.level]} [${LOG_MODULE_LABELS[e.module]}] ${e.message}`,
      )
      .join("\n");
    try {
      const path = await wailsBridge.exportLogs(text);
      if (!path) {
        toast("info", "已取消导出");
        return;
      }
      toast("success", `日志已保存：${path}`);
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "导出失败");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div>
        <h2 className="text-[20px] font-semibold text-[#242824]">运行日志</h2>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.v}
            type="button"
            onClick={() => setFilter(f.v)}
            className={cn(
              "rounded-[8px] px-3 py-1.5 text-[12px] transition-colors",
              filter === f.v ? "bg-primary text-white" : "bg-white border border-border text-muted-foreground hover:bg-[#f7faf5]",
            )}
          >
            {f.l}
          </button>
        ))}
        <input
          type="text"
          placeholder="搜索日志"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-[8px] border border-border px-3 py-1.5 text-[13px] outline-none focus:border-primary"
        />
        <button
          type="button"
          onClick={() => setAutoScroll(!autoScroll)}
          className={cn(
            "rounded-[8px] px-3 py-1.5 text-[12px] border",
            autoScroll ? "border-primary text-primary" : "border-border text-muted-foreground",
          )}
        >
          自动滚动
        </button>
        <button
          type="button"
          onClick={() => {
            if (window.confirm("确定清空日志？")) void clearLogs();
          }}
          className="flex items-center gap-1 rounded-[8px] border border-border px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-[#f7faf5]"
        >
          <Trash2 className="h-3.5 w-3.5" /> 清空
        </button>
        <button
          type="button"
          onClick={() => void exportLogs()}
          className="flex items-center gap-1 rounded-[8px] border border-border px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-[#f7faf5]"
        >
          <Download className="h-3.5 w-3.5" /> 导出
        </button>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_260px]">
        <div
          ref={scrollRef}
          className="min-h-0 overflow-auto rounded-[16px] border border-border bg-white p-4 shadow-[var(--shadow-card)] font-mono text-[12px]"
        >
          {filtered.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center py-12 text-muted-foreground">
              <FileText className="mb-2 h-8 w-8 opacity-40" />
              <p>暂无日志</p>
            </div>
          ) : (
            filtered.map((e) => (
              <div key={e.id} className="flex gap-3 border-b border-border/50 py-2 last:border-0">
                <span className="shrink-0 text-muted-foreground">{e.time || "—"}</span>
                <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium", levelColors[e.level as keyof typeof levelColors])}>
                  {LOG_LEVEL_LABELS[e.level as LogLevel]}
                </span>
                <span className="shrink-0 text-[#5c8fd8]">[{LOG_MODULE_LABELS[e.module]}]</span>
                <span className="text-[#242824]">{e.message}</span>
              </div>
            ))
          )}
        </div>

        <div className="rounded-[16px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 text-[14px] font-semibold">实时状态</h3>
          <ul className="space-y-2 text-[13px]">
            <li className="flex justify-between">
              <span className="text-muted-foreground">本地服务</span>
              <span className={localService === "ready" ? "text-primary" : localService === "manual" ? "text-warning" : "text-danger"}>
                {localService === "ready" ? "正常" : localService === "manual" ? "手动" : "异常"}
              </span>
            </li>
            <li className="flex justify-between">
              <span className="text-muted-foreground">饭饭定制</span>
              <span className={napcatOnline ? "text-primary" : "text-warning"}>
                {napcatOnline ? "在线" : "离线"}
              </span>
            </li>
            <li className="flex justify-between">
              <span className="text-muted-foreground">日志条数</span>
              <span>{entries.length}</span>
            </li>
            <li className="flex justify-between">
              <span className="text-muted-foreground">最近错误</span>
              <span className="text-danger truncate max-w-[120px]">
                {lastError}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
