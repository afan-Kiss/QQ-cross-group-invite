export type MemberRole = "owner" | "admin" | "member" | "unknown";

export type MemberStatus =
  | "success"
  | "filtered"
  | "rate_limited"
  | "failed"
  | "waiting"
  | "inviting";

export type TaskRunStatus =
  | "idle"
  | "preparing"
  | "running"
  | "stopping"
  | "stopped"
  | "completed"
  | "error"
  | "interrupted";

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
  /** Raw token never leaves Python backend; kept empty on purpose. */
  token?: string;
  has_token?: boolean;
  filterReason?: string;
  failReason?: string;
  startedAt?: number;
  finishedAt?: number;
  durationMs?: number;
  sourceGroupId?: string;
}

export interface InviteResult {
  qq: number;
  nickname: string;
  status: MemberStatus;
  reason: string;
  started_at: number;
  finished_at: number;
  duration_ms: number;
}

export interface RateLimitRecord {
  qq: number;
  nickname: string;
  at: number;
  reason?: string;
  source_group_id?: string;
  target_group_id?: string;
  task_id?: string;
}

export interface FailedRecord {
  qq: number;
  nickname: string;
  reason: string;
  at: number;
  source_group_id?: string;
  target_group_id?: string;
  task_id?: string;
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
  totalBatches: number;
  currentNickname: string;
  currentQq: number;
  intervalRemainingMs: number;
  intervalMs: number;
  nextInviteAt: number;
}

export interface RateSeriesPoint {
  timestamp: number;
  success: number;
  failed: number;
  rate_limited: number;
  total: number;
}

export interface AppStatus extends InviteStats {
  running: boolean;
  status: TaskRunStatus;
  task_id: string;
  source_group_id?: string;
  target_group_id?: string;
  logs: string[];
  rate_limit_list: RateLimitRecord[];
  failed_list: FailedRecord[];
  results: InviteResult[];
  rate_series: RateSeriesPoint[];
  members: Member[];
  current_qq: number;
  current_nickname: string;
  message: string;
  error_message: string;
  started_at: number;
  finished_at: number;
  napcat_online?: boolean;
  napcat_message?: string;
  batch: BatchProgress;
}

export interface LoadMembersResponse {
  ok?: boolean;
  count: number;
  eligible?: number;
  filtered?: number;
  members: Array<{
    qq: number;
    nickname: string;
    role: string;
    card?: string;
    token?: string;
    has_token?: boolean;
    eligible?: boolean;
    filter_reason?: string;
  }>;
}

export interface HealthResponse {
  ok: boolean;
  service: string;
  version?: string;
  session_required?: boolean;
  session_match?: boolean;
  pid?: number;
  napcat_online: boolean;
  napcat_message: string;
}

export interface BootstrapStatus {
  localService: "booting" | "ready" | "error" | "port_conflict" | "manual";
  message: string;
  startedByUs: boolean;
  napcatOnline: boolean;
  napcatMessage: string;
  appSession?: string;
  /** Non-secret backend identity: service:version:pid */
  backendInstance?: string;
  backendPid?: number;
  backendVersion?: string;
}

export interface ChartPoint {
  time: string;
  success: number;
  failed: number;
  rateLimited: number;
  total: number;
}

export interface PersistedTask {
  id: string;
  source_group_id: number | string;
  target_group_id: number | string;
  created_at?: number;
  started_at: number;
  finished_at?: number;
  status: string;
  selected_count?: number;
  total: number;
  success: number;
  rate_limited: number;
  failed: number;
  batch_size?: number;
  interval_ms?: number;
  stop_reason?: string;
  error_message?: string;
  timeline?: Array<{ at: number; event: string; detail?: string }>;
}
