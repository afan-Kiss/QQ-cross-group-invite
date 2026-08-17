import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src");
const bad = [];
let scanned = 0;

function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) {
      walk(p);
      continue;
    }
    if (!/\.(ts|tsx|css|json)$/.test(name)) continue;
    scanned += 1;
    const buf = fs.readFileSync(p);
    const rel = path.relative(root, p).replace(/\\/g, "/");

    if (buf.includes(Buffer.from([0xef, 0xbf, 0xbd]))) {
      bad.push({ file: rel, reason: "U+FFFD replacement char" });
      continue;
    }

    let text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
    } catch {
      bad.push({ file: rel, reason: "invalid UTF-8 bytes" });
      continue;
    }

    const strRe = /(["'`])([^"'`]*\?\?\?+[^"'`]*)\1/g;
    let m;
    while ((m = strRe.exec(text))) {
      bad.push({
        file: rel,
        reason: "ASCII ??? in string/template",
        sample: m[0].slice(0, 100),
      });
    }

    const jsxRe = />([^<{]*\?\?\?+[^<{]*)</g;
    while ((m = jsxRe.exec(text))) {
      bad.push({
        file: rel,
        reason: "ASCII ??? in JSX text",
        sample: m[0].slice(0, 100),
      });
    }

    if (/§Õ|锟斤拷|烫烫烫|þÿ/.test(text)) {
      bad.push({ file: rel, reason: "mojibake marker" });
    }
  }
}

walk(root);
console.log(`encoding scan files=${scanned} issues=${bad.length}`);
if (bad.length) {
  for (const item of bad) {
    console.error(
      `${item.file}: ${item.reason}${item.sample ? " | " + item.sample : ""}`,
    );
  }
  process.exit(1);
}
console.log("encoding check OK");
