import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "i18n");

const en = JSON.parse(fs.readFileSync(path.join(root, "en.json"), "utf8"));
const enKeys = Object.keys(en);
let failures = 0;

for (const lang of ["hi", "kn", "ta", "te"]) {
  const raw = fs.readFileSync(path.join(root, `${lang}.json`), "utf8");
  let j;
  try {
    j = JSON.parse(raw);
  } catch (e) {
    console.log(`${lang} PARSE FAIL: ${e.message}`);
    failures += 1;
    continue;
  }
  const keys = Object.keys(j);
  const missing = enKeys.filter((k) => !(k in j));
  const extra = keys.filter((k) => !enKeys.includes(k));
  const bad = Object.entries(j).filter(([, v]) => typeof v !== "string" || !v.trim() || /\uFFFD/.test(v));
  console.log(
    `${lang}: keys=${keys.length} missing=${missing.length ? missing.join(",") : "none"} extra=${extra.length ? extra.join(",") : "none"} bad=${bad.length ? bad.map(([k]) => k).join(",") : "none"}`
  );
  if (missing.length || extra.length || bad.length) failures += 1;
}

process.exit(failures ? 1 : 0);
