#!/usr/bin/env node
// Puts an icon on the desktop that opens a project's bench: one click starts the bench in the background, with no window, and
// opens it in the browser; if that project's bench is already running, the click just opens it.
// Node 18 or newer, no packages.   node shortcut.mjs [--project DIR] [--port N] [--ledger FILE] [--name TEXT] [--to FOLDER] [--no-open]
//   --project  the project the icon opens (default: the current folder)
//   --ledger   the checks ledger, when the project keeps it under another name than .gates.jsonl (passed on to the bench)
//   --name     the icon's name (default: "<project folder> bench")
//   --to       where to put it (default: the desktop)
//   --no-open  the icon starts the bench without opening the browser (for testing a setup)
//
// Windows: a shortcut (.lnk) with the CorvusWing icon, run through the console host's headless mode, so no console window appears.
// macOS:   a .command file; double-clicking it opens Terminal for a moment while the bench starts in the background.
// Linux:   a .desktop launcher; some desktops ask once to "Allow Launching" it.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SERVE = path.join(HERE, "serve.mjs");

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > 1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const PROJECT = path.resolve(arg("--project", process.cwd()));
const PORT = arg("--port", "4477");
const NAME = arg("--name", `${path.basename(PROJECT)} bench`).replace(/[\\/:*?"<>|]/g, "-");
const TO = arg("--to", null);
const LEDGER = arg("--ledger", null);
const OPEN = !process.argv.includes("--no-open");

function refuse(why) {
  console.error(`REFUSED: ${why}`);
  process.exit(2);
}
if (!fs.existsSync(PROJECT) || !fs.statSync(PROJECT).isDirectory()) refuse(`the project folder ${PROJECT} does not exist.`);
if (!fs.existsSync(SERVE)) refuse(`serve.mjs is not beside this file (${HERE}).`);
if (!/^\d+$/.test(PORT)) refuse("--port must be a whole number.");
if (TO && !fs.existsSync(TO)) refuse(`the folder ${TO} does not exist.`);

if (LEDGER && !fs.existsSync(path.resolve(PROJECT, LEDGER))) refuse(`the ledger ${LEDGER} is not in ${PROJECT}.`);

const benchArgs = ["--project", PROJECT, "--port", PORT, ...(LEDGER ? ["--ledger", LEDGER] : []), ...(OPEN ? ["--open"] : []), "--detach"];

function desktop() {
  const d = path.join(os.homedir(), "Desktop");
  return fs.existsSync(d) ? d : null;
}

if (process.platform === "win32") {
  const quote = (s) => `"${s}"`;
  const conhost = path.join(process.env.SystemRoot || "C:\\Windows", "System32", "conhost.exe");
  const headless = fs.existsSync(conhost);
  // With the console host's headless mode, node runs with no window at all; without it, the shortcut starts minimized.
  const target = headless ? conhost : process.execPath;
  const args = [...(headless ? ["--headless", quote(process.execPath)] : []), quote(SERVE), ...benchArgs.map((a) => (a.includes(" ") || a.includes("\\") ? quote(a) : a))].join(" ");
  // Every value reaches PowerShell through the environment, never through the script's own text, so no path can change the script.
  const script = [
    "$ErrorActionPreference = 'Stop'",
    "$dir = if ($env:CB_TO) { $env:CB_TO } else { [Environment]::GetFolderPath('Desktop') }",
    "$lnk = Join-Path $dir ($env:CB_NAME + '.lnk')",
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)",
    "$s.TargetPath = $env:CB_TARGET",
    "$s.Arguments = $env:CB_ARGS",
    "$s.WorkingDirectory = $env:CB_PROJECT",
    "$s.WindowStyle = 7",
    "$s.IconLocation = $env:CB_ICON + ',0'",
    "$s.Description = $env:CB_DESC",
    "$s.Save()",
    "Write-Output $lnk",
  ].join("; ");
  const env = {
    ...process.env, CB_TO: TO || "", CB_NAME: NAME, CB_TARGET: target, CB_ARGS: args, CB_PROJECT: PROJECT,
    CB_ICON: path.join(HERE, "assets", "corvuswing-tile.ico"), CB_DESC: `Open the CorvusWing bench for ${path.basename(PROJECT)}`,
  };
  execFile("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
    { env, windowsHide: true, timeout: 30000 }, (err, out, errText) => {
      if (err) refuse(`Windows did not make the shortcut: ${(errText || err.message).trim()}`);
      console.log(`Made ${out.trim()}`);
      console.log(headless ? "  It starts the bench with no window." : "  It starts the bench minimized (this Windows has no headless console host).");
    });
} else if (process.platform === "darwin") {
  const dir = TO || desktop();
  if (!dir) refuse("no Desktop folder was found; pass --to FOLDER.");
  const file = path.join(dir, `${NAME}.command`);
  const q = (s) => `'${s.replace(/'/g, `'"'"'`)}'`;
  fs.writeFileSync(file, `#!/bin/sh\n${[process.execPath, SERVE, ...benchArgs].map(q).join(" ")}\n`, { mode: 0o755 });
  console.log(`Made ${file}`);
  console.log("  Double-click it: Terminal opens for a moment while the bench starts in the background.");
} else {
  const dir = TO || desktop();
  if (!dir) refuse("no Desktop folder was found; pass --to FOLDER.");
  const file = path.join(dir, `${NAME}.desktop`);
  const q = (s) => `"${s.replace(/(["`$\\])/g, "\\$1")}"`;
  fs.writeFileSync(file, [
    "[Desktop Entry]", "Type=Application", `Name=${NAME}`, `Comment=Open the CorvusWing bench for ${path.basename(PROJECT)}`,
    `Exec=${[process.execPath, SERVE, ...benchArgs].map(q).join(" ")}`, `Icon=${path.join(HERE, "assets", "corvuswing-tile.png")}`,
    "Terminal=false", "",
  ].join("\n"), { mode: 0o755 });
  console.log(`Made ${file}`);
  console.log("  Some desktops ask once to \"Allow Launching\" a new launcher: right-click it and allow it.");
}
