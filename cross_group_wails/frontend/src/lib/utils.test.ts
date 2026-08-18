import { describe, expect, it } from "vitest";
import { formatDateTime, formatTimelineText, hasMojibake, toEpochMs } from "./utils";

describe("toEpochMs", () => {
  it("converts seconds to ms", () => {
    expect(toEpochMs(1_700_000_000)).toBe(1_700_000_000_000);
  });
  it("keeps milliseconds", () => {
    expect(toEpochMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
  it("handles string seconds", () => {
    expect(toEpochMs("1700000000")).toBe(1_700_000_000_000);
  });
});

describe("formatDateTime", () => {
  it("does not render 1970 for second timestamps", () => {
    const text = formatDateTime(1_700_000_000);
    expect(text.includes("1970")).toBe(false);
  });
});

describe("hasMojibake", () => {
  it("detects ascii question marks", () => {
    expect(hasMojibake("?".repeat(4))).toBe(true);
    expect(hasMojibake("ok")).toBe(false);
  });
});

describe("formatTimelineText", () => {
  it("uses plain Chinese for the 15:09 error timeline", () => {
    expect(formatTimelineText("created", "20260818-150905-6a20")).toBe("任务已创建");
    expect(formatTimelineText("started", "total=1454")).toBe("开始邀请，一共 1454 人");
    expect(
      formatTimelineText(
        "error",
        "无法获取来源群信息，请确认群号正确，并保留过跨群邀请的抓包记录",
      ),
    ).toBe(
      "打不开来源群，没法开始邀请。请核对来源群号是否填对；如果从没从这个群往外拉过人，请先在 QQ 里手动从该群邀请一次，再回来重试。",
    );
  });

  it("does not leak english keys", () => {
    expect(formatTimelineText("batch_start", "batch=3")).toBe("开始第 3 批");
    expect(formatTimelineText("members_loaded", "88")).toBe("已加载 88 名成员");
    expect(formatTimelineText("completed", "已完成")).toBe("已完成");
    expect(formatTimelineText("created", "")).not.toMatch(/[A-Za-z=]/);
    expect(formatTimelineText("started", "total=1454")).not.toMatch(/[A-Za-z=]/);
  });
});
