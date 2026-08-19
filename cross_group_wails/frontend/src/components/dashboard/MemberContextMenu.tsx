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

  const canQueue = member.status === "waiting";

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
      label: "\u590d\u5236\u6635\u79f0",
      onClick: async () => {
        await navigator.clipboard.writeText(member.nickname);
        toast("success", "\u5df2\u590d\u5236\u6635\u79f0");
      },
    },
    {
      label: selectedQqs.has(member.qq) ? "\u79fb\u51fa\u9080\u8bf7\u961f\u5217" : "\u52a0\u5165\u9080\u8bf7\u961f\u5217",
      disabled: !canQueue,
      onClick: () => {
        if (selectedQqs.has(member.qq)) deselectQq(member.qq);
        else selectQq(member.qq);
      },
    },
    {
      label: "重新加入队列",
      disabled: !(member.status === "failed" || member.status === "rate_limited" || member.status === "cancelled"),
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
