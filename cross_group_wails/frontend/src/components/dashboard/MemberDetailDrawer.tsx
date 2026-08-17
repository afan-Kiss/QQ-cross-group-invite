import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { formatDateTime, formatDurationMs } from "@/lib/utils";
import { toast } from "@/store/useToastStore";
import { useSettingsStore } from "@/store/useSettingsStore";

const roleLabel = { owner: "群主", admin: "管理员", member: "成员", unknown: "未知" } as const;
const statusLabel = {
  success: "邀请成功",
  filtered: "已过滤",
  rate_limited: "频繁限制",
  failed: "邀请失败",
  waiting: "等待中",
  inviting: "邀请中",
} as const;

async function copyText(text: string, label: string) {
  await navigator.clipboard.writeText(text);
  toast("success", `已复制${label}`);
}

export function MemberDetailDrawer() {
  const qq = useInviteStore((s) => s.detailMemberQq);
  const member = useInviteStore((s) => (qq == null ? undefined : s.getMember(qq)));
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);
  const selectQq = useInviteStore((s) => s.selectQq);
  const deselectQq = useInviteStore((s) => s.deselectQq);
  const requeueMember = useInviteStore((s) => s.requeueMember);
  const selectedQqs = useInviteStore((s) => s.selectedQqs);
  const config = useInviteStore((s) => s.config);
  const animations = useSettingsStore((s) => s.settings.animations);
  const open = Boolean(member);


  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDetailMemberQq(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setDetailMemberQq]);

  const canSelect = member && member.status === "waiting";
  const canRequeue =
    member && (member.status === "failed" || member.status === "rate_limited");

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/20 transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        style={{ transitionDuration: animations ? "200ms" : "0ms" }}
        onClick={() => setDetailMemberQq(null)}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-[380px] flex-col border-l border-border bg-white shadow-xl ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        style={{
          transitionProperty: "transform",
          transitionDuration: animations ? "200ms" : "0ms",
          transitionTimingFunction: "ease-out",
        }}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="text-[15px] font-semibold">成员详情</h3>
          <button
            type="button"
            className="rounded-lg p-1.5 hover:bg-[#eef1eb]"
            onClick={() => setDetailMemberQq(null)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {member && (
          <div className="flex-1 overflow-auto p-4">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-light text-[18px] font-semibold text-primary">
                {member.nickname.slice(0, 1) || "Q"}
              </div>
              <div>
                <div className="text-[16px] font-semibold">{member.nickname}</div>
                <div className="text-[13px] text-muted-foreground">{member.card || "无群名片"}</div>
              </div>
            </div>

            <dl className="space-y-3 text-[13px]">
              <Row label="QQ号" value={<span className="font-mono">{member.qq}</span>} />
              <Row label="角色" value={roleLabel[member.role]} />
              <Row label="来源群" value={member.sourceGroupId || config.source_group_id || "—"} />
              <Row
                label="当前状态"
                value={
                  member.status === "filtered" && member.filterReason
                    ? `已过滤（${member.filterReason}）`
                    : statusLabel[member.status]
                }
              />
              <Row
                label="Token"
                value={member.has_token ? "已获取" : "未获取"}
              />
              <Row label="失败原因" value={member.failReason || "—"} />
              <Row label="邀请开始时间" value={formatDateTime(member.startedAt || 0)} />
              <Row label="完成时间" value={formatDateTime(member.finishedAt || 0)} />
              <Row label="耗时" value={formatDurationMs(member.durationMs || 0)} />
            </dl>

            <div className="mt-6 grid grid-cols-2 gap-2">
              <Action onClick={() => void copyText(String(member.qq), "QQ")}>复制 QQ</Action>
                            {canRequeue ? (
                <Action onClick={() => requeueMember(member.qq)}>重新加入队列</Action>
              ) : (
                <Action disabled>重新加入队列</Action>
              )}
              {canSelect ? (
                <Action
                  onClick={() => {
                    if (selectedQqs.has(member.qq)) deselectQq(member.qq);
                    else selectQq(member.qq);
                  }}
                >
                  {selectedQqs.has(member.qq) ? "取消选择" : "加入选择"}
                </Action>
              ) : (
                <Action disabled>不可选择</Action>
              )}
            </div>
          </div>
        )}
      </aside>
    </>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/60 pb-2">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="text-right text-[#242824]">{value}</dd>
    </div>
  );
}

function Action({
  children,
  onClick,
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-[10px] border border-border bg-[#f7faf5] px-3 py-2 text-[13px] hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}
