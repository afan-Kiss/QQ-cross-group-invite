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
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#f7f8f5]/88 backdrop-blur-[2px]">
      <div className="w-[min(420px,90vw)] rounded-[16px] border border-border bg-white p-6 shadow-[var(--shadow-card)]">
        <div className="flex items-start gap-3">
          {!isError && <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary" />}
          <div className="min-w-0">
            <h2 className="text-[16px] font-semibold text-[#2f352d]">
              {isError ? "��������ʧ��" : "���ڳ�ʼ��"}
            </h2>
            <p className={`mt-2 text-[13px] leading-6 ${isError ? "text-danger" : "text-muted-foreground"}`}>
              {message}
            </p>
            {localService === "ready" && !napcatOnline && (
              <p className="mt-2 text-[13px] leading-6 text-[#d49a12]">
                {napcatMessage || "NapCat δ���ӣ��������� NapCat ���ٽ�������"}
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
            ����
          </button>
        )}
      </div>
    </div>
  );
}
