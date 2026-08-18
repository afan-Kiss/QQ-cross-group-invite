export const USE_MOCK_API = false;

export const API_BASE_URL = "http://127.0.0.1:17888";
export const SERVICE_ID = "cross-group-invite";

import { toEpochMs } from "@/lib/utils";
import { useServiceStore } from "@/store/useServiceStore";
import type {
  AppStatus,
  HealthResponse,
  InviteConfig,
  InviteResult,
  LoadMembersResponse,
  Member,
  MemberRole,
  MemberStatus,
  PersistedTask,
  RateSeriesPoint,
  TaskRunStatus,
} from "./types";

export type ApiErrorCode =
  | "network"
  | "backend"
  | "port_conflict"
  | "service_mismatch"
  | "INVALID_ARGUMENT"
  | "NAPCAT_OFFLINE"
  | "PORT_CONFLICT"
  | "MEMBER_NOT_FOUND"
  | "TOKEN_MISSING"
  | "RATE_LIMITED"
  | "TASK_RUNNING"
  | "TASK_NOT_RUNNING"
  | "INTERNAL_ERROR"
  | "UNAUTHORIZED"
  | string;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: ApiErrorCode = "backend",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((init?.headers as Record<string, string> | undefined) ?? {}),
    };
    const session = useServiceStore.getState().appSession || "";
    // Owned mode: attach session on all business GET/POST (never log/store session).
    if (session) {
      headers["X-App-Session"] = session;
    }
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError("后端服务未连接，请确认本地服务已启动", "network");
  }

  let data: Record<string, unknown> = {};
  try {
    data = (await res.json()) as Record<string, unknown>;
  } catch {
    if (!res.ok) {
      throw new ApiError(`后端响应异常 (${res.status})`, "backend");
    }
  }

  if (!res.ok || data.ok === false) {
    const code = String(data.code ?? "backend");
    const message = String(data.message ?? data.error ?? `请求失败: ${res.status}`);
    throw new ApiError(message, code);
  }
  return data as T;
}

export function validateHealthPayload(data: HealthResponse): HealthResponse {
  if (!data.ok) {
    throw new ApiError("后端服务异常", "backend");
  }
  if (!data.service || data.service !== SERVICE_ID) {
    throw new ApiError(
      `端口 17888 已被其他程序占用（service=${data.service ?? "unknown"}）`,
      "port_conflict",
    );
  }
  return data;
}

function mapRole(role: string): MemberRole {
  if (role === "owner") return "owner";
  if (role === "admin") return "admin";
  if (role === "unknown") return "unknown";
  return "member";
}

function mapResultStatus(status: string): MemberStatus {
  const allowed: MemberStatus[] = [
    "waiting",
    "inviting",
    "success",
    "rate_limited",
    "failed",
    "filtered",
  ];
  return (allowed.includes(status as MemberStatus) ? status : "waiting") as MemberStatus;
}

export function applyResultsToMembers(
  members: Member[],
  results: InviteResult[],
): Member[] {
  if (!results.length) return members;
  const byQq = new Map(results.map((r) => [r.qq, r]));
  return members.map((m) => {
    const r = byQq.get(m.qq);
    if (!r) return m;
    return {
      ...m,
      status: mapResultStatus(r.status),
      failReason: r.reason || m.failReason,
      startedAt: r.started_at || m.startedAt,
      finishedAt: r.finished_at || m.finishedAt,
      durationMs: r.duration_ms || m.durationMs,
    };
  });
}

