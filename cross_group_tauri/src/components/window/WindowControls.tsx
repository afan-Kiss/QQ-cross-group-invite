import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Minus, Square, X } from "lucide-react";

export function WindowControls() {
  const [, setMaximized] = useState(false);

  useEffect(() => {
    const win = getCurrentWindow();
    void win.isMaximized().then(setMaximized);
    const unlisten = win.onResized(async () => {
      setMaximized(await win.isMaximized());
    });
    return () => {
      void unlisten.then((fn) => fn());
    };
  }, []);

  const win = getCurrentWindow();

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => void win.minimize()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-black/5"
        aria-label="minimize"
      >
        <Minus className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => void win.toggleMaximize()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-black/5"
        aria-label="maximize"
      >
        <Square className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => void win.close()}
        className="flex h-9 w-10 items-center justify-center rounded-[8px] text-[#5f665c] transition-colors duration-200 hover:bg-[#e81123] hover:text-white"
        aria-label="close"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
