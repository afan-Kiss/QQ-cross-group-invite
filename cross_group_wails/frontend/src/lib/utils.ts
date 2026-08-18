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

function extractFirstNumber(text: string): string | null {
  const m = String(text || "").match(/(\d+)/);
  return m ? m[1] : null;
}

function rewriteTimelineReason(detail: string): string {
  let text = String(detail || "").trim();
  if (!text) return "";
  if (text.includes("无法获取来源群信息") || text.includes("抓包")) {
    return "打不开来源群，没法开始邀请。请核对来源群号是否填对；如果从没从这个群往外拉过人，请先在 QQ 里手动从该群邀请一次，再回来重试。";
  }
  text = text.replace(
    /来源群信息与成员信息冲突，请重新加载成员/g,
    "来源群和这个人对不上，请重新加载成员后再试",
  );
  text = text.replace(/找不到该成员的邀请信息/g, "找不到这个人的邀请信息，先跳过");
  text = text.replace(/token/gi, "邀请信息");
  return text;
}

/** 任务时间线：只显示大白话原因，不展示英文和技术用语。 */
export function formatTimelineText(event: string, detail?: string): string {
  const ev = String(event || "").trim();
  const raw = String(detail || "").trim();
  const count = extractFirstNumber(raw);

  switch (ev) {
    case "created":
      return "任务已创建";
    case "members_loaded":
      return count ? `已加载 ${count} 名成员` : "成员已加载";
    case "started":
      return count ? `开始邀请，一共 ${count} 人` : "开始邀请";
    case "batch_start":
      return count ? `开始第 ${count} 批` : "开始下一批";
    case "rate_limited":
      return raw ? `操作太频繁，先跳过：${rewriteTimelineReason(raw)}` : "操作太频繁，先跳过";
    case "failed":
      return raw ? `邀请失败：${rewriteTimelineReason(raw)}` : "邀请失败";
    case "stopped":
      return raw && raw !== "已停止" ? `已停止：${rewriteTimelineReason(raw)}` : "已停止";
    case "completed":
      return raw && raw !== "已完成" ? rewriteTimelineReason(raw) : "已完成";
    case "error":
      return rewriteTimelineReason(raw) || "出错了，邀请没能开始";
    default:
      break;
  }

  const rewritten = rewriteTimelineReason(raw);
  if (rewritten && !/^[a-z][a-z0-9_]*$/i.test(rewritten) && !/^[a-z_]+=/i.test(rewritten)) {
    return rewritten;
  }
  if (ev) {
    if (ev === "error") return "出错了，邀请没能开始";
    return "任务有更新";
  }
  return rewritten || "任务有更新";
}
