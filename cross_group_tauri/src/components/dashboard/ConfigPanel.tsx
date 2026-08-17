import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Copy, Loader2, Play, Square, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";

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
  const serviceReady = useServiceStore((s) => s.localService === "ready");
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const actionDisabled = !serviceReady || !napcatOnline;

  const { register, watch, setValue } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: config,
    values: config,
  });

  const filterStaff = watch("filter_staff");

  return (
    <div className="animate-fade-up flex h-full flex-col rounded-[16px] border border-border bg-white p-5 shadow-[var(--shadow-card)]">
      <h2 className="mb-5 text-[16px] font-semibold text-[#2f352d]">��������</h2>

      {!napcatOnline && serviceReady && (
        <p className="mb-4 rounded-[10px] border border-[#f0dca0] bg-[#fff8e6] px-3 py-2 text-[12px] leading-5 text-[#9a7618]">
          NapCat δ���ӣ��������� NapCat ���ټ��س�Ա��ʼ���롣
        </p>
      )}

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="target">Ŀ��Ⱥ��</Label>
          <div className="relative">
            <Input
              id="target"
              placeholder="������Ŀ��Ⱥ��"
              disabled={!serviceReady}
              {...register("target_group_id", {
                onChange: (e) => setConfig({ target_group_id: e.target.value }),
              })}
            />
            <Copy className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#b5bbb0]" />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="source">��ԴȺ��</Label>
          <Input
            id="source"
            placeholder="��������ԴȺ��"
            disabled={!serviceReady}
            {...register("source_group_id", {
              onChange: (e) => setConfig({ source_group_id: e.target.value }),
            })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="batch">��������</Label>
          <Input
            id="batch"
            type="number"
            min={1}
            max={50}
            disabled={!serviceReady}
            {...register("batch_count", {
              onChange: (e) => setConfig({ batch_count: e.target.value }),
            })}
          />
          <p className="text-[12px] text-muted-foreground">ÿ��������������ޣ�1-50��</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="interval">��� (ms)</Label>
          <Input
            id="interval"
            type="number"
            min={500}
            disabled={!serviceReady}
            {...register("interval_ms", {
              onChange: (e) => setConfig({ interval_ms: e.target.value }),
            })}
          />
          <p className="text-[12px] text-muted-foreground">
            ÿ����������ʱ�䣨���� �� 1000��
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="filter">����Ⱥ��/����Ա</Label>
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
          <p className="text-[12px] text-muted-foreground">����������Ⱥ���͹���Ա</p>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => void loadMembers()}
          disabled={actionDisabled || loadingMembers || inviting}
        >
          {loadingMembers ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Users className="h-4 w-4" />
          )}
          ���س�Ա
        </Button>
        <Button
          className="w-full"
          onClick={() => void startInvite()}
          disabled={actionDisabled || inviting}
        >
          <Play className="h-4 w-4" />
          ��ʼ����
        </Button>
        <Button
          variant="warning"
          className="w-full"
          onClick={() => void stopInvite()}
          disabled={!serviceReady || !inviting}
        >
          <Square className="h-4 w-4" />
          ֹͣ����
        </Button>
      </div>
    </div>
  );
}
