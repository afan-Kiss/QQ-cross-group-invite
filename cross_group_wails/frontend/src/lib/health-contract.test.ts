import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import type { HealthResponse } from "./types";

describe("health contract", () => {
  it("HealthResponse has session_match/required not session_id", () => {
    const sample: HealthResponse = {
      ok: true,
      service: "cross-group-invite",
      napcat_online: false,
      napcat_message: "",
      session_required: true,
      session_match: false,
    };
    expect("session_id" in sample).toBe(false);
    expect(sample.session_required).toBe(true);
  });

  it("frontend src does not use health.session_id as auth", () => {
    const root = path.resolve(__dirname, "..");
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of fs.readdirSync(dir)) {
        if (name === "health-contract.test.ts") continue;
        const p = path.join(dir, name);
        const st = fs.statSync(p);
        if (st.isDirectory()) walk(p);
        else if (/\.(ts|tsx)$/.test(name)) {
          const text = fs.readFileSync(p, "utf8");
          if (/health\.session_id\b/.test(text) || /session_id\?:\s*string/.test(text)) {
            hits.push(p);
          }
        }
      }
    };
    walk(root);
    expect(hits).toEqual([]);
  });
});
