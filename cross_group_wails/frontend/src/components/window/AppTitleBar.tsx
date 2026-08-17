import { Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { WindowControls } from "./WindowControls";
import { WindowToggleMaximise } from "../../../wailsjs/runtime/runtime";

export function AppTitleBar() {
  const handleDoubleClick = () => {
    void WindowToggleMaximise();
  };

  return (
    <header
      className={cn(
        "relative z-20 flex h-[52px] shrink-0 items-center justify-between border-b border-white/60 px-4",
        "bg-white/72 backdrop-blur-xl backdrop-saturate-150",
      )}
      style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
      onDoubleClick={handleDoubleClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-primary text-white shadow-sm">
          <Users className="h-4 w-4" />
        </div>
        <h1 className="text-[15px] font-semibold tracking-tight text-[#242824]">
          QQ跨群邀请工具
        </h1>
      </div>
      <WindowControls />
    </header>
  );
}
