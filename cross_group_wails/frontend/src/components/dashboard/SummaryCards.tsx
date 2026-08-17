import {
  Users,
  CircleCheck,
  ShieldAlert,
  CircleX,
  Hourglass,
} from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { SummaryCard } from "./SummaryCard";

export function SummaryCards() {
  const stats = useInviteStore((s) => s.stats);
  const memberTotal = useInviteStore((s) => s.members.length);
  const total = stats.total || memberTotal;

  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
      <SummaryCard title="总人数" value={total} description="任务/成员总数" icon={Users} />
      <SummaryCard title="已成功" value={stats.success} description="成功邀请" icon={CircleCheck} />
      <SummaryCard title="频繁限制" value={stats.rate_limited} description="触发冷却" icon={ShieldAlert} tone="warning" />
      <SummaryCard title="失败" value={stats.failed} description="邀请失败" icon={CircleX} tone="danger" />
      <SummaryCard title="等待" value={stats.waiting} description="待处理" icon={Hourglass} tone="info" />
    </section>
  );
}
