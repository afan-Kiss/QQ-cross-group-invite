import appIcon from "@/assets/app-icon.png";
import { cn } from "@/lib/utils";
import { WindowControls } from "./WindowControls";
import { toggleMaximized } from "@/lib/window-state";

export function AppTitleBar() {
  return (
    <header
      className={cn(
        "relative z-20 flex h-[52px] shrink-0 items-center justify-between border-b border-border bg-white px-4",
      )}
      style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
      onDoubleClick={() => void toggleMaximized()}
    >
      <div className="flex items-center gap-3">
        <img src={appIcon} alt="" className="h-8 w-8 rounded-[8px]" draggable={false} />
        <h1 className="text-[15px] font-semibold tracking-tight text-[#242824]">
          QQ跨群邀请工具
        </h1>
      </div>
      <WindowControls />
    </header>
  );
}
