import {
  LayoutDashboard,
  Users,
  Send,
  ShieldAlert,
  CircleX,
  FileText,
  Settings,
  Info,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useNavigationStore, type AppPage } from "@/store/useNavigationStore";
import { useServiceStore } from "@/store/useServiceStore";

const navItems: { page: AppPage; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { page: "dashboard", label: "控制台", icon: LayoutDashboard },
  { page: "members", label: "成员列表", icon: Users },
  { page: "tasks", label: "邀请任务", icon: Send },
  { page: "rate-limit", label: "频繁限制", icon: ShieldAlert },
  { page: "failed", label: "失败记录", icon: CircleX },
  { page: "logs", label: "运行日志", icon: FileText },
  { page: "settings", label: "系统设置", icon: Settings },
  { page: "about", label: "关于", icon: Info },
];

export function Sidebar() {
  const page = useNavigationStore((s) => s.page);
  const navigate = useNavigationStore((s) => s.navigate);
  const collapsed = useNavigationStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useNavigationStore((s) => s.toggleSidebar);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-border bg-white transition-[width] duration-200",
        collapsed ? "w-[72px]" : "w-[220px]",
      )}
    >
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const active = page === item.page || (page === "task-detail" && item.page === "tasks");
          const Icon = item.icon;
          return (
            <button
              key={item.page}
              type="button"
              onClick={() => navigate(item.page)}
              className={cn(
                "group relative flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                active
                  ? "bg-primary-light text-primary"
                  : "text-[#6b726a] hover:bg-primary-light/60",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
              )}
              <Icon className={cn("h-4 w-4 shrink-0", active && "text-primary")} />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <button
          type="button"
          onClick={toggleSidebar}
          className="mb-3 flex w-full items-center justify-center rounded-[8px] py-1.5 text-muted-foreground hover:bg-[#f7faf5]"
          title={collapsed ? "展开" : "收缩"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
        {!collapsed && (
          <div className="space-y-2 text-[11px] text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>本地服务</span>
              <span className={localService === "ready" ? "text-primary" : "text-danger"}>
                ● {localService === "ready" ? "正常" : "异常"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>NapCat</span>
              <span className={napcatOnline ? "text-primary" : "text-warning"}>
                ● {napcatOnline ? "在线" : "离线"}
              </span>
            </div>
            <div className="text-[10px] text-muted-foreground/80">版本 1.0.0</div>
          </div>
        )}
      </div>
    </aside>
  );
}
