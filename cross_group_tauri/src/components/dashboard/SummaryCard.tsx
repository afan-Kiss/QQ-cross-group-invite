import type { LucideIcon } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";

interface SummaryCardProps {
  title: string;
  value: number;
  description: string;
  icon: LucideIcon;
  tone?: "primary" | "warning" | "danger";
}

const toneMap = {
  primary: {
    icon: "bg-primary-light text-primary",
    value: "text-[#2f352d]",
  },
  warning: {
    icon: "bg-[#fff8e6] text-[#d49a12]",
    value: "text-[#2f352d]",
  },
  danger: {
    icon: "bg-danger-light text-danger",
    value: "text-[#2f352d]",
  },
};

export function SummaryCard({
  title,
  value,
  description,
  icon: Icon,
  tone = "primary",
}: SummaryCardProps) {
  const styles = toneMap[tone];
  return (
    <div className="animate-fade-up flex min-w-[180px] flex-1 items-center gap-4 rounded-[16px] border border-border bg-white p-4 shadow-[var(--shadow-card)]">
      <div
        className={cn(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px]",
          styles.icon,
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="text-[13px] text-muted-foreground">{title}</div>
        <div className={cn("text-[32px] font-semibold leading-tight", styles.value)}>
          {formatNumber(value)}
        </div>
        <div className="text-[12px] text-muted-foreground">{description}</div>
      </div>
    </div>
  );
}
