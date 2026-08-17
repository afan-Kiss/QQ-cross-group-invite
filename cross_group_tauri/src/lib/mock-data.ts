import type {
  BatchProgress,
  ChartPoint,
  FailedRecord,
  InviteConfig,
  Member,
  RateLimitRecord,
} from "./types";

export const mockConfig: InviteConfig = {
  target_group_id: "",
  source_group_id: "",
  batch_count: "20",
  interval_ms: "1500",
  filter_staff: true,
};

export const mockStats = {
  total: 1258,
  completed: 842,
  success: 718,
  rate_limited: 86,
  failed: 38,
  waiting: 416,
  inviting: 28,
};

export const mockBatch: BatchProgress = {
  batchNumber: 43,
  batchTotal: 20,
  batchDone: 18,
  currentNickname: "�ǳ���",
  currentQq: 246813579,
  intervalRemainingMs: 1120,
};

export const mockMembers: Member[] = [
  {
    qq: 123456789,
    nickname: "�����Ա�",
    role: "owner",
    status: "success",
  },
  {
    qq: 987654321,
    nickname: "�������",
    role: "admin",
    status: "filtered",
    filterReason: "����Ա",
  },
  {
    qq: 246813579,
    nickname: "�ǳ���",
    role: "member",
    status: "rate_limited",
  },
  {
    qq: 112233445,
    nickname: "���¾���",
    role: "member",
    status: "failed",
    failReason: "�Է������˼���Ȩ��",
  },
  {
    qq: 556677889,
    nickname: "һЦ�κ�",
    role: "member",
    status: "waiting",
  },
  {
    qq: 998877665,
    nickname: "ǳЦ��Ȼ",
    role: "member",
    status: "waiting",
  },
];

export const mockLogs: string[] = [
  "[11:23:15] [��Ϣ] ��Ա�б�������ɣ��� 1,258 �ˣ����˺���Ч 1,218 �ˣ�",
  "[11:23:20] [��Ϣ] ��ʼ���룬����������20�������1500ms������Ⱥ��/����Ա������",
  "[11:23:21] [�ɹ�] ����ɹ��������Ա� (123456789)",
  "[11:23:23] [��Ϣ] ��������Ա��������� (987654321)",
  "[11:23:24] [����] Ƶ�����ƣ��ǳ��� (246813579)�����������Զ���",
  "[11:23:26] [����] ����ʧ�ܣ����¾��� (112233445)��ԭ�򣺶Է������˼���Ȩ��",
  "[11:23:28] [��Ϣ] �� 43 ��������ɣ��ɹ� 12��Ƶ������ 3��ʧ�� 1",
  "[11:23:28] [��Ϣ] �ȴ� 1500 ms �������һ��...",
];

export const mockRateLimitList: RateLimitRecord[] = [
  { qq: 246813579, nickname: "�ǳ���", at: Date.now() / 1000 - 300 },
  { qq: 135792468, nickname: "�����ƽ�", at: Date.now() / 1000 - 240 },
  { qq: 192837465, nickname: "�Ϸ�֪��", at: Date.now() / 1000 - 180 },
  { qq: 564738291, nickname: "�Ƶ�����", at: Date.now() / 1000 - 120 },
  { qq: 314159265, nickname: "��������", at: Date.now() / 1000 - 60 },
];

export const mockFailedList: FailedRecord[] = [
  {
    qq: 112233445,
    nickname: "���¾���",
    reason: "�Է������˼���Ȩ��",
    at: Date.now() / 1000,
  },
  {
    qq: 223344556,
    nickname: "ƽ��ϲ��",
    reason: "��Ҫ��֤��Ϣ",
    at: Date.now() / 1000,
  },
  {
    qq: 334455667,
    nickname: "����΢��",
    reason: "Ⱥ����",
    at: Date.now() / 1000,
  },
  {
    qq: 445566778,
    nickname: "ʱ������",
    reason: "��Ҫ��֤��Ϣ",
    at: Date.now() / 1000,
  },
  {
    qq: 556677889,
    nickname: "ǳЦ��Ȼ",
    reason: "�Է������˼���Ȩ��",
    at: Date.now() / 1000,
  },
];

export const mockChartData: ChartPoint[] = [
  { time: "11:20", success: 12, failed: 1, rateLimited: 2 },
  { time: "11:21", success: 18, failed: 0, rateLimited: 1 },
  { time: "11:22", success: 15, failed: 2, rateLimited: 3 },
  { time: "11:23", success: 22, failed: 1, rateLimited: 2 },
  { time: "11:24", success: 19, failed: 0, rateLimited: 4 },
  { time: "11:25", success: 24, failed: 1, rateLimited: 1 },
];
