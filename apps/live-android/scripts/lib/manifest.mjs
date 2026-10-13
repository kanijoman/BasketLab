// The demo matches the app can replay (issue #223): every recording of tests/recordings/ that has its package,
// newest first. The first one is the default match of the app; the bundled sample game is only a fallback.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

/** "10-10-2026 - 17:00" (FEB) -> "2026-10-10T17:00"; "" when it cannot be read. */
export function parseStart(text) {
  const m = /^(\d{2})-(\d{2})-(\d{4})\s*-\s*(\d{2}):(\d{2})/.exec(String(text ?? ""));
  return m ? `${m[3]}-${m[2]}-${m[1]}T${m[4]}:${m[5]}` : "";
}

/** "MIPELLETYMAS B.F. LEON" -> "Mipelletymas B.F. Leon" (abbreviations with dots stay as they are). */
export function titleCase(name) {
  return String(name)
    .split(/\s+/)
    .map((w) => (w.includes(".") ? w : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

export function buildManifest(recordingsDir) {
  if (!fs.existsSync(recordingsDir)) return [];
  const matches = [];
  for (const file of fs.readdirSync(recordingsDir).filter((f) => f.endsWith(".rec.json.gz"))) {
    const code = file.replace(".rec.json.gz", "");
    if (!fs.existsSync(path.join(recordingsDir, `${code}.package.json`))) continue; // the engine needs the package
    const pack = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(recordingsDir, file))).toString("utf8"));
    const [home, away] = (pack.base?.HEADER?.TEAM ?? []).map((t) => ({ id: String(t.id), name: String(t.name).trim() }));
    if (!home || !away) continue;
    matches.push({
      code,
      title: `${titleCase(home.name)} – ${titleCase(away.name)}`,
      home,
      away,
      date: parseStart(pack.base.HEADER.starttime),
      recording: `${code}.recording.json`,
      package: `${code}.package.json`,
    });
  }
  return matches.sort((a, b) => b.date.localeCompare(a.date) || b.code.localeCompare(a.code));
}
