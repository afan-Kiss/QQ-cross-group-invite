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
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

export function parseLogLevel(line: string): "info" | "success" | "warning" | "error" {
  if (line.includes("[�ɹ�]") || line.includes("[�ɹ�")) return "success";
  if (line.includes("[����]") || line.includes("[����")) return "warning";
  if (line.includes("[����]") || line.includes("[����")) return "error";
  return "info";
}
