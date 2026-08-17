import { useEffect, useState, type ReactNode } from "react";
import { useSettingsStore, persistSettings } from "@/store/useSettingsStore";
import { useServiceStore } from "@/store/useServiceStore";
import { wailsBridge } from "@/lib/wails-bridge";
import { Loader2 } from "lucide-react";

export function SettingsPage() {
  const settings = useSettingsStore((s) => s.settings);
  const update = useSettingsStore((s) => s.update);
  const load = useSettingsStore((s) => s.load);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diag, setDiag] = useState<Array<{ label: string; value: string }> | null>(null);

  useEffect(() => {
    load();
  }, [load]);

  const save = () => {
    persistSettings(settings);
  };

  const runDiagnostic = async () => {
    setDiagnosing(true);
    try {
      const health = await wailsBridge.probeHealth();
      setDiag([
        { label: "本地服务", value: health.localService === "ready" ? "正常" : health.message },
        { label: "17888", value: health.localService === "ready" ? "正常" : "异常" },
        { label: "NapCat", value: health.napcatOnline ? "在线" : "离线" },
        { label: "sidecar", value: health.startedByUs ? "运行中" : "外部/未启动" },
        { label: "日志目录", value: "可写" },
      ]);
    } finally {
      setDiagnosing(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto">
      <div>
        <h2 className="text-[20px] font-semibold text-[#242824]">系统设置</h2>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SettingCard title="基础设置">
          <Field label="默认批量人数" value={settings.defaultBatchCount} onChange={(v) => update({ defaultBatchCount: v })} />
          <Field label="默认邀请间隔(ms)" value={settings.defaultIntervalMs} onChange={(v) => update({ defaultIntervalMs: v })} />
          <Toggle label="默认过滤群主/管理员" checked={settings.defaultFilterStaff} onChange={(v) => update({ defaultFilterStaff: v })} />
          <Toggle label="启动后自动连接服务" checked={settings.autoConnectOnStart} onChange={(v) => update({ autoConnectOnStart: v })} />
        </SettingCard>

        <SettingCard title="界面设置">
          <SelectField label="主题" value={settings.theme} options={[{ v: "light", l: "浅色" }, { v: "system", l: "跟随系统" }]} onChange={(v) => update({ theme: v as "light" | "system" })} />
          <Field label="界面缩放(%)" value={settings.uiScale} onChange={(v) => update({ uiScale: v })} />
          <Toggle label="动画效果" checked={settings.animations} onChange={(v) => update({ animations: v })} />
          <Toggle label="紧凑表格" checked={settings.compactTable} onChange={(v) => update({ compactTable: v })} />
        </SettingCard>

        <SettingCard title="日志设置">
          <SelectField label="日志级别" value={settings.logLevel} options={["INFO", "WARN", "ERROR"].map((l) => ({ v: l, l }))} onChange={(v) => update({ logLevel: v })} />
          <Field label="最大日志文件(MB)" value={settings.maxLogFileSize} onChange={(v) => update({ maxLogFileSize: v })} />
          <Field label="保留天数" value={settings.logRetentionDays} onChange={(v) => update({ logRetentionDays: v })} />
          <Toggle label="自动清理" checked={settings.autoCleanLogs} onChange={(v) => update({ autoCleanLogs: v })} />
        </SettingCard>

        <SettingCard title="连接设置">
          <div className="text-[13px]">
            <span className="text-muted-foreground">本地服务地址</span>
            <p className="mt-1 font-mono">{settings.serviceAddress}</p>
          </div>
          <div className="text-[13px]">
            <span className="text-muted-foreground">NapCat 状态</span>
            <p className="mt-1">{napcatOnline ? "在线" : "离线"}</p>
          </div>
          <div className="text-[13px]">
            <span className="text-muted-foreground">OneBot 端口</span>
            <input
              type="text"
              value={settings.onebotPort}
              onChange={(e) => update({ onebotPort: e.target.value })}
              className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 text-[13px] outline-none focus:border-primary"
            />
          </div>
          <div className="text-[13px]">
            <span className="text-muted-foreground">OneBot 密码</span>
            <input
              type="password"
              value={settings.onebotPassword}
              onChange={(e) => update({ onebotPassword: e.target.value })}
              placeholder="留空表示无密码"
              className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 text-[13px] outline-none focus:border-primary"
            />
          </div>
        </SettingCard>
      </div>

      <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">运行诊断</h3>
          <button
            type="button"
            onClick={() => void runDiagnostic()}
            disabled={diagnosing}
            className="flex items-center gap-2 rounded-[10px] bg-primary px-4 py-2 text-[13px] text-white hover:bg-primary-hover disabled:opacity-60"
          >
            {diagnosing && <Loader2 className="h-4 w-4 animate-spin" />}
            运行诊断
          </button>
        </div>
        {diag && (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
            {diag.map((item) => (
              <div key={item.label} className="rounded-[10px] bg-[#f7faf5] px-3 py-2 text-[13px]">
                <span className="text-muted-foreground">{item.label}</span>
                <p className="font-medium">{item.value}</p>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-[12px] text-muted-foreground">
          本地服务当前：{localService === "ready" ? "正常" : "未就绪"}
        </p>
      </div>

      <button
        type="button"
        onClick={save}
        className="self-start rounded-[10px] bg-primary px-6 py-2.5 text-[13px] font-medium text-white hover:bg-primary-hover"
      >
        保存设置
      </button>
    </div>
  );
}

function SettingCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold">{title}</h3>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-[13px] text-muted-foreground">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 text-[13px] outline-none focus:border-primary"
      />
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-[#65ad57]" />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { v: string; l: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="text-[13px] text-muted-foreground">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 text-[13px] outline-none focus:border-primary"
      >
        {options.map((o) => (
          <option key={o.v} value={o.v}>{o.l}</option>
        ))}
      </select>
    </div>
  );
}
