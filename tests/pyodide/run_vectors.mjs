// Runs the shared live_core test vectors inside Pyodide and compares with the Python reference.
//
//   cd tests/pyodide && npm ci && node run_vectors.mjs
//
// Exit code 0 = Pyodide reproduces every expected result exactly; 1 = mismatch (details printed).
// Only src/live_core (standard library) is copied into the Pyodide file system, exactly what
// the Android app will bundle.

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { loadPyodide } from "pyodide";

const root = path.resolve(import.meta.dirname, "../..");
const vectorsPath = process.env.VECTORS_PATH ?? path.join(root, "tests/live_vectors/vectors.json");
const gamePath = path.join(root, "src/JSON_samples/feb_game.json");

function percentile(values, q) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
}

const started = performance.now();
const pyodide = await loadPyodide();
const loadMs = performance.now() - started;

// Bundle exactly what the app ships: src/__init__.py + src/live_core/*.py
pyodide.FS.mkdirTree("/app/src/live_core");
pyodide.FS.writeFile("/app/src/__init__.py", "");
const files = fs.readdirSync(path.join(root, "src/live_core")).filter((f) => f.endsWith(".py"));
for (const file of files) {
  pyodide.FS.writeFile(`/app/src/live_core/${file}`, fs.readFileSync(path.join(root, "src/live_core", file), "utf8"));
}
pyodide.runPython(`import sys; sys.path.insert(0, "/app")`);

const { expected, ...suite } = JSON.parse(fs.readFileSync(vectorsPath, "utf8"));
const importStarted = performance.now();
const runSuiteJson = pyodide.runPython("from src.live_core.vectors import run_suite_json; run_suite_json");
const importMs = performance.now() - importStarted;

const runStarted = performance.now();
const { result, timings_ms: timings } = JSON.parse(runSuiteJson(JSON.stringify(suite), fs.readFileSync(gamePath, "utf8")));
const runMs = performance.now() - runStarted;

const failures = [];
result.unit.forEach((actual, i) => {
  try {
    assert.deepStrictEqual(actual, expected.unit[i]);
  } catch {
    failures.push({ kind: "unit", fn: suite.unit[i].fn, args: JSON.stringify(suite.unit[i].args).slice(0, 160), actual, expected: expected.unit[i] });
  }
});
result.engine.checkpoints.forEach((actual, i) => {
  try {
    assert.deepStrictEqual(actual, expected.engine.checkpoints[i]);
  } catch {
    failures.push({ kind: "engine", checkpoint: suite.engine.checkpoints[i], actual, expected: expected.engine.checkpoints[i] });
  }
});

const total = result.unit.length + result.engine.checkpoints.length;
console.log(`Pyodide ${pyodide.version} | Python ${pyodide.runPython("import sys; sys.version.split()[0]")}`);
console.log(`bundle: ${files.length} files from src/live_core`);
console.log(`load ${loadMs.toFixed(0)} ms | import live_core ${importMs.toFixed(0)} ms | all vectors ${runMs.toFixed(0)} ms`);
console.log(`engine update (replay + engine + alerts): p50 ${percentile(timings, 0.5).toFixed(1)} ms, p95 ${percentile(timings, 0.95).toFixed(1)} ms, max ${Math.max(...timings).toFixed(1)} ms over ${timings.length} updates`);

if (failures.length) {
  console.error(`\nFAILED ${failures.length} of ${total}:`);
  for (const f of failures.slice(0, 5)) console.error(JSON.stringify(f, null, 1).slice(0, 900));
  process.exit(1);
}
console.log(`OK: ${total} of ${total} vectors identical to the Python reference`);
