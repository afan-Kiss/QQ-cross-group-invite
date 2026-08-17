import { Loader2 } from "lucide-react";
import { useServiceStore } from "@/store/useServiceStore";

export function BootstrapOverlay() {
  const localService = useServiceStore((s) => s.localService);
  const message = useServiceStore((s) => s.message);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const napcatMessage = useServiceStore((s) => s.napcatMessage);
  const bootstrapped = useServiceStore((s) => s.bootstrapped);

  if (bootstrapped) return null;

  const isError = localService === "error" || localService === "port_conflict";

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#f6f7f3]/90">
      <div className="w-[min(420px,90vw)] rounded-[16px] border border-border bg-white p-6 shadow-[var(--shadow-card)]">
        <div className="mb-4 text-center">
          <h2 className="text-[18px] font-semibold text-[#242824]">QQ跨群邀请工具</h2>
        </div>
        <div className="flex items-start gap-3">
          {!isError && <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary" />}
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold text-[#242824]">
              {isError ? "启动服务失败" : "正在初始化"}
            </h3>
            <p className={`mt-2 text-[13px] leading-6 ${isError ? "text-danger" : "text-muted-foreground"}`}>
              {message}
            </p>
            {!isError && (
              <ul className="mt-3 space-y-1 text-[12px] text-muted-foreground">
                <li>正在启动本地服务...</li>
                <li>正在检测 NapCat...</li>
                <li>正在初始化界面...</li>
              </ul>
            )}
            {localService === "ready" && !napcatOnline && (
              <p className="mt-2 text-[13px] leading-6 text-warning">
                {napcatMessage || "NapCat 未连接，请启动 NapCat 后再继续操作"}
              </p>
            )}
          </div>
        </div>
        {isError && (
          <button
            type="button"
            className="mt-5 w-full rounded-[10px] bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-hover"
            onClick={() => void useServiceStore.getState().ensureBackend()}
          >
            重试
          </button>
        )}
      </div>
    </div>
  );
}
