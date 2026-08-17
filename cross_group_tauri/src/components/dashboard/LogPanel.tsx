import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { parseLogLevel } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

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
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScrollLogs && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScrollLogs]);

  return (
    <div className="animate-fade-up flex h-full min-h-[220px] flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-3 text-[15px] font-semibold text-[#2f352d]">������־</h3>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-auto rounded-[12px] border border-border bg-[#fafbf9] p-3 font-mono text-[12px] leading-6"
      >
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
          �Զ�����
        </label>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={clearLogs}>
            �����־
          </Button>
          <Button variant="secondary" size="sm">
            ������־
          </Button>
        </div>
      </div>
    </div>
  );
}
