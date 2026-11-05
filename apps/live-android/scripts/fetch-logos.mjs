// Downloads the team crests the app shows into public/logos/<id>.png (issue #230). Runs during `npm run build`
// (it needs network; CI has it). It never fails the build: a missing crest is shown as the team's initials.
//   ids = teams of the demo matches + teams of the calendars of the catalogue config/competitions.json (FEB ones; FBCYL has its own below)
import fs from "node:fs";
import path from "node:path";
import { downloadLogos, fbcylLogosFromCalendar, resizeLogo, teamIdsFromCalendar } from "./lib/logos.mjs";
import { buildManifest } from "./lib/manifest.mjs";

const appRoot = path.resolve(import.meta.dirname, "..");
const repoRoot = path.resolve(appRoot, "../..");
const outDir = path.join(appRoot, "public", "logos");

const ids = new Set();
for (const match of buildManifest(path.join(repoRoot, "tests/recordings"))) {
  ids.add(match.home.id);
  ids.add(match.away.id);
}

try {
  const config = JSON.parse(fs.readFileSync(path.join(repoRoot, "config/competitions.json"), "utf8"));
  const feb = (config.competitions ?? []).filter((c) => c.active !== false && c.league !== "fbcyl" && c.competition_url);
  for (const scrape of feb) {
    try {
      const response = await fetch(scrape.competition_url, { headers: { "User-Agent": "Mozilla/5.0 BasketLab" } });
      if (response.ok) for (const id of teamIdsFromCalendar(await response.text())) ids.add(id);
      else console.warn(`fetch-logos: calendar ${scrape.competition} answered HTTP ${response.status}`);
    } catch (error) {
      console.warn(`fetch-logos: calendar ${scrape.competition} not read (${error.message})`);
    }
  }
} catch (error) {
  console.warn(`fetch-logos: config/competitions.json not read (${error.message})`);
}

// FBCYL (issue #514): its crests are not on FEB's server; the calendar of each group lists them (config/fbcyl_groups.json)
const fbcyl = [];
try {
  const config = JSON.parse(fs.readFileSync(path.join(repoRoot, "config/fbcyl_groups.json"), "utf8"));
  for (const group of config.groups ?? []) {
    try {
      const response = await fetch(`${config.calendar_api}/${group}/0`, { headers: { "User-Agent": "Mozilla/5.0 BasketLab" } });
      if (response.ok) fbcyl.push(...fbcylLogosFromCalendar(JSON.parse(Buffer.from(await response.text(), "base64").toString("utf8"))));
      else console.warn(`fetch-logos: FBCYL group ${group} answered HTTP ${response.status}`);
    } catch (error) {
      console.warn(`fetch-logos: FBCYL group ${group} not read (${error.message})`);
    }
  }
} catch (error) {
  console.warn(`fetch-logos: config/fbcyl_groups.json not read (${error.message})`);
}
const fbcylIds = new Set(fbcyl.map(item => item.id));
const result = await downloadLogos([...[...ids].filter(id => !fbcylIds.has(id)), ...fbcyl], outDir, fetch, { resize: resizeLogo });
console.log(`fetch-logos: ${ids.size} teams, ${result.saved} downloaded, ${result.skipped} already there, ${result.failed.length} failed`);
for (const f of result.failed) console.warn(`  ${f.id}: ${f.reason}`);
