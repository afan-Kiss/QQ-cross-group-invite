import { z } from "zod";

export const INVITE_LIMITS = {
  batchMin: 1,
  batchMax: 1000,
  intervalMin: 100,
  intervalMax: 600000,
} as const;

/** Positive decimal group id: no leading zeros, not zero. */
const positiveGroupId = (label: string) =>
  z.string().regex(/^[1-9]\d*$/, label);

const batchCountField = z.string().refine((v) => {
  const n = Number(v);
  return Number.isInteger(n) && n >= INVITE_LIMITS.batchMin && n <= INVITE_LIMITS.batchMax;
}, `\u6bcf\u6279\u4eba\u6570\u5fc5\u987b\u4e3a ${INVITE_LIMITS.batchMin}\u2013${INVITE_LIMITS.batchMax}`);

const intervalMsField = z.string().refine((v) => {
  const n = Number(v);
  return Number.isInteger(n) && n >= INVITE_LIMITS.intervalMin && n <= INVITE_LIMITS.intervalMax;
}, `\u9080\u8bf7\u95f4\u9694\u5fc5\u987b\u4e3a ${INVITE_LIMITS.intervalMin}\u2013${INVITE_LIMITS.intervalMax} \u6beb\u79d2`);

export const inviteConfigSchema = z
  .object({
    target_group_id: positiveGroupId("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u76ee\u6807\u7fa4\u53f7"),
    source_group_id: positiveGroupId("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u6765\u6e90\u7fa4\u53f7"),
    batch_count: batchCountField,
    interval_ms: intervalMsField,
    filter_staff: z.boolean(),
  })
  .refine((v) => v.target_group_id !== v.source_group_id, {
    message: "\u76ee\u6807\u7fa4\u4e0d\u80fd\u4e0e\u6765\u6e90\u7fa4\u76f8\u540c",
    path: ["target_group_id"],
  });

export const inviteDefaultsSchema = z.object({
  defaultBatchCount: batchCountField,
  defaultIntervalMs: intervalMsField,
});

export type InviteConfigFormValues = z.infer<typeof inviteConfigSchema>;

export function parseInviteConfigForm(values: unknown) {
  return inviteConfigSchema.safeParse(values);
}

export function parseInviteDefaults(values: unknown) {
  return inviteDefaultsSchema.safeParse(values);
}

export function validateInviteBatchInterval(
  batch_count: string,
  interval_ms: string,
): { ok: true; batch: number; interval: number } | { ok: false; message: string } {
  const parsed = inviteDefaultsSchema.safeParse({ defaultBatchCount: batch_count, defaultIntervalMs: interval_ms });
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    return { ok: false, message: issue?.message ?? "\u53c2\u6570\u65e0\u6548" };
  }
  return {
    ok: true,
    batch: Number(parsed.data.defaultBatchCount),
    interval: Number(parsed.data.defaultIntervalMs),
  };
}
