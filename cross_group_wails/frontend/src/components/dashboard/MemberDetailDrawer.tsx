import { useEffect, useState, type ReactNode } from "react";
import { Eye, EyeOff, X } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { formatDateTime, formatDurationMs, maskToken } from "@/lib/utils";
import { toast } from "@/store/useToastStore";
import { useSettingsStore } from "@/store/useSettingsStore";

const roleLabel = { owner: "???", admin: "?????", member: "???" } as const;
const statusLabel = {
  success: "??????",
  filtered: "?????",
  rate_limited: "???????",
  failed: "???????",
  waiting: "?????",
  inviting: "??????",
} as const;

async function copyText(text: string, label: string) {
  await navigator.clipboard.writeText(text);
  toast("success", `?????${label}`);
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
  const [showToken, setShowToken] = useState(false);
  const open = Boolean(member);

  useEffect(() => {
    setShowToken(false);
  }, [qq]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDetailMemberQq(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setDetailMemberQq]);

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
          <h3 className="text-[15px] font-semibold">???????</h3>
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
                <div className="text-[13px] text-muted-foreground">{member.card || "??????"}</div>
              </div>
            </div>

            <dl className="space-y-3 text-[13px]">
              <Row label="QQ??" value={<span className="font-mono">{member.qq}</span>} />
              <Row label="???" value={roleLabel[member.role]} />
              <Row label="????" value={config.source_group_id || "??"} />
              <Row
                label="?????"
                value={
                  member.status === "filtered" && member.filterReason
                    ? `??????${member.filterReason}??`
                    : statusLabel[member.status]
                }
              />
              <Row
                label="Token"
                value={
                  <div className="flex items-center gap-2">
                    <span className="font-mono">
                      {showToken ? member.token || "??" : maskToken(member.token)}
                    </span>
                    <button
                      type="button"
                      className="rounded p-1 hover:bg-[#eef1eb]"
                      onClick={() => setShowToken((v) => !v)}
                    >
                      {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                }
              />
              <Row label="??????" value={member.failReason || "??"} />
              <Row label="????????" value={formatDateTime(member.startedAt || 0)} />
              <Row label="??????" value={formatDateTime(member.finishedAt || 0)} />
              <Row label="???" value={formatDurationMs(member.durationMs || 0)} />
            </dl>

            <div className="mt-6 grid grid-cols-2 gap-2">
              <Action
                onClick={() => void copyText(String(member.qq), "QQ")}
              >
                ???? QQ
              </Action>
              <Action
                onClick={() => {
                  if (!member.token) {
                    toast("warning", "???????? Token");
                    return;
                  }
                  toast("warning", "Token ????????????????????????");
                  void copyText(member.token, "Token");
                }}
              >
                ???? Token
              </Action>
              <Action onClick={() => requeueMember(member.qq)}>??????????</Action>
              <Action
                onClick={() => {
                  if (selectedQqs.has(member.qq)) deselectQq(member.qq);
                  else selectQq(member.qq);
                }}
              >
                {selectedQqs.has(member.qq) ? "??????" : "???????"}
              </Action>
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
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-[10px] border border-border bg-[#f7faf5] px-3 py-2 text-[13px] hover:border-primary hover:text-primary"
    >
      {children}
    </button>
  );
}
