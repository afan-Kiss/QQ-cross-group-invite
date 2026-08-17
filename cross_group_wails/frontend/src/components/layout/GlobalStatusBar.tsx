import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";

export function GlobalStatusBar() {
  const inviting = useInviteStore((s) => s.inviting);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);

  const serviceOk = localService === "ready";
  const napcatOk = napcatOnline;

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t border-border bg-white px-4 text-[12px] text-muted-foreground">
      <div className="flex items-center gap-2">
        <span
          className={inviting ? "text-primary" : "text-primary"}
        >
          ● {inviting ? "正在邀请" : "就绪"}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span>
          本地服务 <span className={serviceOk ? "text-primary" : "text-danger"}>●</span>
        </span>
        <span>
          饭饭定制 <span className={napcatOk ? "text-primary" : "text-warning"}>●</span>
        </span>
      </div>
      <div>版本 1.0.0</div>
    </footer>
  );
}
