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

export const LOG_LEVEL_LABELS: Record<LogLevel, string> = {
  INFO: "信息",
  SUCCESS: "成功",
  WARN: "警告",
  ERROR: "错误",
};

export const LOG_MODULE_LABELS: Record<LogModule, string> = {
  SERVICE: "服务",
  NAPCAT: "饭饭定制",
  MEMBERS: "成员",
  INVITE: "邀请",
  TOKEN: "邀请信息",
  SYSTEM: "系统",
};

let logId = 0;

const TIME_PREFIX = /^(?:\[(\d{2}:\d{2}:\d{2})\]|(\d{2}:\d{2}:\d{2}))\s*(.*)$/;

export function parseLogLine(line: string): LogEntry | null {
  const raw = String(line ?? "").replace(/\s+$/, "");
  if (!raw.trim()) return null;
  const match = raw.match(TIME_PREFIX);
  const time = match?.[1] || match?.[2] || "";
  const body = (match?.[3] ?? raw).trim();
  let level: LogLevel = "INFO";
  if (/成功|SUCCESS/i.test(body)) level = "SUCCESS";
  else if (/WARN|警告|频繁/i.test(body)) level = "WARN";
  else if (/ERROR|失败|错误|异常/i.test(body)) level = "ERROR";
  let module: LogModule = "SYSTEM";
  if (/饭饭定制|NapCat|napcat/i.test(body)) module = "NAPCAT";
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
    set((s) => {
      const prevByKey = new Map<string, string>();
      for (const e of s.entries) {
        if (e.time && e.message) prevByKey.set(e.message, e.time);
      }
      const entries: LogEntry[] = [];
      for (const line of lines) {
        const parsed = parseLogLine(line);
        if (!parsed) continue;
        if (!parsed.time) parsed.time = prevByKey.get(parsed.message) ?? "";
        entries.push(parsed);
      }
      return { entries };
    });
  },
  add: (entry) =>
    set((s) => ({
      entries: [...s.entries, { ...entry, id: `log-${++logId}` }].slice(-500),
    })),
  clear: () => set({ entries: [] }),
  setAutoScroll: (v) => set({ autoScroll: v }),
}));
