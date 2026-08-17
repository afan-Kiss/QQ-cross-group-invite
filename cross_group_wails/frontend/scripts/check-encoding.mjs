import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src");
const bad = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p);
    else if (/\.(ts|tsx|css|json)$/.test(name)) {
      const buf = fs.readFileSync(p);
      if (buf.includes(Buffer.from([0xef, 0xbf, 0xbd]))) bad.push(p);
    }
  }
}
walk(root);
if (bad.length) {
  console.error("Mojibake found:");
  for (const p of bad) console.error(p);
  process.exit(1);
}
console.log("encoding check OK");
