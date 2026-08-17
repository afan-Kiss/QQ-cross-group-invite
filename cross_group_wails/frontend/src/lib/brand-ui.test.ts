import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

function walk(dir: string, acc: string[] = []): string[] {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) {
      if (name === "node_modules") continue;
      walk(full, acc);
    } else if (/\.(tsx|ts)$/.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx")) {
      acc.push(full);
    }
  }
  return acc;
}

describe("brand UI", () => {
  it("user-visible UI sources do not show NapCat label", () => {
    const files = walk(SRC).filter((f) => {
      const rel = f.replace(/\\/g, "/");
      // bridge may keep internal English bootstrap key for Go contract
      if (rel.endsWith("/lib/wails-bridge.ts")) return false;
      if (rel.includes("/store/") || rel.includes("/lib/") || rel.includes("/hooks/")) return false;
      return /\.(tsx)$/.test(rel);
    });
    const offenders: string[] = [];
    for (const f of files) {
      const text = fs.readFileSync(f, "utf8");
      const noComments = text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
      if (/NapCat/.test(noComments)) {
        offenders.push(path.relative(SRC, f));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("formal UI has no NapCat open-source external links", () => {
    const files = walk(SRC).filter((f) => f.endsWith(".tsx"));
    const offenders: string[] = [];
    for (const f of files) {
      const text = fs.readFileSync(f, "utf8");
      if (/napcat\.github|github\.com\/.*[Nn]ap[Cc]at|napcat\.qq|napneko/i.test(text)) {
        offenders.push(path.relative(SRC, f));
      }
      if (/https?:\/\/(?!127\.0\.0\.1)/.test(text) && /NapCat|napcat/i.test(text)) {
        offenders.push(path.relative(SRC, f));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("About page has no dead update button", () => {
    const about = fs.readFileSync(path.join(SRC, "pages", "AboutPage.tsx"), "utf8");
    expect(about).not.toMatch(/\u68c0\u67e5\u66f4\u65b0/);
    expect(about).toMatch(/\u996d\u996d\u5b9a\u5236\u72b6\u6001/);
    expect(about).toMatch(/\u6253\u5f00\u65e5\u5fd7\u76ee\u5f55/);
  });
});
