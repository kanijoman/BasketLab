// The demo matches the app can replay (issue #223): every recording of tests/recordings/ that has its package,
// newest first, except the default of demos.json (issue #441), which goes first: it is the match the app opens with; the bundled sample game is only a fallback.
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

/** `SEGUNDA_FEB_2026_2027_Liga_Regular_A` -> `SEGUNDA FEB · Liga Regular A` (the season is left out); a name without season is just spaced. */
export function competitionOfCollection(collection) {
  if (!collection) return "";
  const fbcyl = /^FBCYL_.*_20\d\d_?$/.exec(String(collection));        // FBCYL names end with the year of the season
  const parts = fbcyl ? [String(collection).replace(/_20\d\d_?$/, "")] : String(collection).split(/_20\d\d_20\d\d_?/);
  const clean = (text) => text.replace(/_+/g, " ").trim();
  return parts.length > 1 && parts[1] ? `${clean(parts[0])} · ${clean(parts[1])}` : clean(parts[0]);
}

/** The package of a demo: its collection and the team whose point of view it has ("" when the file does not say). */
function packageInfo(file) {
  try {
    const body = JSON.parse(fs.readFileSync(file, "utf8")).package ?? {};
    return { competition: competitionOfCollection(body.collection), teamId: body.team?.id ? String(body.team.id) : "" };
  } catch {
    return { competition: "", teamId: "" };
  }
}

/** `demos.json` of the folder: `{ "default": "<code>" }`, the match the app opens with; without it (or broken) the newest one is. */
function defaultCode(recordingsDir) {
  try {
    return String(JSON.parse(fs.readFileSync(path.join(recordingsDir, "demos.json"), "utf8")).default ?? "");
  } catch {
    return "";
  }
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
      ...packageInfo(path.join(recordingsDir, `${code}.package.json`)),
    });
  }
  matches.sort((a, b) => b.date.localeCompare(a.date) || b.code.localeCompare(a.code));
  const first = matches.findIndex((m) => m.code === defaultCode(recordingsDir));   // the app opens with the first one
  return first > 0 ? [matches[first], ...matches.slice(0, first), ...matches.slice(first + 1)] : matches;
}
