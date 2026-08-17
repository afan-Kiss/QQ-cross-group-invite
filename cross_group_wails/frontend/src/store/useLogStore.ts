import { create } from "zustand";

export type LogLevel = "INFO" | "SUCCESS" | "WARN" | "ERROR";
export type LogModule = "SERVICE" | "NAPCAT" | "MEMBERS" | "INVITE" | "TOKEN" | "SYSTEM";

export interface LogEntry {
  id: string;
  time: string;
  level: LogLevel;
  module: LogModule;
  message: string;
}

let logId = 0;

function parseLogLine(line: string): LogEntry | null {
  const match = line.match(/^(\d{2}:\d{2}:\d{2})\s*(.*)$/);
  const time = match?.[1] ?? new Date().toLocaleTimeString("zh-CN", { hour12: false });
  const body = match?.[2] ?? line;
  let level: LogLevel = "INFO";
  if (/成功|SUCCESS/i.test(body)) level = "SUCCESS";
  else if (/WARN|警告|频繁/i.test(body)) level = "WARN";
  else if (/ERROR|失败|错误/i.test(body)) level = "ERROR";
  let module: LogModule = "SYSTEM";
  if (/NapCat|napcat/i.test(body)) module = "NAPCAT";
  else if (/成员|member/i.test(body)) module = "MEMBERS";
  else if (/邀请|invite/i.test(body)) module = "INVITE";
  else if (/token/i.test(body)) module = "TOKEN";
  else if (/服务|service/i.test(body)) module = "SERVICE";
  return {
    id: `log-${++logId}`,
    time,
    level,
    module,
    message: body.replace(/token[=:]\S+/gi, "token=***"),
  };
}

interface LogStore {
  entries: LogEntry[];
  autoScroll: boolean;
  setFromRaw: (lines: string[]) => void;
  add: (entry: Omit<LogEntry, "id">) => void;
  clear: () => void;
  setAutoScroll: (v: boolean) => void;
}

export const useLogStore = create<LogStore>((set) => ({
  entries: [],
  autoScroll: true,
  setFromRaw: (lines) => {
    const entries = lines.map((line) => parseLogLine(line)).filter(Boolean) as LogEntry[];
    set({ entries });
  },
  add: (entry) =>
    set((s) => ({
      entries: [...s.entries, { ...entry, id: `log-${++logId}` }].slice(-500),
    })),
  clear: () => set({ entries: [] }),
  setAutoScroll: (v) => set({ autoScroll: v }),
}));
