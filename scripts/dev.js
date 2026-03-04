#!/usr/bin/env node
const { spawnSync } = require("node:child_process");

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("Usage: node scripts/dev.js <python_module_or_script> [args...]");
  process.exit(1);
}

const target = args[0];
const targetArgs = args.slice(1);

const looksLikeScriptPath = target.endsWith(".py") || target.includes("/") || target.includes("\\");
const pythonArgs = looksLikeScriptPath ? [target, ...targetArgs] : ["-m", target, ...targetArgs];

const candidates = process.platform === "win32" ? ["python", "py"] : ["python3", "python"];

let lastError = null;
for (const cmd of candidates) {
  const result = spawnSync(cmd, pythonArgs, { stdio: "inherit" });
  if (!result.error) {
    process.exit(result.status === null ? 1 : result.status);
  }
  lastError = result.error;
}

console.error("Could not find a Python interpreter. Install Python and ensure it's in PATH.");
if (lastError && lastError.message) {
  console.error(lastError.message);
}
process.exit(1);
