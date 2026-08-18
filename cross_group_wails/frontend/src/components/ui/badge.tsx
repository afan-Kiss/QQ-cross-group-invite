import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        owner: "bg-[#fff1e6] text-[#c76b1d]",
        admin: "bg-[#e8f0ff] text-[#3b6fc7]",
        member: "bg-primary-light text-primary-hover",
        unknown: "bg-[#eef0ec] text-[#7a8276]",
        success: "bg-primary-light text-primary-hover",
        filtered: "bg-[#eef0ec] text-[#7a8276]",
        waiting: "bg-[#eef0ec] text-[#7a8276]",
        inviting: "bg-[#e8edf5] text-[#5b6f8f]",
        rate_limited: "bg-[#fff8e6] text-[#b8860b]",
        failed: "bg-danger-light text-danger",
        cancelled: "bg-[#eef0ec] text-[#7a8276]",
      },
    },
    defaultVariants: {
      variant: "member",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
