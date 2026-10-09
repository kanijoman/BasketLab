// Copies into public/ everything the app ships and that lives outside apps/live-android:
//   public/engine/live_core.json  the Python sources of src/live_core (standard library only)
//   public/pyodide/               the Pyodide runtime (offline: nothing is fetched from a CDN)
//   public/demo/                  a preparation package + a finished FEB game for the demo replay
// Generated files are git-ignored; this runs before dev / build / test.

import fs from "node:fs";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const repoRoot = path.resolve(appRoot, "../..");
const out = (...p) => path.join(appRoot, "public", ...p);

fs.rmSync(out("engine"), { recursive: true, force: true });
fs.mkdirSync(out("engine"), { recursive: true });
const liveCore = path.join(repoRoot, "src/live_core");
const files = {};
for (const name of fs.readdirSync(liveCore).filter((f) => f.endsWith(".py")).sort()) {
  files[name] = fs.readFileSync(path.join(liveCore, name), "utf8");
}
fs.writeFileSync(out("engine", "live_core.json"), JSON.stringify({ files }));

fs.rmSync(out("pyodide"), { recursive: true, force: true });
fs.mkdirSync(out("pyodide"), { recursive: true });
const pyodideDir = path.join(appRoot, "node_modules/pyodide");
for (const name of ["pyodide.asm.wasm", "pyodide.asm.mjs", "python_stdlib.zip", "pyodide-lock.json"]) {
  fs.copyFileSync(path.join(pyodideDir, name), out("pyodide", name));
}

fs.rmSync(out("demo"), { recursive: true, force: true });
fs.mkdirSync(out("demo"), { recursive: true });
const vectors = JSON.parse(fs.readFileSync(path.join(repoRoot, "tests/live_vectors/vectors.json"), "utf8"));
fs.writeFileSync(out("demo", "package.json"), vectors.engine.package);
fs.copyFileSync(path.join(repoRoot, "src/JSON_samples/feb_game.json"), out("demo", "game.json"));

console.log(`sync-engine: ${Object.keys(files).length} live_core modules, Pyodide runtime, demo data`);
