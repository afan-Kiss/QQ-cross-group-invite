import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

export function formatPercent(value: number, total: number): string {
  if (total <= 0) return "0.00%";
  return `${((value / total) * 100).toFixed(2)}%`;
}

export function formatTime(ts: number): string {
  if (!ts) return "\u2014";
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

export function formatDateTime(ts: number): string {
  if (!ts) return "\u2014";
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  return d.toLocaleString("zh-CN", { hour12: false });
}

export function formatDurationMs(ms: number): string {
  if (!ms || ms < 0) return "\u2014";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} \u79d2`;
}

export function maskToken(token: string | undefined): string {
  if (!token) return "\u2014";
  if (token.length <= 8) return "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";
  return `${token.slice(0, 4)}\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022${token.slice(-4)}`;
}

export function parseLogLevel(line: string): "info" | "success" | "warning" | "error" {
  if (line.includes("\u6210\u529f")) return "success";
  if (line.includes("\u9891\u7e41") || line.includes("\u8b66\u544a")) return "warning";
  if (line.includes("\u5931\u8d25") || line.includes("\u5f02\u5e38") || line.includes("\u9519\u8bef")) return "error";
  return "info";
}

export function hasMojibake(text: string): boolean {
  return text.includes("\uFFFD");
}
