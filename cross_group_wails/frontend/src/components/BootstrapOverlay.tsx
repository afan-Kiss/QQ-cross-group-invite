import { Loader2 } from "lucide-react";
import { useServiceStore } from "@/store/useServiceStore";

export function BootstrapOverlay() {
  const localService = useServiceStore((s) => s.localService);
  const message = useServiceStore((s) => s.message);
  const bootstrapped = useServiceStore((s) => s.bootstrapped);
  const ensureBackend = useServiceStore((s) => s.ensureBackend);

  if (bootstrapped || localService === "ready") return null;

  const isError = localService === "error" || localService === "port_conflict";
  const isConflict = localService === "port_conflict";

  const copyDiag = async () => {
    const text = [
      `localService=${localService}`,
      `message=${message}`,
      `time=${new Date().toISOString()}`,
    ].join("\n");
    await navigator.clipboard.writeText(text);
  };

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
              {isConflict ? "端口冲突" : isError ? "启动服务失败" : "正在初始化"}
            </h3>
            <p className={`mt-2 text-[13px] leading-6 ${isError ? "text-danger" : "text-muted-foreground"}`}>
              {isConflict ? `端口 17888 已被其他程序占用。${message}` : message}
            </p>
            {!isError && (
              <ul className="mt-3 space-y-1 text-[12px] text-muted-foreground">
                <li>正在检测本地服务...</li>
                <li>必要时启动 sidecar...</li>
                <li>健康检查通过后进入控制台</li>
              </ul>
            )}
          </div>
        </div>
        {isError && (
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="rounded-[10px] bg-primary px-4 py-2 text-[13px] text-white hover:bg-primary-hover"
              onClick={() => void ensureBackend()}
            >
              重新检测
            </button>
            {isConflict && (
              <button
                type="button"
                className="rounded-[10px] border border-border px-4 py-2 text-[13px] hover:bg-[#f7faf5]"
                onClick={() => void copyDiag()}
              >
                复制诊断信息
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
