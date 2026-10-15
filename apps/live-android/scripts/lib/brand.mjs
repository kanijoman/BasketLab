// What the Android resources of the app are made of (issue #311): the launcher icon and the splash, from design/brand/*.svg.
// scripts/make-icons.mjs writes them; scripts/lib/brand.test.mjs checks that they are there, at the right size.
export const NAVY = [0x1a, 0x27, 0x44];

// density -> launcher icon (legacy and round, dp 48) and adaptive foreground (dp 108)
export const LAUNCHER = [
  ["mdpi", 48, 108], ["hdpi", 72, 162], ["xhdpi", 96, 216], ["xxhdpi", 144, 324], ["xxxhdpi", 192, 432],
];

// the splash images of a Capacitor project: the default one and one per density and orientation (width x height in px)
export const SPLASH = {
  default: [480, 320],
  port: [["mdpi", 320, 480], ["hdpi", 480, 800], ["xhdpi", 720, 1280], ["xxhdpi", 960, 1600], ["xxxhdpi", 1280, 1920]],
  land: [["mdpi", 480, 320], ["hdpi", 800, 480], ["xhdpi", 1280, 720], ["xxhdpi", 1600, 960], ["xxxhdpi", 1920, 1280]],
};

export function launcherSpecs() {
  return LAUNCHER.flatMap(([density, size, foreground]) => [
    { file: `mipmap-${density}/ic_launcher.png`, size, kind: "icon" },
    { file: `mipmap-${density}/ic_launcher_round.png`, size, kind: "round" },
    { file: `mipmap-${density}/ic_launcher_foreground.png`, size: foreground, kind: "foreground" },
  ]);
}

export function splashSpecs() {
  const [w, h] = SPLASH.default;
  return [
    { file: "drawable/splash.png", width: w, height: h },
    ...["port", "land"].flatMap((o) => SPLASH[o].map(([d, width, height]) => ({ file: `drawable-${o}-${d}/splash.png`, width, height }))),
  ];
}
