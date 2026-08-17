import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Play, Square, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";
import { cn } from "@/lib/utils";

const schema = z.object({
  target_group_id: z.string(),
  source_group_id: z.string(),
  batch_count: z.string(),
  interval_ms: z.string(),
  filter_staff: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

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
  const actionDisabled = !serviceReady || !napcatOnline;

  const sameGroup =
    config.target_group_id &&
    config.source_group_id &&
    config.target_group_id === config.source_group_id;

  const { register, watch, setValue } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: config,
    values: config,
  });

  const filterStaff = watch("filter_staff");

  return (
    <div className="animate-fade-up flex h-full flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h2 className="mb-4 text-[16px] font-semibold text-[#242824]">邀请配置</h2>

      <div className="mb-4 rounded-[12px] border border-border bg-[#f7faf5] p-3 text-[12px]">
        <div className="mb-2 font-medium text-[#242824]">连接状态</div>
        <div className="space-y-1.5 text-muted-foreground">
          <div className="flex justify-between">
            <span>本地服务</span>
            <span className={serviceReady ? "text-primary" : "text-danger"}>
              ● {serviceReady ? "正常" : "异常"}
            </span>
          </div>
          <div className="flex justify-between">
            <span>NapCat</span>
            <span className={napcatOnline ? "text-primary" : "text-warning"}>
              ● {napcatOnline ? "在线" : "离线"}
            </span>
          </div>
        </div>
      </div>

      {!napcatOnline && serviceReady && (
        <div className="mb-4 rounded-[10px] border border-[#f0dca0] bg-warning-light px-3 py-2 text-[12px] leading-5 text-[#9a7618]">
          <p>NapCat 未连接，请启动 NapCat 后再加载成员或开始邀请。</p>
          <button
            type="button"
            className="mt-2 rounded-[8px] border border-[#e0c56a] bg-white px-3 py-1 text-[12px] hover:bg-[#fff8e6]"
            onClick={() => void useServiceStore.getState().refreshHealth()}
          >
            重新检测
          </button>
        </div>
      )}

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="target">目标群号</Label>
          <Input
            id="target"
            placeholder="请输入目标群号"
            disabled={!serviceReady}
            className={cn(sameGroup && "border-danger focus-visible:ring-danger/30")}
            {...register("target_group_id", {
              onChange: (e) => setConfig({ target_group_id: e.target.value.replace(/\D/g, "") }),
            })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="source">来源群号</Label>
          <Input
            id="source"
            placeholder="请输入来源群号"
            disabled={!serviceReady}
            className={cn(sameGroup && "border-danger focus-visible:ring-danger/30")}
            {...register("source_group_id", {
              onChange: (e) => setConfig({ source_group_id: e.target.value.replace(/\D/g, "") }),
            })}
          />
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
        </div>

        <div className="space-y-2">
          <Label htmlFor="interval">间隔 (ms)</Label>
          <Input
            id="interval"
            type="number"
            min={500}
            disabled={!serviceReady}
            {...register("interval_ms", {
              onChange: (e) => setConfig({ interval_ms: e.target.value }),
            })}
          />
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
          onClick={() => void loadMembers()}
          disabled={Boolean(actionDisabled || loadingMembers || phaseBusy || sameGroup)}
        >
          {loadingMembers ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}
          加载成员
        </Button>
        <Button
          className="w-full"
          onClick={() => void startInvite()}
          disabled={Boolean(actionDisabled || phaseBusy || sameGroup)}
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