export function normalizeStatus(
  raw: Record<string, unknown>,
  members: Member[] = [],
): AppStatus {
  const total = Number(raw.total ?? 0);
  const done = Number(raw.done ?? raw.completed ?? 0);
  const success = Number(raw.success ?? 0);
  const frequent = ((raw.frequent ?? raw.rate_limit_list ?? []) as Array<Record<string, unknown>>).map((r) => ({
    qq: Number(r.qq ?? 0),
    nickname: String(r.nickname ?? ""),
    reason: r.reason != null ? String(r.reason) : undefined,
    at: toEpochMs(r.at as number),
    source_group_id: r.source_group_id != null ? String(r.source_group_id) : undefined,
    target_group_id: r.target_group_id != null ? String(r.target_group_id) : undefined,
    task_id: r.task_id != null ? String(r.task_id) : undefined,
  }));
  const errors = ((raw.errors ?? raw.failed_list ?? []) as Array<Record<string, unknown>>).map((r) => ({
    qq: Number(r.qq ?? 0),
    nickname: String(r.nickname ?? ""),
    reason: String(r.reason ?? ""),
    at: toEpochMs(r.at as number),
    source_group_id: r.source_group_id != null ? String(r.source_group_id) : undefined,
    target_group_id: r.target_group_id != null ? String(r.target_group_id) : undefined,
    task_id: r.task_id != null ? String(r.task_id) : undefined,
  }));
  const results = ((raw.results ?? []) as InviteResult[]).map((r) => ({
    ...r,
    status: mapResultStatus(String(r.status)),
  }));
  const rateSeries = (raw.rate_series ?? []) as RateSeriesPoint[];
  const running = Boolean(raw.running);
  const currentQq = Number(raw.current_qq ?? 0);
  const batchSize = Number(raw.batch_size ?? raw.batch_count ?? 20) || 20;
  const batchNumber = Number(raw.batch_number ?? 0);
  const batchDone = Number(raw.batch_done ?? 0);
  const totalBatches = Number(raw.total_batches ?? 0);
  const intervalMs = Number(raw.interval_ms ?? 0);
  const nextInviteAt = Number(raw.next_invite_at ?? 0);
  const intervalRemainingMs = Number(
    raw.interval_remaining_ms ??
      (running && nextInviteAt > Date.now() / 1000
        ? Math.max(0, (nextInviteAt - Date.now() / 1000) * 1000)
        : 0),
  );
  const status = String(raw.status ?? (running ? "running" : "idle")) as TaskRunStatus;

  // Do NOT merge results into members here. Ownership/task matching belongs in the store.

  const waitingFromResults = results.filter((r) => r.status === "waiting").length;
  const invitingFromResults = results.filter((r) => r.status === "inviting").length;

  return {
    running,
    status,
    task_id: String(raw.task_id ?? ""),
    source_group_id: raw.source_group_id != null ? String(raw.source_group_id) : "",
    target_group_id: raw.target_group_id != null ? String(raw.target_group_id) : "",
    total,
    completed: done,
    success,
    rate_limited: Number(raw.rate_limited_count ?? raw.rate_limited ?? frequent.length),
    failed: Number(raw.failed_count ?? raw.failed ?? errors.length),
    waiting: results.length ? waitingFromResults : Math.max(0, total - done),
    inviting: results.length ? invitingFromResults : running && currentQq > 0 ? 1 : 0,
    logs: (raw.logs as string[]) ?? [],
    rate_limit_list: frequent,
    failed_list: errors,
    results,
    rate_series: rateSeries,
    members,
    current_qq: running ? currentQq : 0,
    current_nickname: running ? String(raw.current_nickname ?? "") : "",
    message: String(raw.message ?? ""),
    error_message: String(raw.error_message ?? ""),
    started_at: Number(raw.started_at ?? 0),
    finished_at: Number(raw.finished_at ?? 0),
    napcat_online: Boolean(raw.napcat_online),
    napcat_message: String(raw.napcat_message ?? ""),
    timeline: Array.isArray(raw.timeline)
      ? (raw.timeline as Array<{ at?: number; event?: string; detail?: string }>).map((ev) => ({
          at: Number(ev.at || 0),
          event: String(ev.event || ""),
          detail: ev.detail != null ? String(ev.detail) : undefined,
        }))
      : [],
    batch: {
      batchNumber,
      batchTotal: Number(raw.batch_total_count ?? batchSize) || batchSize,
      batchDone,
      totalBatches,
      currentNickname: running ? String(raw.current_nickname ?? "") : "",
      currentQq: running ? currentQq : 0,
      intervalRemainingMs: running ? intervalRemainingMs : 0,
      intervalMs,
      nextInviteAt,
    },
  };
}

