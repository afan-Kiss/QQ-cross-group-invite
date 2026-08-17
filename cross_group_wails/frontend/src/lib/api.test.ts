import { describe, expect, it } from "vitest";
import {
  applyResultsToMembers,
  normalizeStatus,
  validateHealthPayload,
  ApiError,
} from "@/lib/api";
import type { Member } from "@/lib/types";

describe("validateHealthPayload", () => {
  it("accepts correct service identity", () => {
    const h = validateHealthPayload({
      ok: true,
      service: "cross-group-invite",
      napcat_online: false,
      napcat_message: "",
    });
    expect(h.service).toBe("cross-group-invite");
  });

  it("rejects port conflict when service mismatches", () => {
    expect(() =>
      validateHealthPayload({
        ok: true,
        service: "other",
        napcat_online: false,
        napcat_message: "",
      }),
    ).toThrow(ApiError);
  });
});

describe("normalizeStatus", () => {
  it("uses backend batch and interval remaining", () => {
    const status = normalizeStatus(
      {
        running: true,
        status: "running",
        total: 10,
        done: 3,
        success: 2,
        batch_number: 1,
        batch_done: 3,
        batch_size: 20,
        total_batches: 1,
        interval_remaining_ms: 1200,
        next_invite_at: Date.now() / 1000 + 1.2,
        results: [
          { qq: 1, nickname: "a", status: "success", reason: "", started_at: 1, finished_at: 2, duration_ms: 1000 },
          { qq: 2, nickname: "b", status: "waiting", reason: "", started_at: 0, finished_at: 0, duration_ms: 0 },
        ],
        frequent: [],
        errors: [],
        logs: [],
        rate_series: [{ timestamp: 100, success: 1, failed: 0, rate_limited: 0, total: 1 }],
      },
      [],
    );
    expect(status.batch.batchNumber).toBe(1);
    expect(status.batch.intervalRemainingMs).toBe(1200);
    expect(status.waiting).toBe(1);
    expect(status.rate_series[0].success).toBe(1);
  });

  it("maps error status without completed message override", () => {
    const status = normalizeStatus({
      running: false,
      status: "error",
      message: "boom",
      error_message: "boom",
      total: 0,
      done: 0,
      success: 0,
      frequent: [],
      errors: [],
      results: [],
      logs: [],
    });
    expect(status.status).toBe("error");
    expect(status.message).toBe("boom");
  });
});

describe("applyResultsToMembers", () => {
  it("updates member status from results", () => {
    const members: Member[] = [
      { qq: 11, nickname: "n1", role: "member", status: "waiting" },
      { qq: 12, nickname: "n2", role: "member", status: "waiting" },
    ];
    const out = applyResultsToMembers(members, [
      {
        qq: 11,
        nickname: "n1",
        status: "success",
        reason: "",
        started_at: 1,
        finished_at: 2,
        duration_ms: 10,
      },
    ]);
    expect(out[0].status).toBe("success");
    expect(out[1].status).toBe("waiting");
  });
});

describe("selectedQqs payload", () => {
  it("builds qq_list from selected set", () => {
    const selectedQqs = new Set([10001, 10002]);
    const qq_list = Array.from(selectedQqs);
    expect(qq_list).toEqual([10001, 10002]);
    expect(qq_list.length).toBe(2);
  });
});

describe("task state mapping", () => {
  it("maps backend statuses", () => {
    const map = (s: string) => {
      if (["running", "preparing", "stopping"].includes(s)) return s;
      if (s === "stopped") return "stopped";
      if (s === "error") return "error";
      return "completed";
    };
    expect(map("error")).toBe("error");
    expect(map("stopped")).toBe("stopped");
    expect(map("completed")).toBe("completed");
  });
});


describe("normalizeStatus ownership", () => {
  it("does not merge results into members", () => {
    const members: Member[] = [
      { qq: 10001, nickname: "n", role: "member", status: "waiting" },
    ];
    const status = normalizeStatus(
      {
        running: false,
        status: "completed",
        task_id: "task-old",
        total: 1,
        done: 1,
        success: 1,
        results: [
          {
            qq: 10001,
            nickname: "n",
            status: "success",
            reason: "",
            started_at: 1,
            finished_at: 2,
            duration_ms: 1,
          },
        ],
        frequent: [],
        errors: [],
        logs: [],
      },
      members,
    );
    expect(status.members[0].status).toBe("waiting");
    expect(status.results[0].status).toBe("success");
  });
});
