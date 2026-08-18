import { afterEach, describe, expect, it, vi } from "vitest";
import { LOG_LEVEL_LABELS, LOG_MODULE_LABELS, parseLogLine, useLogStore } from "./useLogStore";

const PREPARE = "\u6b63\u5728\u51c6\u5907\u8de8\u7fa4\u9080\u8bf7...";
const ABORT =
  "\u5f02\u5e38\u7ec8\u6b62: \u65e0\u6cd5\u83b7\u53d6\u6765\u6e90\u7fa4\u4fe1\u606f\uff0c\u8bf7\u786e\u8ba4\u7fa4\u53f7\u6b63\u786e";
const DONE = "\u4efb\u52a1\u7ed3\u675f";

describe("parseLogLine", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps the original event time from [HH:MM:SS] instead of now", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-18T15:09:56"));
    const a = parseLogLine(`[15:09:05] ${PREPARE}`);
    vi.setSystemTime(new Date("2026-08-18T16:00:00"));
    const b = parseLogLine(`[15:09:05] ${PREPARE}`);
    expect(a?.time).toBe("15:09:05");
    expect(b?.time).toBe("15:09:05");
    expect(a?.message).toBe(PREPARE);
    expect(a?.level).toBe("INFO");
    expect(a?.module).toBe("INVITE");
  });

  it("classifies abort as error and system", () => {
    const e = parseLogLine(`[15:09:05] ${ABORT}`);
    expect(e?.time).toBe("15:09:05");
    expect(e?.level).toBe("ERROR");
    expect(e?.module).toBe("SYSTEM");
    expect(e?.message).toContain("\u5f02\u5e38\u7ec8\u6b62");
  });

  it("does not invent a clock time when the line has no timestamp", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-18T15:09:56"));
    const e = parseLogLine(DONE);
    expect(e?.time).toBe("");
    expect(e?.message).toBe(DONE);
  });
});

describe("useLogStore.setFromRaw", () => {
  it("does not rewrite timestamps on refresh", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-18T15:09:56"));
    const lines = [`[15:09:05] ${PREPARE}`, `[15:09:05] ${ABORT}`, `[15:09:05] ${DONE}`];
    useLogStore.getState().setFromRaw(lines);
    vi.setSystemTime(new Date("2026-08-18T18:22:11"));
    useLogStore.getState().setFromRaw(lines);
    const times = useLogStore.getState().entries.map((e) => e.time);
    expect(times).toEqual(["15:09:05", "15:09:05", "15:09:05"]);
    vi.useRealTimers();
    useLogStore.getState().clear();
  });
});

describe("Chinese labels", () => {
  it("maps levels and modules to Chinese", () => {
    expect(LOG_LEVEL_LABELS).toEqual({
      INFO: "\u4fe1\u606f",
      SUCCESS: "\u6210\u529f",
      WARN: "\u8b66\u544a",
      ERROR: "\u9519\u8bef",
    });
    expect(LOG_MODULE_LABELS.INVITE).toBe("\u9080\u8bf7");
    expect(LOG_MODULE_LABELS.SYSTEM).toBe("\u7cfb\u7edf");
    expect(LOG_MODULE_LABELS.NAPCAT).toBe("\u996d\u996d\u5b9a\u5236");
  });
});
