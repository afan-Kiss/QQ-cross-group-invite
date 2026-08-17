import { MemberTable } from "@/components/dashboard/MemberTable";
import { useInviteStore } from "@/store/useInviteStore";
import { formatNumber } from "@/lib/utils";
import { Users, User, Shield, Key } from "lucide-react";

export function MembersPage() {
  const members = useInviteStore((s) => s.members);
  const membersLoaded = useInviteStore((s) => s.membersLoaded);
  const loadMembers = useInviteStore((s) => s.loadMembers);
  const config = useInviteStore((s) => s.config);

  const normalCount = members.filter((m) => m.role === "member").length;
  const staffCount = members.filter((m) => m.role === "owner" || m.role === "admin").length;
  const tokenCount = members.filter((m) => m.token).length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div>
        <h2 className="text-[20px] font-semibold text-[#242824]">来源群成员</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          管理已加载成员并筛选待邀请对象
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "总成员", value: members.length, icon: Users },
          { label: "普通成员", value: normalCount, icon: User },
          { label: "管理人员", value: staffCount, icon: Shield },
          { label: "有效Token", value: tokenCount, icon: Key },
        ].map((c) => (
          <div
            key={c.label}
            className="rounded-[14px] border border-border bg-white p-4 shadow-[var(--shadow-card)]"
          >
            <div className="flex items-center gap-2 text-muted-foreground">
              <c.icon className="h-4 w-4" />
              <span className="text-[12px]">{c.label}</span>
            </div>
            <div className="mt-2 text-[24px] font-semibold text-[#242824]">
              {formatNumber(c.value)}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-muted-foreground">
          来源群：{config.source_group_id || "未设置"}
        </span>
        <button
          type="button"
          onClick={() => void loadMembers()}
          className="rounded-[10px] bg-primary-light px-3 py-1.5 text-[13px] text-primary hover:bg-primary/10"
        >
          重新加载
        </button>
      </div>

      <div className="min-h-0 flex-1 rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
        {!membersLoaded && members.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Users className="mb-3 h-10 w-10 text-muted-foreground/40" />
            <p className="text-[15px] font-medium text-[#242824]">暂无成员</p>
            <p className="mt-1 text-[13px] text-muted-foreground">
              请先填写来源群并加载成员
            </p>
          </div>
        ) : (
          <MemberTable />
        )}
      </div>
    </div>
  );
}
