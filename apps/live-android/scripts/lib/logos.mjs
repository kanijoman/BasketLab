// Team crests for the app (issue #230): ids from the FEB calendar of the competitions we follow, images downloaded
// during the build into public/logos/<id>.png. They are NOT committed (club crests in a public repository); a
// failed download only means the app shows the team's initials instead.
import fs from "node:fs";
import path from "node:path";

export const febLogoUrl = (id) => `https://imagenes.feb.es/imagen.aspx?i=${id}&ti=1`;

// FEB serves 500x500 PNGs of up to ~260 KB; the app shows them at 44-48 px, so they are shrunk to 96 px (~5 KB).
const MAX_BYTES = 1_000_000;
const LOGO_PX = 96;

/** Shrinks a crest to a small square PNG (sharp; a build dependency). */
export async function resizeLogo(bytes) {
  const { default: sharp } = await import("sharp");
  const out = await sharp(Buffer.from(bytes))
    .resize(LOGO_PX, LOGO_PX, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png({ palette: true })
    .toBuffer();
  return new Uint8Array(out);
}

/** Every team id linked from a FEB calendar page (``Equipo.aspx?i=<id>``), once each. */
export function teamIdsFromCalendar(html) {
  const ids = new Set();
  for (const m of String(html).matchAll(/Equipo\.aspx\?i=(\d+)/gi)) ids.add(m[1]);
  return [...ids];
}

/** Downloads the missing logos; never throws: returns what was saved, skipped and what failed (and why). */
export async function downloadLogos(ids, outDir, fetchFn = fetch, { resize = async (bytes) => bytes } = {}) {
  fs.mkdirSync(outDir, { recursive: true });
  const result = { saved: 0, skipped: 0, failed: [] };
  for (const id of ids) {
    const target = path.join(outDir, `${id}.png`);
    if (fs.existsSync(target)) {
      result.skipped += 1;
      continue;
    }
    try {
      const response = await fetchFn(febLogoUrl(id), { headers: { Accept: "image/*" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const type = response.headers?.get?.("content-type") ?? "";
      const body = new Uint8Array(await response.arrayBuffer());
      if (body.byteLength > MAX_BYTES) throw new Error("too large");
      if (!type.startsWith("image/")) throw new Error("not an image");
      fs.writeFileSync(target, await resize(body));
      result.saved += 1;
    } catch (error) {
      result.failed.push({ id, reason: error instanceof Error ? error.message : String(error) });
    }
  }
  return result;
}
