import { z } from "zod";

/** Positive decimal group id: no leading zeros, not zero. */
const positiveGroupId = (label: string) =>
  z.string().regex(/^[1-9]\d*$/, label);

export const inviteConfigSchema = z
  .object({
    target_group_id: positiveGroupId("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u76ee\u6807\u7fa4\u53f7"),
    source_group_id: positiveGroupId("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u6765\u6e90\u7fa4\u53f7"),
    batch_count: z.string().refine((v) => {
      const n = Number(v);
      return Number.isInteger(n) && n >= 1 && n <= 1000;
    }, "\u6bcf\u6279\u4eba\u6570\u5fc5\u987b\u4e3a 1\u20131000"),
    interval_ms: z.string().refine((v) => {
      const n = Number(v);
      return Number.isInteger(n) && n >= 100 && n <= 600000;
    }, "\u9080\u8bf7\u95f4\u9694\u5fc5\u987b\u4e3a 100\u2013600000 \u6beb\u79d2"),
    filter_staff: z.boolean(),
  })
  .refine((v) => v.target_group_id !== v.source_group_id, {
    message: "\u76ee\u6807\u7fa4\u4e0d\u80fd\u4e0e\u6765\u6e90\u7fa4\u76f8\u540c",
    path: ["target_group_id"],
  });

export type InviteConfigFormValues = z.infer<typeof inviteConfigSchema>;

export function parseInviteConfigForm(values: unknown) {
  return inviteConfigSchema.safeParse(values);
}
