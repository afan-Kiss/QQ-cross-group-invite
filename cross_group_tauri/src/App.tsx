import { useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { DashboardPage } from "@/pages/DashboardPage";

function App() {
  useEffect(() => {
    const win = getCurrentWindow();
    const unlisten = win.onCloseRequested(async (event) => {
      event.preventDefault();
      await invoke("shutdown_backend_command");
      await win.destroy();
    });
    return () => {
      void unlisten.then((fn) => fn());
    };
  }, []);

  return (
    <div className="h-full bg-page-bg p-2">
      <DashboardPage />
    </div>
  );
}

export default App;
