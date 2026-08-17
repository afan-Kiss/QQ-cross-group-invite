import { BootstrapOverlay } from "@/components/BootstrapOverlay";
import { AppTitleBar } from "@/components/window/AppTitleBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { GlobalStatusBar } from "@/components/layout/GlobalStatusBar";
import { ToastContainer } from "@/components/ui/ToastContainer";
import { useBootstrap } from "@/hooks/useBootstrap";
import { usePollingStatus } from "@/hooks/usePollingStatus";
import { useNavigationStore } from "@/store/useNavigationStore";
import { DashboardPage } from "@/pages/DashboardPage";
import { MembersPage } from "@/pages/MembersPage";
import { TasksPage } from "@/pages/TasksPage";
import { TaskDetailPage } from "@/pages/TaskDetailPage";
import { RateLimitPage } from "@/pages/RateLimitPage";
import { FailedPage } from "@/pages/FailedPage";
import { LogsPage } from "@/pages/LogsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AboutPage } from "@/pages/AboutPage";
import { cn } from "@/lib/utils";

export function MainLayout() {
  useBootstrap();
  usePollingStatus();
  const page = useNavigationStore((s) => s.page);

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-[12px] border border-border bg-page-bg shadow-[0_8px_32px_rgba(28,36,24,0.08)]">
      <BootstrapOverlay />
      <ToastContainer />
      <AppTitleBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main
          className={cn(
            "min-h-0 flex-1 overflow-hidden p-4 animate-fade-in",
          )}
        >
          {page === "dashboard" && <DashboardPage />}
          {page === "members" && <MembersPage />}
          {page === "tasks" && <TasksPage />}
          {page === "task-detail" && <TaskDetailPage />}
          {page === "rate-limit" && <RateLimitPage />}
          {page === "failed" && <FailedPage />}
          {page === "logs" && <LogsPage />}
          {page === "settings" && <SettingsPage />}
          {page === "about" && <AboutPage />}
        </main>
      </div>
      <GlobalStatusBar />
    </div>
  );
}
