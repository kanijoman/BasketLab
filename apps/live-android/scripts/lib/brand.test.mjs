// Issue #311: the launcher icon and the splash of the Android app are the BasketLab Live mark (design/brand), at every density.
// @vitest-environment node
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { describe, expect, it } from "vitest";
import { LAUNCHER, NAVY, SPLASH, launcherSpecs, splashSpecs } from "./brand.mjs";

const res = path.resolve(import.meta.dirname, "../../android/app/src/main/res");
const brand = path.resolve(import.meta.dirname, "../../../../design/brand");

describe("brand specs", () => {
  it("has a launcher icon of every kind at the five densities", () => {
    const specs = launcherSpecs();
    expect(specs).toHaveLength(15);
    expect(specs.find((s) => s.file === "mipmap-xxxhdpi/ic_launcher.png").size).toBe(192);
    expect(specs.find((s) => s.file === "mipmap-xxxhdpi/ic_launcher_foreground.png").size).toBe(432);
    expect(specs.find((s) => s.file === "mipmap-mdpi/ic_launcher_round.png").size).toBe(48);
  });

  it("has a splash for the default and for every portrait and landscape density", () => {
    const specs = splashSpecs();
    expect(specs).toHaveLength(11);
    expect(specs.find((s) => s.file === "drawable-port-xxxhdpi/splash.png")).toMatchObject({ width: 1280, height: 1920 });
    expect(specs.find((s) => s.file === "drawable-land-hdpi/splash.png")).toMatchObject({ width: 800, height: 480 });
  });
});

describe("the brand files are there and the generated resources follow them", () => {
  it("has the three SVGs of the brand", () => {
    for (const name of ["live-mark.svg", "live-icon.svg", "live-foreground.svg"]) {
      expect(fs.readFileSync(path.join(brand, name), "utf8")).toContain("#E8651A");
    }
  });

  // Issue #614: the ends of the white pulse go outside the ball and vanished on the light theme; a navy line under it, as the web's mark (#613).
  it("draws the pulse of the mark over a navy line, so its ends are seen on a light screen", () => {
    const mark = fs.readFileSync(path.join(brand, "live-mark.svg"), "utf8");
    const pulse = 'd="M 6 54 L 30 54 L 38 36 L 51 70 L 60 44 L 66 54 L 94 54"';
    const navy = mark.indexOf(`${pulse} fill="none" stroke="#1A2744"`);
    expect(navy).toBeGreaterThan(-1);
    expect(navy).toBeLessThan(mark.indexOf(`${pulse} fill="none" stroke="#FFFFFF"`));
  });

  it("every launcher icon has the size of its spec", async () => {
    for (const spec of launcherSpecs()) {
      const meta = await sharp(path.join(res, spec.file)).metadata();
      expect([meta.width, meta.height], spec.file).toEqual([spec.size, spec.size]);
    }
  });

  it("the adaptive foreground is transparent around the mark and the legacy icon is not", async () => {
    const fg = await sharp(path.join(res, "mipmap-xxxhdpi/ic_launcher_foreground.png")).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    expect(fg.data[3]).toBe(0);                                         // the corner is see-through: the navy comes from the background
    const legacy = await sharp(path.join(res, "mipmap-xxxhdpi/ic_launcher.png")).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const centre = ((96 * 192) + 96) * 4;
    expect(legacy.data[centre + 3]).toBe(255);
  });

  it("every splash has its size and is dark navy at its corner, with the mark in the middle", async () => {
    for (const spec of splashSpecs()) {
      const { data, info } = await sharp(path.join(res, spec.file)).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      expect([info.width, info.height], spec.file).toEqual([spec.width, spec.height]);
      expect([data[0], data[1], data[2]], spec.file).toEqual(NAVY);
      const mid = ((Math.floor(info.height / 2) * info.width) + Math.floor(info.width / 2)) * 3;
      expect([data[mid], data[mid + 1], data[mid + 2]], spec.file).not.toEqual(NAVY);
    }
  });

  it("the adaptive icon is on the navy of the brand, not on the white of the template", () => {
    expect(fs.readFileSync(path.join(res, "values/ic_launcher_background.xml"), "utf8")).toContain("#1A2744");
    expect(LAUNCHER.length).toBe(5);
    expect(SPLASH.port.length + SPLASH.land.length).toBe(10);
  });
});
