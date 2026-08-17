import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { wailsBridge } from "@/lib/wails-bridge";
import { useServiceStore } from "@/store/useServiceStore";

export function AboutPage() {
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const [info, setInfo] = useState({
    appVersion: "1.0.0",
    wailsVersion: "2.12.0",
    goVersion: "",
    frontendVersion: "1.0.0",
    pythonServiceVersion: "",
  });

  useEffect(() => {
    void wailsBridge.getAppInfo().then((raw) => {
      if (raw) {
        setInfo({
          appVersion: raw.appVersion,
          wailsVersion: raw.wailsVersion,
          goVersion: raw.goVersion,
          frontendVersion: raw.frontendVersion,
          pythonServiceVersion: raw.pythonServiceVersion || "—",
        });
      }
    });
  }, []);

  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-md rounded-[16px] border border-border bg-white p-8 shadow-[var(--shadow-card)] text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[16px] bg-primary text-white">
          <Users className="h-8 w-8" />
        </div>
        <h2 className="mt-4 text-[22px] font-semibold text-[#242824]">QQ跨群邀请工具</h2>
        <p className="mt-1 text-[14px] text-muted-foreground">版本 {info.appVersion}</p>

        <dl className="mt-6 space-y-3 text-left text-[13px]">
          {[
            ["Wails 版本", info.wailsVersion],
            ["Go 版本", info.goVersion || "—"],
            ["前端版本", info.frontendVersion],
            ["Python 服务版本", info.pythonServiceVersion],
            ["NapCat 状态", napcatOnline ? "在线" : "离线"],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-border/50 py-2">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="font-medium text-[#242824]">{v}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => void wailsBridge.openLogsDir()}
            className="w-full rounded-[10px] border border-border py-2.5 text-[13px] hover:bg-[#f7faf5]"
          >
            打开日志目录
          </button>
          <button
            type="button"
            disabled
            className="w-full rounded-[10px] border border-border py-2.5 text-[13px] text-muted-foreground opacity-60 cursor-not-allowed"
            title="暂未开放"
          >
            检查更新（暂未开放）
          </button>
        </div>
      </div>
    </div>
  );
}
