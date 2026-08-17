import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Normalize epoch seconds or milliseconds to milliseconds. */
export function toEpochMs(value: number | string | null | undefined): number {
  if (value == null || value === "") return 0;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return 0;
    return value > 0 && value < 1e12 ? Math.round(value * 1000) : Math.round(value);
  }
  const n = Number(value);
  if (Number.isFinite(n)) {
    return n > 0 && n < 1e12 ? Math.round(n * 1000) : Math.round(n);
  }
  const t = Date.parse(String(value));
  return Number.isFinite(t) ? t : 0;
}

export function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

export function formatPercent(value: number, total: number): string {
  if (total <= 0) return "0.00%";
  return `${((value / total) * 100).toFixed(2)}%`;
}

export function formatTime(ts: number): string {
  const ms = toEpochMs(ts);
  if (!ms) return "—";
  return new Date(ms).toLocaleTimeString("zh-CN", { hour12: false });
}

export function formatDateTime(ts: number): string {
  const ms = toEpochMs(ts);
  if (!ms) return "—";
  return new Date(ms).toLocaleString("zh-CN", { hour12: false });
}

export function formatDurationMs(ms: number): string {
  if (!ms || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} 秒`;
}

export function maskToken(token: string | undefined): string {
  if (!token) return "—";
  if (token.length <= 8) return "••••••••";
  return `${token.slice(0, 4)}••••••••••${token.slice(-4)}`;
}

export function parseLogLevel(line: string): "info" | "success" | "warning" | "error" {
  if (line.includes("成功")) return "success";
  if (line.includes("频繁") || line.includes("警告")) return "warning";
  if (line.includes("失败") || line.includes("异常") || line.includes("错误")) return "error";
  return "info";
}

export function hasMojibake(text: string): boolean {
  return text.includes(String.fromCharCode(0xfffd)) || /\?\?\?/.test(text);
}
