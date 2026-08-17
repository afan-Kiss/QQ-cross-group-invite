import {
  Users,
  ClipboardCheck,
  CircleCheck,
  ShieldAlert,
  CircleX,
} from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { SummaryCard } from "./SummaryCard";

export function SummaryCards() {
  const stats = useInviteStore((s) => s.stats);

  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
      <SummaryCard title="总成员" value={stats.total} description="成员总数" icon={Users} />
      <SummaryCard title="已完成" value={stats.completed} description="已处理成员" icon={ClipboardCheck} tone="info" />
      <SummaryCard title="成功数" value={stats.success} description="成功邀请" icon={CircleCheck} />
      <SummaryCard title="频繁限制" value={stats.rate_limited} description="触发冷却" icon={ShieldAlert} tone="warning" />
      <SummaryCard title="失败数" value={stats.failed} description="邀请失败" icon={CircleX} tone="danger" />
    </section>
  );
}
