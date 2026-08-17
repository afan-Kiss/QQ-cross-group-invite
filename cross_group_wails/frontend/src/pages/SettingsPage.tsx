import { useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { useSettingsStore, persistSettings } from "@/store/useSettingsStore";
import { useServiceStore } from "@/store/useServiceStore";
import { useInviteStore } from "@/store/useInviteStore";
import { api } from "@/lib/api";
import { wailsBridge } from "@/lib/wails-bridge";
import { toast } from "@/store/useToastStore";

export function SettingsPage() {
  const settings = useSettingsStore((s) => s.settings);
  const update = useSettingsStore((s) => s.update);
  const load = useSettingsStore((s) => s.load);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const ensureBackend = useServiceStore((s) => s.ensureBackend);
  const setConfig = useInviteStore((s) => s.setConfig);
  const [diagnosing, setDiagnosing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [diag, setDiag] = useState<Array<{ label: string; value: string; ok?: boolean }> | null>(null);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    const token = settings.napcatWebuiToken;
    persistSettings(settings);
    setConfig({
      batch_count: settings.defaultBatchCount,
      interval_ms: settings.defaultIntervalMs,
      filter_staff: settings.defaultFilterStaff,
    });
    if (localService !== "ready") {
      if (token) {
        toast("warning", "服务未连接，Token 尚未保存");
      } else {
        toast("success", "本地设置已保存");
      }
      return;
    }
    try {
      await api.saveConfig({
        target_group_id: useInviteStore.getState().config.target_group_id,
        source_group_id: useInviteStore.getState().config.source_group_id,
        batch_count: settings.defaultBatchCount,
        interval_ms: settings.defaultIntervalMs,
        filter_staff: settings.defaultFilterStaff,
        onebot_url: settings.onebotUrl,
        napcat_webui_token: token,
        log_level: settings.logLevel,
        max_log_file_mb: settings.maxLogFileSize,
        log_retention_days: settings.logRetentionDays,
        auto_clean_logs: settings.autoCleanLogs,
      } as never);
      if (token) update({ napcatWebuiToken: "" });
      toast("success", "设置已保存");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "保存失败");
    }
  };

  const runDiagnostic = async () => {
    setDiagnosing(true);
    try {
      const items = await wailsBridge.runDiagnostics();
      setDiag(items.map((i) => ({ label: i.label, value: i.value, ok: i.ok })));
    } catch {
      const health = await wailsBridge.probeHealth().catch(() => null);
      setDiag([
        {
          label: "本地服务",
          value: health?.localService === "ready" ? "正常" : health?.message || "异常",
          ok: health?.localService === "ready",
        },
        { label: "17888", value: health?.localService === "ready" ? "正常" : "异常", ok: health?.localService === "ready" },
        { label: "NapCat", value: health?.napcatOnline ? "在线" : "离线", ok: !!health?.napcatOnline },
        { label: "服务地址", value: "127.0.0.1:17888（内置服务）", ok: true },
      ]);
    } finally {
      setDiagnosing(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      await api.testConnection({
        onebot_url: settings.onebotUrl,
        napcat_webui_token: settings.napcatWebuiToken,
      });
      toast("success", "连接测试成功");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
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
          {!settings.autoConnectOnStart && (
            <button
              type="button"
              className="mt-2 rounded-[10px] bg-primary px-4 py-2 text-[13px] text-white"
              onClick={() => void ensureBackend()}
            >
              连接服务
            </button>
          )}
        </SettingCard>

        <SettingCard title="界面设置">
          <SelectField
            label="主题"
            value={settings.theme}
            options={[
              { v: "light", l: "浅色" },
              { v: "system", l: "跟随系统" },
            ]}
            onChange={(v) => update({ theme: v as "light" | "system" })}
          />
          <SelectField
            label="界面缩放"
            value={settings.uiScale}
            options={["90", "100", "110", "125"].map((v) => ({ v, l: `${v}%` }))}
            onChange={(v) => update({ uiScale: v })}
          />
          <Toggle label="动画效果" checked={settings.animations} onChange={(v) => update({ animations: v })} />
          <Toggle label="紧凑表格" checked={settings.compactTable} onChange={(v) => update({ compactTable: v })} />
        </SettingCard>

        <SettingCard title="日志设置">
          <SelectField
            label="日志级别"
            value={settings.logLevel}
            options={["INFO", "WARN", "ERROR"].map((l) => ({ v: l, l }))}
            onChange={(v) => update({ logLevel: v })}
          />
          <Field label="最大日志文件(MB)" value={settings.maxLogFileSize} onChange={(v) => update({ maxLogFileSize: v })} />
          <Field label="保留天数" value={settings.logRetentionDays} onChange={(v) => update({ logRetentionDays: v })} />
          <Toggle label="自动清理" checked={settings.autoCleanLogs} onChange={(v) => update({ autoCleanLogs: v })} />
          <p className="text-[12px] text-muted-foreground">日志相关设置下次启动 sidecar 后生效</p>
        </SettingCard>

        <SettingCard title="连接设置">
          <div className="text-[13px]">
            <span className="text-muted-foreground">本地服务地址</span>
            <p className="mt-1 font-mono">127.0.0.1:17888（内置服务）</p>
          </div>
          <div className="text-[13px]">
            <span className="text-muted-foreground">NapCat 状态</span>
            <p className="mt-1">{napcatOnline ? "在线" : "离线"} · 本地服务 {localService}</p>
          </div>
          <Field label="OneBot 地址" value={settings.onebotUrl} onChange={(v) => update({ onebotUrl: v })} />
          <div className="text-[13px]">
            <span className="text-muted-foreground">NapCat WebUI Token</span>
            <input
              type="password"
              value={settings.napcatWebuiToken}
              onChange={(e) => update({ napcatWebuiToken: e.target.value })}
              placeholder="留空表示不修改已保存 Token"
              className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 text-[13px] outline-none focus:border-primary"
            />
          </div>
          <button
            type="button"
            disabled={testing || localService !== "ready"}
            onClick={() => void testConnection()}
            className="mt-2 flex items-center gap-2 rounded-[10px] border border-border px-4 py-2 text-[13px] hover:bg-[#f7faf5] disabled:opacity-50"
          >
            {testing && <Loader2 className="h-4 w-4 animate-spin" />}
            测试连接
          </button>
        </SettingCard>
      </div>

      <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">运行诊断</h3>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void runDiagnostic()}
              disabled={diagnosing}
              className="flex items-center gap-2 rounded-[10px] bg-primary px-4 py-2 text-[13px] text-white hover:bg-primary-hover disabled:opacity-60"
            >
              {diagnosing && <Loader2 className="h-4 w-4 animate-spin" />}
              运行诊断
            </button>
            {diag && (
              <button
                type="button"
                className="rounded-[10px] border border-border px-4 py-2 text-[13px]"
                onClick={async () => {
                  await navigator.clipboard.writeText(
                    diag.map((d) => `${d.label}: ${d.value}`).join("\n"),
                  );
                  toast("success", "诊断结果已复制");
                }}
              >
                复制诊断结果
              </button>
            )}
          </div>
        </div>
        {diag && (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
            {diag.map((item) => (
              <div key={item.label} className="rounded-[10px] bg-[#f7faf5] px-3 py-2 text-[13px]">
                <span className="text-muted-foreground">{item.label}</span>
                <p className={`font-medium ${item.ok === false ? "text-danger" : item.ok ? "text-primary" : ""}`}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void save()}
          className="rounded-[10px] bg-primary px-5 py-2.5 text-[14px] font-medium text-white hover:bg-primary-hover"
        >
          保存设置
        </button>
      </div>
    </div>
  );
}

function SettingCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 text-[15px] font-semibold">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 outline-none focus:border-primary"
      />
    </label>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
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
  options: Array<{ v: string; l: string }>;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-[8px] border border-border px-3 py-2 outline-none focus:border-primary"
      >
        {options.map((o) => (
          <option key={o.v} value={o.v}>
            {o.l}
          </option>
        ))}
      </select>
    </label>
  );
}
