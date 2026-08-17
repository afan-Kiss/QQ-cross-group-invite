import { Settings } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";

export function StatusBar() {
  const statusText = useInviteStore((s) => s.statusText);
  const inviting = useInviteStore((s) => s.inviting);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const napcatMessage = useServiceStore((s) => s.napcatMessage);

  const serviceLabel =
    localService === "ready"
      ? "���ط�������"
      : localService === "port_conflict"
        ? "���ط��񣺶˿ڳ�ͻ"
        : localService === "error"
          ? "���ط����쳣"
          : "���ط���������";

  const napcatLabel = napcatOnline ? "NapCat������" : "NapCat������";

  return (
    <footer className="flex h-9 shrink-0 items-center justify-between border-t border-border bg-white/90 px-4 text-[12px] text-muted-foreground">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              inviting ? "animate-pulse bg-primary" : localService === "ready" ? "bg-primary" : "bg-[#d49a12]"
            }`}
          />
          <span>{statusText || "����"}</span>
        </div>
        <span className={localService === "ready" ? "text-primary" : "text-danger"}>
          {serviceLabel}
        </span>
        <span className={napcatOnline ? "text-primary" : "text-[#d49a12]"} title={napcatMessage}>
          {napcatLabel}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span>�汾��1.0.0</span>
        <button className="transition-colors hover:text-primary">������</button>
        <button className="flex items-center gap-1 transition-colors hover:text-primary">
          <Settings className="h-3.5 w-3.5" />
          ����
        </button>
      </div>
    </footer>
  );
}
