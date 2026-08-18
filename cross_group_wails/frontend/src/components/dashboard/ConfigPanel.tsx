import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Play, Square, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";
import { cn } from "@/lib/utils";
import {
  inviteConfigSchema,
  type InviteConfigFormValues,
} from "@/lib/invite-config-schema";

type FormValues = InviteConfigFormValues;

export function ConfigPanel() {
  const config = useInviteStore((s) => s.config);
  const setConfig = useInviteStore((s) => s.setConfig);
  const loadMembers = useInviteStore((s) => s.loadMembers);
  const startInvite = useInviteStore((s) => s.startInvite);
  const stopInvite = useInviteStore((s) => s.stopInvite);
  const loadingMembers = useInviteStore((s) => s.loadingMembers);
  const inviting = useInviteStore((s) => s.inviting);
  const invitePhase = useInviteStore((s) => s.invitePhase);
  const stats = useInviteStore((s) => s.stats);
  const phaseBusy = invitePhase !== "idle";
  const canStop = invitePhase === "running";
  const stopping = invitePhase === "stopping";
  const serviceReady = useServiceStore((s) => s.localService === "ready");
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const refreshingNapcat = useServiceStore((s) => s.refreshingNapcat);
  const refreshNapcat = useServiceStore((s) => s.refreshNapcat);
  const actionDisabled = !serviceReady || !napcatOnline;

  const sameGroup =
    config.target_group_id &&
    config.source_group_id &&
    config.target_group_id === config.source_group_id;

  const { register, watch, setValue, formState, trigger } = useForm<FormValues>({
    resolver: zodResolver(inviteConfigSchema),
    defaultValues: config,
    values: config,
    mode: "onChange",
  });

  const filterStaff = watch("filter_staff");
  const errors = formState.errors;
  const configInvalid = Boolean(
    errors.target_group_id || errors.source_group_id || errors.batch_count || errors.interval_ms,
  );

  const onLoadMembers = async () => {
    const ok = await trigger(["source_group_id"]);
    if (!ok) return;
    await loadMembers();
  };

  const onStartInvite = async () => {
    const ok = await trigger();
    if (!ok) return;
    await startInvite();
  };

  return (
    <div className="animate-fade-up flex h-full min-h-0 flex-col overflow-y-auto rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h2 className="mb-4 text-[16px] font-semibold text-[#242824]">邀请配置</h2>

      {!napcatOnline && serviceReady && (
        <div className="mb-4 rounded-[10px] border border-[#f0dca0] bg-warning-light px-3 py-2 text-[12px] leading-5 text-[#9a7618]">
          <p>饭饭定制未连接，请启动饭饭定制后再加载成员或开始邀请。</p>
          <button
            type="button"
            className="mt-2 rounded-[8px] border border-[#e0c56a] bg-white px-3 py-1 text-[12px] hover:bg-[#fff8e6] disabled:opacity-60"
            disabled={refreshingNapcat}
            onClick={() => void refreshNapcat()}
          >
            {refreshingNapcat ? "检测中..." : "重新检测"}
          </button>
        </div>
      )}

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="source">来源群号（从哪个群拉人）</Label>
          <Input
            id="source"
            placeholder="填当前要导出成员的群号"
            disabled={!serviceReady}
            className={cn(sameGroup && "border-danger focus-visible:ring-danger/30")}
            {...register("source_group_id", {
              onChange: (e) => setConfig({ source_group_id: e.target.value.replace(/\D/g, "") }),
            })}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void onLoadMembers();
              }
            }}
          />
          <p className="text-[12px] text-muted-foreground">填好后来源群号后点「加载成员」，不会自动加载。</p>
          {errors.source_group_id && (
            <p className="text-[12px] text-danger">{String(errors.source_group_id.message || "")}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="target">目标群号（邀请进哪个群）</Label>
          <Input
            id="target"
            placeholder="填成员要加入的群号"
            disabled={!serviceReady}
            className={cn(sameGroup && "border-danger focus-visible:ring-danger/30")}
            {...register("target_group_id", {
              onChange: (e) => setConfig({ target_group_id: e.target.value.replace(/\D/g, "") }),
            })}
          />
          <p className="text-[12px] text-muted-foreground">开始邀请时才会用到，加载成员不需要填这个。</p>
          {errors.target_group_id && (
            <p className="text-[12px] text-danger">{String(errors.target_group_id.message || "")}</p>
          )}
          {sameGroup && (
            <p className="text-[12px] text-danger">目标群不能与来源群相同</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="batch">每批人数</Label>
          <Input
            id="batch"
            type="number"
            min={1}
            max={1000}
            disabled={!serviceReady}
            {...register("batch_count", {
              onChange: (e) => setConfig({ batch_count: e.target.value }),
            })}
          />
          <p className="text-[12px] text-muted-foreground">每批处理人数（1-1000），总人数以所选成员为准</p>
          {errors.batch_count && (
            <p className="text-[12px] text-danger">{String(errors.batch_count.message || "")}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="interval">间隔 (ms)</Label>
          <Input
            id="interval"
            type="number"
            min={100}
            max={600000}
            disabled={!serviceReady}
            {...register("interval_ms", {
              onChange: (e) => setConfig({ interval_ms: e.target.value }),
            })}
          />
          {errors.interval_ms && (
            <p className="text-[12px] text-danger">{String(errors.interval_ms.message || "")}</p>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="filter">过滤群主/管理员</Label>
            <Switch
              id="filter"
              checked={filterStaff}
              disabled={!serviceReady}
              onCheckedChange={(checked) => {
                setValue("filter_staff", checked);
                setConfig({ filter_staff: checked });
              }}
            />
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Button
          variant="outline"
          className="w-full border-primary-light bg-primary-light text-primary hover:bg-primary/10"
          onClick={() => void onLoadMembers()}
          disabled={Boolean(actionDisabled || loadingMembers || phaseBusy || sameGroup || Boolean(errors.source_group_id))}
        >
          {loadingMembers ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}
          加载成员
        </Button>
        <Button
          className="w-full"
          onClick={() => void onStartInvite()}
          disabled={Boolean(actionDisabled || phaseBusy || sameGroup || configInvalid)}
        >
          <Play className="h-4 w-4" />
          开始邀请
        </Button>
        <Button
          variant="warning"
          className="w-full"
          onClick={() => void stopInvite()}
          disabled={!serviceReady || !canStop}
        >
          <Square className="h-4 w-4" />
          {stopping || stats.status === "stopping" ? "正在停止…" : "停止邀请"}
        </Button>
      </div>
    </div>
  );
}
