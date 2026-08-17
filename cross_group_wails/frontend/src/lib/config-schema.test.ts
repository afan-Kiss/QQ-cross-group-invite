import { describe, expect, it } from "vitest";
import { z } from "zod";

const schema = z
  .object({
    target_group_id: z.string().regex(/^\d+$/),
    source_group_id: z.string().regex(/^\d+$/),
    batch_count: z.string().refine((v) => {
      const n = Number(v);
      return Number.isInteger(n) && n >= 1 && n <= 1000;
    }),
    interval_ms: z.string().refine((v) => {
      const n = Number(v);
      return Number.isInteger(n) && n >= 100 && n <= 600000;
    }),
    filter_staff: z.boolean(),
  })
  .refine((v) => v.target_group_id !== v.source_group_id);

describe("invite config bounds", () => {
  const base = {
    target_group_id: "1",
    source_group_id: "2",
    batch_count: "20",
    interval_ms: "1500",
    filter_staff: true,
  };
  it("accepts edges", () => {
    expect(schema.safeParse({ ...base, batch_count: "1" }).success).toBe(true);
    expect(schema.safeParse({ ...base, batch_count: "1000" }).success).toBe(true);
    expect(schema.safeParse({ ...base, interval_ms: "100" }).success).toBe(true);
    expect(schema.safeParse({ ...base, interval_ms: "600000" }).success).toBe(true);
  });
  it("rejects invalid", () => {
    expect(schema.safeParse({ ...base, batch_count: "0" }).success).toBe(false);
    expect(schema.safeParse({ ...base, batch_count: "-1" }).success).toBe(false);
    expect(schema.safeParse({ ...base, batch_count: "1001" }).success).toBe(false);
    expect(schema.safeParse({ ...base, interval_ms: "99" }).success).toBe(false);
    expect(schema.safeParse({ ...base, source_group_id: "1" }).success).toBe(false);
    expect(schema.safeParse({ ...base, source_group_id: "" }).success).toBe(false);
  });
});
