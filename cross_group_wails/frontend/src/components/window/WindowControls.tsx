import { useEffect, useState } from "react";
import { WindowHide, WindowMinimise } from "../../../wailsjs/runtime/runtime";
import { subscribeMaximized, toggleMaximized } from "@/lib/window-state";

export function WindowControls() {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => subscribeMaximized(setMaximized), []);

  const handleClose = () => {
    // Close to tray; full exit is via tray menu "退出".
    void WindowHide();
  };

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => void WindowMinimise()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-black/5"
        aria-label="最小化"
        title="最小化"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="8" width="10" height="1.5" rx="0.5" /></svg>
      </button>
      <button
        type="button"
        onClick={() => void toggleMaximized()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-[#eaf5e7]"
        aria-label={maximized ? "还原" : "最大化"}
        title={maximized ? "还原" : "最大化"}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2">
          {maximized ? (
            <path d="M3 5V3h5v5H8M5 7v2h5V5H8" />
          ) : (
            <rect x="2" y="2" width="8" height="8" rx="1" />
          )}
        </svg>
      </button>
      <button
        type="button"
        onClick={() => void handleClose()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-[#e81123] hover:text-white"
        aria-label="关闭"
        title="关闭"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
      </button>
    </div>
  );
}
