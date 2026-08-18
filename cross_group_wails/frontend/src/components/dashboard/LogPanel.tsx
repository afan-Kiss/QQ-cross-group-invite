import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { parseLogLevel } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";
import { wailsBridge } from "@/lib/wails-bridge";
import { toast } from "@/store/useToastStore";

const levelClass = {
  info: "text-[#6b7a8f]",
  success: "text-primary",
  warning: "text-[#d49a12]",
  error: "text-danger",
};

export function LogPanel() {
  const logs = useInviteStore((s) => s.logs);
  const autoScrollLogs = useInviteStore((s) => s.autoScrollLogs);
  const setAutoScrollLogs = useInviteStore((s) => s.setAutoScrollLogs);
  const clearLogs = useInviteStore((s) => s.clearLogs);
  const serviceReady = useServiceStore((s) => s.localService === "ready");
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScrollLogs && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScrollLogs]);

  const exportLogs = async () => {
    try {
      const stamp = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      const name = `QQ跨群邀请工具日志_${stamp.getFullYear()}${pad(stamp.getMonth() + 1)}${pad(stamp.getDate())}_${pad(stamp.getHours())}${pad(stamp.getMinutes())}${pad(stamp.getSeconds())}.txt`;
      const content = logs.join("\n");
      const path = await wailsBridge.exportLogs(content);
      if (path) toast("success", `已导出到 ${path}`);
      else {
        // fallback download when not in wails or cancelled
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
        toast("success", "日志已导出");
      }
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "导出失败");
    }
  };

  return (
    <div className="animate-fade-up flex h-full min-h-0 flex-col overflow-hidden rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-[#2f352d]">运行日志</h3>
        <div className="flex shrink-0 items-center gap-3 text-[12px] text-muted-foreground">
          <span>
            本地服务{" "}
            <span className={serviceReady ? "text-primary" : "text-danger"}>
              ● {serviceReady ? "正常" : "异常"}
            </span>
          </span>
          <span>
            饭饭定制{" "}
            <span className={napcatOnline ? "text-primary" : "text-warning"}>
              ● {napcatOnline ? "在线" : "离线"}
            </span>
          </span>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-auto rounded-[12px] border border-border bg-[#fafbf9] p-3 font-mono text-[12px] leading-6"
      >
        {logs.length === 0 && (
          <div className="text-muted-foreground">暂无日志</div>
        )}
        {logs.map((line, i) => {
          const level = parseLogLevel(line);
          return (
            <div key={`${line}-${i}`} className={levelClass[level]}>
              {line}
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <Checkbox
            checked={autoScrollLogs}
            onCheckedChange={(v) => setAutoScrollLogs(Boolean(v))}
          />
          自动滚动
        </label>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => void clearLogs()}>
            清空日志
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void exportLogs()}>
            导出日志
          </Button>
        </div>
      </div>
    </div>
  );
}
