export type MemberRole = "owner" | "admin" | "member";

export type MemberStatus =
  | "success"
  | "filtered"
  | "rate_limited"
  | "failed"
  | "waiting"
  | "inviting";

export interface InviteConfig {
  target_group_id: string;
  source_group_id: string;
  batch_count: string;
  interval_ms: string;
  filter_staff: boolean;
}

export interface Member {
  qq: number;
  nickname: string;
  role: MemberRole;
  status: MemberStatus;
  card?: string;
  token?: string;
  filterReason?: string;
  failReason?: string;
}

export interface RateLimitRecord {
  qq: number;
  nickname: string;
  at: number;
  reason?: string;
}

export interface FailedRecord {
  qq: number;
  nickname: string;
  reason: string;
  at: number;
}

export interface InviteStats {
  total: number;
  completed: number;
  success: number;
  rate_limited: number;
  failed: number;
  waiting: number;
  inviting: number;
}

export interface BatchProgress {
  batchNumber: number;
  batchTotal: number;
  batchDone: number;
  currentNickname: string;
  currentQq: number;
  intervalRemainingMs: number;
}

export interface InviteStatus {
  running: boolean;
  total: number;
  done: number;
  success: number;
  current_qq: number;
  current_nickname: string;
  message: string;
  frequent: RateLimitRecord[];
  errors: FailedRecord[];
  logs: string[];
}

export interface AppStatus extends InviteStats {
  running: boolean;
  logs: string[];
  rate_limit_list: RateLimitRecord[];
  failed_list: FailedRecord[];
  members: Member[];
  current_qq: number;
  current_nickname: string;
  message: string;
  napcat_online?: boolean;
  napcat_message?: string;
  batch: BatchProgress;
}

export interface LoadMembersResponse {
  count: number;
  members: Array<{
    qq: number;
    nickname: string;
    role: string;
    card?: string;
    token?: string;
  }>;
}

export interface HealthResponse {
  ok: boolean;
  service: string;
  version?: string;
  napcat_online: boolean;
  napcat_message: string;
}

export interface BootstrapStatus {
  localService: "booting" | "ready" | "error" | "port_conflict";
  message: string;
  startedByUs: boolean;
  napcatOnline: boolean;
  napcatMessage: string;
}

export interface ChartPoint {
  time: string;
  success: number;
  failed: number;
  rateLimited: number;
}