export const api = {
  async health(): Promise<HealthResponse> {
    const data = await request<HealthResponse>("/health");
    return validateHealthPayload(data);
  },

  async getConfig(): Promise<InviteConfig> {
    const data = await request<InviteConfig & { ok?: boolean }>("/config");
    return {
      target_group_id: String(data.target_group_id ?? ""),
      source_group_id: String(data.source_group_id ?? ""),
      batch_count: String(data.batch_count ?? "20"),
      interval_ms: String(data.interval_ms ?? "1500"),
      filter_staff: Boolean(data.filter_staff ?? true),
    };
  },

  async saveConfig(config: InviteConfig | (InviteConfig & Record<string, unknown>)): Promise<void> {
    await request("/config", { method: "POST", body: JSON.stringify(config) });
  },

  async loadMembers(payload: {
    source_group_id: string;
    filter_staff: boolean;
  }): Promise<LoadMembersResponse> {
    return request("/members/load", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async startInvite(payload: {
    target_group_id: string;
    source_group_id: string;
    batch_count: number;
    interval_ms: number;
    filter_staff: boolean;
    qq_list: number[];
  }): Promise<{ task_id?: string }> {
    return request("/invite/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async stopInvite(taskId?: string): Promise<void> {
    const body = taskId ? { task_id: taskId } : {};
    await request("/invite/stop", { method: "POST", body: JSON.stringify(body) });
  },

  async getStatus(members: Member[] = []): Promise<AppStatus> {
    const raw = await request<Record<string, unknown>>("/status");
    return normalizeStatus(raw, members);
  },

  async clearLogs(): Promise<void> {
    await request("/state/clear-logs", { method: "POST", body: "{}" });
  },

  async clearFailed(): Promise<void> {
    await request("/state/clear-failed", { method: "POST", body: "{}" });
  },

  async clearRateLimits(): Promise<void> {
    await request("/state/clear-rate-limits", { method: "POST", body: "{}" });
  },

  async listTasks(): Promise<PersistedTask[]> {
    const data = await request<{ tasks: PersistedTask[] }>("/tasks");
    return data.tasks ?? [];
  },

  async getTask(id: string): Promise<PersistedTask | null> {
    try {
      const data = await request<{ task: PersistedTask }>(`/tasks/${encodeURIComponent(id)}`);
      return data.task ?? null;
    } catch (e) {
      if (e instanceof ApiError && (e.code === "MEMBER_NOT_FOUND" || e.message.includes("不存在"))) {
        return null;
      }
      throw e;
    }
  },

  async testConnection(payload?: {
    onebot_url?: string;
    napcat_webui_token?: string;
  }): Promise<void> {
    await request("/test-connection", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  async refreshNapcat(): Promise<{ napcat_online: boolean; napcat_message: string }> {
    const data = await request<{ napcat_online?: boolean; napcat_message?: string }>("/napcat/refresh", {
      method: "POST",
      body: "{}",
    });
    return {
      napcat_online: Boolean(data.napcat_online),
      napcat_message: String(data.napcat_message ?? ""),
    };
  },

  mapLoadedMembers(
    rows: LoadMembersResponse["members"],
    filterStaff: boolean,
  ): Member[] {
    return rows.map((m) => {
      const role = mapRole(m.role);
      const isStaff = role === "owner" || role === "admin";
      const backendFiltered = m.eligible === false || Boolean(m.filter_reason);
      const shouldFilter = backendFiltered || (filterStaff && isStaff);
      let status: MemberStatus = "waiting";
      let filterReason: string | undefined = m.filter_reason || undefined;
      if (shouldFilter) {
        status = "filtered";
        if (!filterReason) {
          filterReason = role === "owner" ? "群主" : "管理员";
        }
      }
      return {
        qq: m.qq,
        nickname: m.nickname,
        role,
        status,
        card: m.card,
        token: "",
        has_token: Boolean(m.has_token ?? m.token),
        filterReason,
      };
    });
  },
};
