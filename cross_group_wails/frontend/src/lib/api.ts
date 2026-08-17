/** 开发环境可手动设置 VITE_USE_MOCK=true */
export const USE_MOCK_API =
  import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === "true";

export const API_BASE_URL = "http://127.0.0.1:17888";
export const SERVICE_ID = "cross-group-invite";

import type {
  AppStatus,
  HealthResponse,
  InviteConfig,
  LoadMembersResponse,
  Member,
  MemberRole,
  MemberStatus,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code:
      | "network"
      | "backend"
      | "port_conflict"
      | "service_mismatch" = "backend",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
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

  if (!res.ok) {
    throw new ApiError(String(data.error ?? `请求失败: ${res.status}`), "backend");
  }
  return data as T;
}

export function validateHealthPayload(data: HealthResponse): HealthResponse {
  if (!data.ok) {
    throw new ApiError("后端服务异常", "backend");
  }
  if (data.service !== SERVICE_ID) {
    throw new ApiError(
      `17888 端口被占用（service=${data.service ?? "unknown"}）`,
      "port_conflict",
    );
  }
  return data;
}

function mapRole(role: string): MemberRole {
  if (role === "owner") return "owner";
  if (role === "admin") return "admin";
  return "member";
}

function mapBackendStatus(
  member: Member,
  running: boolean,
  currentQq: number,
  frequentQqs: Set<number>,
  errorQqs: Map<number, string>,
): MemberStatus {
  if (member.status !== "waiting") return member.status;
  if (frequentQqs.has(member.qq)) return "rate_limited";
  if (errorQqs.has(member.qq)) return "failed";
  if (running && currentQq === member.qq) return "inviting";
  return "waiting";
}

function normalizeStatus(raw: Record<string, unknown>, members: Member[]): AppStatus {
  const total = Number(raw.total ?? 0);
  const done = Number(raw.done ?? raw.completed ?? 0);
  const success = Number(raw.success ?? 0);
  const frequent = (raw.frequent ?? raw.rate_limit_list ?? []) as Array<{
    qq: number;
    nickname: string;
    reason?: string;
    at: number;
  }>;
  const errors = (raw.errors ?? raw.failed_list ?? []) as Array<{
    qq: number;
    nickname: string;
    reason: string;
    at: number;
  }>;
  const running = Boolean(raw.running);
  const currentQq = Number(raw.current_qq ?? 0);
  const frequentQqs = new Set(frequent.map((x) => x.qq));
  const errorQqs = new Map(errors.map((x) => [x.qq, x.reason]));
  const batchCount = Number(raw.batch_count ?? 20) || 20;

  const mergedMembers =
    members.length > 0
      ? members.map((m) => ({
          ...m,
          status: mapBackendStatus(m, running, currentQq, frequentQqs, errorQqs),
          failReason: errorQqs.get(m.qq),
        }))
      : [];

  return {
    running,
    total,
    completed: done,
    success,
    rate_limited: frequent.length,
    failed: errors.length,
    waiting: Math.max(0, total - done),
    inviting: running && currentQq > 0 ? 1 : 0,
    logs: (raw.logs as string[]) ?? [],
    rate_limit_list: frequent,
    failed_list: errors,
    members: mergedMembers,
    current_qq: currentQq,
    current_nickname: String(raw.current_nickname ?? ""),
    message: String(raw.message ?? ""),
    napcat_online: Boolean(raw.napcat_online),
    napcat_message: String(raw.napcat_message ?? ""),
    batch: {
      batchNumber: Math.max(1, Math.ceil(done / batchCount)),
      batchTotal: batchCount,
      batchDone: done % batchCount || (done > 0 ? batchCount : 0),
      currentNickname: String(raw.current_nickname ?? ""),
      currentQq,
      intervalRemainingMs: running ? 1120 : 0,
    },
  };
}

export const api = {
  async health(): Promise<HealthResponse> {
    const data = await request<HealthResponse>("/health");
    return validateHealthPayload(data);
  },

  async getConfig(): Promise<InviteConfig> {
    return request("/config");
  },

  async saveConfig(config: InviteConfig): Promise<void> {
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
    count: number;
    interval_ms: number;
    filter_staff: boolean;
    qq_list?: number[];
  }): Promise<void> {
    await request("/invite/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async stopInvite(): Promise<void> {
    await request("/invite/stop", { method: "POST", body: JSON.stringify({}) });
  },

  async getStatus(members: Member[] = []): Promise<AppStatus> {
    const raw = await request<Record<string, unknown>>("/status");
    return normalizeStatus(raw, members);
  },

  mapLoadedMembers(
    rows: LoadMembersResponse["members"],
    filterStaff: boolean,
  ): Member[] {
    return rows.map((m) => {
      const role = mapRole(m.role);
      const isStaff = role === "owner" || role === "admin";
      let status: MemberStatus = "waiting";
      let filterReason: string | undefined;
      if (filterStaff && isStaff) {
        status = "filtered";
        filterReason = role === "owner" ? "群主" : "管理员";
      }
      return {
        qq: m.qq,
        nickname: m.nickname,
        role,
        status,
        card: m.card,
        token: m.token,
        filterReason,
      };
    });
  },
};
