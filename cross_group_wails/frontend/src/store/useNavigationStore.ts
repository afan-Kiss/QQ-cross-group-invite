import { create } from "zustand";

export type AppPage =
  | "dashboard"
  | "members"
  | "tasks"
  | "task-detail"
  | "rate-limit"
  | "failed"
  | "logs"
  | "settings"
  | "about";

interface NavigationState {
  page: AppPage;
  taskId: string | null;
  sidebarCollapsed: boolean;
  navigate: (page: AppPage) => void;
  openTaskDetail: (taskId: string) => void;
  backToTasks: () => void;
  toggleSidebar: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  page: "dashboard",
  taskId: null,
  sidebarCollapsed: false,
  navigate: (page) => set({ page, taskId: page === "task-detail" ? null : null }),
  openTaskDetail: (taskId) => set({ page: "task-detail", taskId }),
  backToTasks: () => set({ page: "tasks", taskId: null }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
