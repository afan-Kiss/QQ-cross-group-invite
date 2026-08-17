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
      <SummaryCard
        title="����"
        value={stats.total}
        description="��Ա����"
        icon={Users}
      />
      <SummaryCard
        title="�����"
        value={stats.completed}
        description="�Ѵ�����Ա"
        icon={ClipboardCheck}
      />
      <SummaryCard
        title="�ɹ���"
        value={stats.success}
        description="�ɹ�����"
        icon={CircleCheck}
      />
      <SummaryCard
        title="Ƶ������"
        value={stats.rate_limited}
        description="����ȴ����"
        icon={ShieldAlert}
        tone="warning"
      />
      <SummaryCard
        title="ʧ����"
        value={stats.failed}
        description="����ʧ��"
        icon={CircleX}
        tone="danger"
      />
    </section>
  );
}
