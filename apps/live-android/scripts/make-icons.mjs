// Writes the launcher icon and the splash of the Android app from the brand SVGs (issue #311):
//   node scripts/make-icons.mjs      (needs `sharp`, already a dependency of the app)
// The results are committed (android/app/src/main/res/...), so the build does not depend on this script: run it when the brand changes.
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { NAVY, launcherSpecs, splashSpecs } from "./lib/brand.mjs";

const appRoot = path.resolve(import.meta.dirname, "..");
const res = path.join(appRoot, "android/app/src/main/res");
const brand = path.resolve(appRoot, "../../design/brand");
const svg = (name) => fs.readFileSync(path.join(brand, name));
const navyHex = "#" + NAVY.map((c) => c.toString(16).padStart(2, "0")).join("").toUpperCase();

const write = async (file, buffer) => {
  const target = path.join(res, file);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, buffer);
};

const roundMask = (size) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#fff"/></svg>`);

for (const { file, size, kind } of launcherSpecs()) {
  const source = svg(kind === "foreground" ? "live-foreground.svg" : "live-icon.svg");
  let image = sharp(source, { density: 600 }).resize(size, size);
  if (kind === "round") {
    image = sharp(await image.png().toBuffer()).composite([{ input: await sharp(roundMask(size)).png().toBuffer(), blend: "dest-in" }]);
  }
  await write(file, await image.png().toBuffer());
}

// the splash: the mark (about a third of the short side) in the middle of the navy of the brand
const mark = svg("live-mark.svg");
for (const { file, width, height } of splashSpecs()) {
  const side = Math.round(Math.min(width, height) * 0.34);
  const centred = await sharp(mark, { density: 600 }).resize(side, side).png().toBuffer();
  await write(file, await sharp({ create: { width, height, channels: 3, background: { r: NAVY[0], g: NAVY[1], b: NAVY[2] } } })
    .composite([{ input: centred, gravity: "center" }]).png().toBuffer());
}

// the adaptive icon sits on the navy of the brand
fs.writeFileSync(path.join(res, "values/ic_launcher_background.xml"),
  `<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">${navyHex}</color>\n</resources>\n`);
console.log(`make-icons: ${launcherSpecs().length} launcher icons, ${splashSpecs().length} splash images, background ${navyHex}`);
