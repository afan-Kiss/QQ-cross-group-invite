import { cn } from "@/lib/utils";
import { useToastStore, type ToastType } from "@/store/useToastStore";
import { CheckCircle2, Info, AlertTriangle, XCircle, X } from "lucide-react";

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="h-4 w-4 text-primary" />,
  info: <Info className="h-4 w-4 text-[#5c8fd8]" />,
  warning: <AlertTriangle className="h-4 w-4 text-warning" />,
  error: <XCircle className="h-4 w-4 text-danger" />,
};

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);

  return (
    <div className="pointer-events-none fixed right-4 top-[60px] z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "pointer-events-auto flex items-center gap-3 rounded-[12px] border border-border bg-white px-4 py-3 shadow-[var(--shadow-card)]",
            "animate-fade-up min-w-[280px] max-w-[360px]",
          )}
        >
          {icons[t.type]}
          <span className="flex-1 text-[13px] text-[#242824]">{t.message}</span>
          <button
            type="button"
            onClick={() => remove(t.id)}
            className="text-muted-foreground hover:text-[#242824]"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
