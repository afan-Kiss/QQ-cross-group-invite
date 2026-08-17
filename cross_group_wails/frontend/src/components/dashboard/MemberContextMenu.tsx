import { useEffect } from "react";
import type { Member } from "@/lib/types";
import { useInviteStore } from "@/store/useInviteStore";
import { toast } from "@/store/useToastStore";

interface Props {
  x: number;
  y: number;
  member: Member;
  onClose: () => void;
}

export function MemberContextMenu({ x, y, member, onClose }: Props) {
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);
  const selectQq = useInviteStore((s) => s.selectQq);
  const deselectQq = useInviteStore((s) => s.deselectQq);
  const requeueMember = useInviteStore((s) => s.requeueMember);
  const selectedQqs = useInviteStore((s) => s.selectedQqs);

  useEffect(() => {
    const close = () => onClose();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("click", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const canQueue =
    member.status === "waiting" ||
    member.status === "failed" ||
    member.status === "rate_limited";

  const items: Array<{
    label: string;
    disabled?: boolean;
    onClick: () => void;
  }> = [
    {
      label: "查看详情",
      onClick: () => setDetailMemberQq(member.qq),
    },
    {
      label: "复制 QQ",
      onClick: async () => {
        await navigator.clipboard.writeText(String(member.qq));
        toast("success", "已复制QQ");
      },
    },
    {
      label: "复制昵称",
      onClick: async () => {
        await navigator.clipboard.writeText(member.nickname);
        toast("success", "已复制昵称");
      },
    },
    {
      label: "复制 Token",
      disabled: !member.token,
      onClick: async () => {
        if (!member.token) return;
        toast("warning", "Token 属于敏感运行数据，请勿泄露");
        await navigator.clipboard.writeText(member.token);
        toast("success", "已复制Token");
      },
    },
    {
      label: selectedQqs.has(member.qq) ? "移出邀请队列" : "加入邀请队列",
      disabled: !canQueue,
      onClick: () => {
        if (selectedQqs.has(member.qq)) deselectQq(member.qq);
        else selectQq(member.qq);
      },
    },
    {
      label: "重新邀请",
      disabled: !(member.status === "failed" || member.status === "rate_limited"),
      onClick: () => requeueMember(member.qq),
    },
  ];

  const left = Math.min(x, window.innerWidth - 200);
  const top = Math.min(y, window.innerHeight - 260);

  return (
    <div
      className="fixed z-[60] min-w-[180px] rounded-[10px] border border-border bg-white py-1 shadow-lg"
      style={{ left, top }}
      onClick={(e) => e.stopPropagation()}
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          disabled={item.disabled}
          className="block w-full px-3 py-2 text-left text-[13px] hover:bg-[#f7faf5] disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => {
            item.onClick();
            onClose();
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
