#!/usr/bin/env node
// The CorvusWing bench: one page over a project's own notes, served on this machine only.
// Node 18 or newer, no packages.
//   node serve.mjs [--project DIR] [--port N] [--ledger FILE] [--open] [--detach] [--keep-running] [--check]
//   --check         serve nothing: print each panel FILLED, PARTLY or EMPTY, with the file, heading or table an empty one is read
//                   from, and exit (the agent's half of "Fit the project to the bench" in SKILL.md)
//   --open          open the page in the default browser once it is listening
//   --detach        start the bench in the background with no window and return at once (the desktop icon uses it); if a bench for
//                   this project already answers, open that one instead of starting a second
//   --keep-running  do not stop when the page is closed (by default the bench stops 45 s after its last page closes, or 3 min after
//                   it last heard from any page, once a page has been open; the page's Stop button stops it at once)
//
// What it reads, and only this: STATE.md, HANDOFF.md, PLAN.md, DECISIONS.md, INBOX.md, the read-path files' sizes, the checks
// ledger (.gates.jsonl unless --ledger names another), and `git` for the branch, the last commit and the uncommitted count.
// What it writes, and only this: INBOX.md, one appended message per Send.
// Who can reach it: this machine only (127.0.0.1). Every request must name this server as its host (a page on another site
// that points its own name at 127.0.0.1 is refused), and a message is accepted only with the key this launch put in the page
// and from this page's own origin, so no other web page can write into the inbox an agent reads.
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { execFile, spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HOST = "127.0.0.1";
const KB = 1024;
const READ_PATH = ["AGENTS.md", "CLAUDE.md", "PICKUP.md", "STATE.md", "HANDOFF.md"];
const INBOX = "INBOX.md";
const INBOX_HEADER = [
  "# INBOX",
  "",
  "Messages to the agent, written from the bench's Message Claude box, newest at the bottom. At the start of its next step the",
  "agent reads every message marked `waiting`, acts on it inside the house rules in AGENTS.md, and changes `waiting` to",
  "`read HH:MM` or `answered HH:MM: <one line>`. Nothing here is ever deleted.",
  "",
  "",
].join("\n");
const ENTRY = /^## (M-\d+) · (.+?) · (.*)$/;

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > 1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const PROJECT = path.resolve(arg("--project", process.cwd()));
const FIRST_PORT = Number(arg("--port", "4477"));
const LEDGER = arg("--ledger", ".gates.jsonl");
const OPEN = process.argv.includes("--open");
const DETACH = process.argv.includes("--detach");
const CHECK = process.argv.includes("--check");
const EXIT_WHEN_CLOSED = !process.argv.includes("--keep-running");
const BYE_MS = 45 * 1000;      // after the last page says goodbye: room for a reload, or another tab's heartbeat
const IDLE_MS = 3 * 60 * 1000; // no page heard from at all: a crashed browser never says goodbye
const KEY = crypto.randomBytes(18).toString("hex");

if (Number(process.versions.node.split(".")[0]) < 18) {
  console.error(`REFUSED: the bench needs Node 18 or newer; this is ${process.versions.node}.`);
  process.exit(2);
}
if (!fs.existsSync(PROJECT) || !fs.statSync(PROJECT).isDirectory()) {
  console.error(`REFUSED: the project folder ${PROJECT} does not exist.`);
  process.exit(2);
}
if (!Number.isInteger(FIRST_PORT) || FIRST_PORT < 1024 || FIRST_PORT > 65535) {
  console.error(`REFUSED: --port must be a whole number from 1024 to 65535.`);
  process.exit(2);
}

// ---------------------------------------------------------------- the project's files

function readDoc(name) {
  const p = path.join(PROJECT, name);
  try {
    const st = fs.statSync(p);
    if (!st.isFile()) return null;
    return { name, text: fs.readFileSync(p, "utf8").replace(/\r\n/g, "\n"), bytes: st.size };
  } catch {
    return null;
  }
}

// One markdown table row split into cells; a pipe inside `code` or written as \| stays inside its cell.
function cells(line) {
  const s = line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
  const out = [];
  let cur = "";
  let code = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "\\" && s[i + 1] === "|") { cur += "|"; i++; continue; }
    if (c === "`") code = !code;
    if (c === "|" && !code) { out.push(cur.trim()); cur = ""; continue; }
    cur += c;
  }
  out.push(cur.trim());
  return out;
}

const SEPARATOR = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

// Every table in a document, with the heading it sits under and each row's line number.
function tables(doc) {
  const lines = doc.text.split("\n");
  const found = [];
  let heading = "";
  for (let i = 0; i < lines.length; i++) {
    const h = /^#{1,6}\s+(.*)$/.exec(lines[i]);
    if (h) { heading = h[1].trim(); continue; }
    if (lines[i].trim().startsWith("|") && i + 1 < lines.length && SEPARATOR.test(lines[i + 1])) {
      const header = cells(lines[i]).map((x) => x.toLowerCase());
      const rows = [];
      let j = i + 2;
      for (; j < lines.length && lines[j].trim().startsWith("|"); j++) rows.push({ cells: cells(lines[j]), line: j + 1 });
      found.push({ heading, header, rows, line: i + 1 });
      i = j - 1;
    }
  }
  return found;
}

const isExample = (row) => /^example:/i.test(row.cells[0] || "");
const column = (header, ...names) => header.findIndex((h) => names.some((n) => h.startsWith(n)));
const cellOf = (t, row, ...names) => {
  const k = column(t.header, ...names);
  return k >= 0 ? row.cells[k] || "" : "";
};
// A template's own placeholder ("<what you are building>", "YYYY-MM-DD") is not a fact yet.
const placeholder = (s) => !s || /^<[^>]*>\.?$/.test(s.trim()) || /YYYY-MM-DD/.test(s);

function section(doc, title) {
  const lines = doc.text.split("\n");
  const i = lines.findIndex((l) => /^#{1,6}\s+/.test(l) && l.replace(/^#+\s+/, "").trim().toLowerCase() === title.toLowerCase());
  if (i < 0) return null;
  const body = [];
  for (let j = i + 1; j < lines.length && !/^#{1,6}\s+/.test(lines[j]); j++) body.push(lines[j]);
  const text = body.join("\n").trim();
  return placeholder(text) ? null : { text, line: i + 1 };
}

function readState() {
  const doc = readDoc("STATE.md");
  if (!doc) return { absent: "STATE.md is not in this project yet. The start-here skill writes it." };
  const checked = /Last checked at commit `([^`]*)` on branch `([^`]*)` \(([^)]*)\)/.exec(doc.text);
  const works = tables(doc).find((t) => /what works now/i.test(t.heading));
  const rows = works ? works.rows.filter((r) => !isExample(r)) : [];
  return {
    sentence: section(doc, "The project in one sentence"),
    done: section(doc, "Done looks like"),
    checked: checked && !placeholder(checked[1]) ? { commit: checked[1], branch: checked[2], date: checked[3] } : null,
    works: rows.map((r) => ({ area: r.cells[0] || "", status: r.cells[1] || "", how: r.cells[2] || "", line: r.line })),
    examplesHidden: works ? works.rows.length - rows.length : 0,
  };
}

function readNext() {
  const doc = readDoc("HANDOFF.md");
  if (!doc) return { absent: "HANDOFF.md is not in this project yet. The start-here skill writes it." };
  const all = tables(doc);
  const t = all.find((x) => /^next/i.test(x.heading)) || all.find((x) => column(x.header, "task") >= 0);
  if (!t) return { absent: "HANDOFF.md has no table of next tasks." };
  const real = t.rows.filter((r) => !isExample(r));
  const blocked = all.find((x) => /^blocked/i.test(x.heading));
  return {
    items: real.slice(0, 4).map((r) => ({
      id: cellOf(t, r, "id"), task: cellOf(t, r, "task"), done: cellOf(t, r, "done when", "done"),
      cancel: cellOf(t, r, "cancel"), size: cellOf(t, r, "size"), status: cellOf(t, r, "status"), line: r.line,
    })),
    total: real.length,
    blocked: blocked ? blocked.rows.filter((r) => !isExample(r)).length : 0,
    examplesHidden: t.rows.length - real.length,
  };
}

function lane(status) {
  const s = status.toLowerCase().trim();
  if (/^(done|merged|finished|complete|completed|closed|dropped|canceled|cancelled|thrown|abandoned|shipped)\b/.test(s)) return "closed";
  if (/^(in progress|in-progress|doing|active|started|working|review|in review|order written|blocked)\b/.test(s)) return "open";
  return "upcoming";
}

function readTasks() {
  const doc = readDoc("PLAN.md");
  if (!doc) return { absent: "PLAN.md is not in this project yet. The start-here skill writes it with you." };
  const t = tables(doc).find((x) => column(x.header, "task") >= 0 && column(x.header, "status") >= 0);
  if (!t) return { absent: "PLAN.md has no table with a Task and a Status column." };
  const real = t.rows.filter((r) => !isExample(r));
  const lanes = { open: [], upcoming: [], closed: [] };
  for (const r of real) {
    const status = cellOf(t, r, "status");
    lanes[lane(status)].push({
      id: cellOf(t, r, "id"), task: cellOf(t, r, "task"), milestone: cellOf(t, r, "milestone"),
      size: cellOf(t, r, "size"), status, line: r.line,
    });
  }
  return { lanes, line: t.line, examplesHidden: t.rows.length - real.length };
}

function readDecisions() {
  const doc = readDoc("DECISIONS.md");
  if (!doc) return { absent: "DECISIONS.md is not in this project yet. The start-here skill writes it." };
  const t = tables(doc).find((x) => column(x.header, "decision") >= 0);
  if (!t) return { absent: "DECISIONS.md has no table with a Decision column." };
  const real = t.rows.filter((r) => !isExample(r));
  return {
    newest: real.slice(-6).reverse().map((r) => ({
      id: cellOf(t, r, "id"), date: cellOf(t, r, "date"), decision: cellOf(t, r, "decision"),
      undo: cellOf(t, r, "reversal"), line: r.line,
    })),
    total: real.length,
    examplesHidden: t.rows.length - real.length,
  };
}

function when(v) {
  if (typeof v === "number") return new Date(v < 1e12 ? v * 1000 : v).toISOString();
  return typeof v === "string" && v.trim() ? v : null;
}

function readChecks(head) {
  let text;
  try {
    text = fs.readFileSync(path.resolve(PROJECT, LEDGER), "utf8"); // a name in the project, or a full path
  } catch {
    return { absent: `No checks ledger in this project yet (${LEDGER}). The gates skill builds one.`, ledger: LEDGER };
  }
  const last = new Map();
  let runs = 0;
  let unparsed = 0;
  for (const raw of text.split(/\r?\n/)) {
    if (!raw.trim()) continue;
    let o;
    try { o = JSON.parse(raw); } catch { unparsed++; continue; }
    const name = o && (o.name ?? o.gate ?? o.id);
    if (name == null) { unparsed++; continue; }
    runs++;
    const result = String(o.result ?? o.status ?? o.outcome ?? "").toUpperCase();
    const seconds = Number(o.seconds ?? o.secs ?? o.duration);
    last.set(String(name), {
      name: String(name), result: result || null, seconds: Number.isFinite(seconds) ? seconds : null,
      at: when(o.time ?? o.at ?? o.ts ?? o.when ?? o.date), commit: o.commit ? String(o.commit) : null,
    });
  }
  const gates = [...last.values()].map((g) => ({
    ...g,
    atHead: head && g.commit ? head.startsWith(g.commit) || g.commit.startsWith(head) : null,
  }));
  return { ledger: LEDGER, gates, runs, unparsed };
}

function readNotes() {
  const files = READ_PATH.map((name) => {
    const d = readDoc(name);
    return { name, bytes: d ? d.bytes : null };
  });
  return { files, total: files.reduce((s, f) => s + (f.bytes || 0), 0), warn: 300 * KB, budget: 400 * KB, ceiling: 500 * KB };
}

function readInbox() {
  const doc = readDoc(INBOX);
  if (!doc) return { messages: [], total: 0, waiting: 0 };
  const lines = doc.text.split("\n");
  const msgs = [];
  let cur = null;
  for (let i = 0; i < lines.length; i++) {
    const m = ENTRY.exec(lines[i]);
    if (m) { cur = { id: m[1], at: m[2].trim(), status: m[3].trim(), body: [], line: i + 1 }; msgs.push(cur); continue; }
    if (/^#{1,2}\s/.test(lines[i])) { cur = null; continue; }
    if (cur) cur.body.push(lines[i].replace(/^\\#/, "#"));
  }
  return {
    messages: msgs.slice(-8).reverse().map((m) => ({ ...m, body: m.body.join("\n").trim() })),
    total: msgs.length,
    waiting: msgs.filter((m) => /^waiting/i.test(m.status)).length,
  };
}

function appendInbox(text) {
  const p = path.join(PROJECT, INBOX);
  let existing = "";
  try { existing = fs.readFileSync(p, "utf8"); } catch { /* the first message makes the file */ }
  let max = 0;
  for (const m of existing.matchAll(/^## M-(\d+) · /gm)) max = Math.max(max, Number(m[1]));
  const id = `M-${String(max + 1).padStart(3, "0")}`;
  const d = new Date();
  const two = (n) => String(n).padStart(2, "0");
  const at = `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}`;
  // A line that starts with # inside a message is escaped, so a message can never forge another message's heading.
  const body = text.replace(/\r\n?/g, "\n").trim().split("\n").map((l) => (/^\s{0,3}#/.test(l) ? "\\" + l.trimStart() : l)).join("\n");
  let block = `## ${id} · ${at} · waiting\n\n${body}\n`;
  if (!existing) block = INBOX_HEADER + block;
  else block = (existing.endsWith("\n\n") || existing.endsWith("\r\n\r\n") ? "" : existing.endsWith("\n") ? "\n" : "\n\n") + block;
  if (existing.includes("\r\n")) block = block.replace(/\n/g, "\r\n");
  fs.appendFileSync(p, block);
  return { id, at };
}

function git(args) {
  return new Promise((resolve) => {
    execFile("git", ["-C", PROJECT, ...args], { windowsHide: true, timeout: 4000 }, (err, out) => resolve(err ? null : out.trim()));
  });
}

async function readGit() {
  if ((await git(["rev-parse", "--is-inside-work-tree"])) !== "true") {
    return { absent: "This project is not a git repository, or git is not installed." };
  }
  const branch = await git(["rev-parse", "--abbrev-ref", "HEAD"]);
  const log = await git(["log", "-1", "--format=%h%x1f%H%x1f%ct%x1f%s"]);
  const status = await git(["status", "--porcelain"]);
  let head = null;
  if (log) {
    const [short, full, ct, subject] = log.split("\x1f");
    head = { short, full, at: new Date(Number(ct) * 1000).toISOString(), subject };
  }
  return { branch, head, uncommitted: status == null ? null : status.split("\n").filter(Boolean).length };
}

async function collect() {
  const g = await readGit();
  return {
    project: path.basename(PROJECT),
    readAt: new Date().toISOString(),
    git: g,
    state: readState(),
    next: readNext(),
    tasks: readTasks(),
    decisions: readDecisions(),
    checks: readChecks(g.head ? g.head.full : null),
    notes: readNotes(),
    inbox: readInbox(),
  };
}

// The About tab: the kit's own README, LICENSE and NOTICE -- from the about/ folder an install puts beside this file, or from
// the kit's checkout when the bench runs from there.
function aboutDirs() {
  const dirs = [path.join(HERE, "about")];
  const kit = path.resolve(HERE, "..", "..");
  if (fs.existsSync(path.join(kit, "skills", "bench", "serve.mjs"))) dirs.push(kit);
  return dirs;
}
function readAbout() {
  const out = {};
  for (const name of ["README.md", "LICENSE", "NOTICE.md"]) {
    out[name] = null;
    for (const dir of aboutDirs()) {
      try { out[name] = fs.readFileSync(path.join(dir, name), "utf8").replace(/\r\n/g, "\n"); break; } catch { /* next */ }
    }
  }
  return out;
}

// ---------------------------------------------------------------- the server

const ASSETS = new Set(fs.existsSync(path.join(HERE, "assets")) ? fs.readdirSync(path.join(HERE, "assets")) : []);
const TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml" };
let PORT = FIRST_PORT;

function send(res, code, type, body, extra = {}) {
  res.writeHead(code, {
    "Content-Type": type, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer", "Cross-Origin-Resource-Policy": "same-origin", ...extra,
  });
  res.end(body);
}
const json = (res, code, obj) => send(res, code, "application/json; charset=utf-8", JSON.stringify(obj));
const refuse = (res, code, why) => json(res, code, { refused: why });

// ---------------------------------------------------------------- staying alive while a page is open, and stopping

let pageSeen = false;
let lastSeen = 0;
let byeTimer = null;
function touch() {
  pageSeen = true;
  lastSeen = Date.now();
  if (byeTimer) { clearTimeout(byeTimer); byeTimer = null; }
}
function shutdown(why) {
  console.log(`CorvusWing bench stopped: ${why}.`);
  server.close();
  setTimeout(() => process.exit(0), 150).unref();
}
setInterval(() => {
  if (EXIT_WHEN_CLOSED && pageSeen && Date.now() - lastSeen > IDLE_MS) shutdown("no page has been heard from for 3 minutes");
}, 15 * 1000).unref();

function openBrowser(url) {
  const [cmd, args] = process.platform === "win32" ? ["explorer.exe", [url]]
    : process.platform === "darwin" ? ["open", [url]] : ["xdg-open", [url]];
  try {
    const c = spawn(cmd, args, { detached: true, stdio: "ignore", windowsHide: true });
    c.on("error", () => console.log(`  open ${url} in your browser`));
    c.unref();
  } catch {
    console.log(`  open ${url} in your browser`);
  }
}

const hostOk = (req) => [`127.0.0.1:${PORT}`, `localhost:${PORT}`].includes(String(req.headers.host || "").toLowerCase());
const originOk = (req) => !req.headers.origin || [`http://127.0.0.1:${PORT}`, `http://localhost:${PORT}`].includes(req.headers.origin);

function page(res) {
  let html;
  try { html = fs.readFileSync(path.join(HERE, "bench.html"), "utf8"); } catch {
    return send(res, 500, "text/plain; charset=utf-8", `REFUSED: bench.html is missing beside ${path.join(HERE, "serve.mjs")}.`);
  }
  const nonce = crypto.randomBytes(16).toString("base64");
  html = html.replaceAll("__NONCE__", nonce).replace("__KEY__", KEY);
  send(res, 200, "text/html; charset=utf-8", html, {
    "Content-Security-Policy": `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; img-src 'self'; ` +
      "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  });
}

function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const parts = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > limit) { reject(new Error("too large")); req.destroy(); } else parts.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(parts).toString("utf8")));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    if (!hostOk(req)) return refuse(res, 403, "This bench answers only to its own address on this machine.");
    if (!originOk(req)) return refuse(res, 403, "Requests from other sites are refused.");
    const url = new URL(req.url, `http://${HOST}:${PORT}`);
    if (req.method === "GET" && url.pathname === "/api/hello") return json(res, 200, { bench: "corvuswing", project: PROJECT });
    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) { touch(); return page(res); }
    if (req.method === "GET" && url.pathname === "/api/state") { touch(); return json(res, 200, await collect()); }
    if (req.method === "GET" && url.pathname === "/api/about") { touch(); return json(res, 200, readAbout()); }
    if (req.method === "POST" && url.pathname === "/api/alive") {
      if (req.headers["x-bench-key"] !== KEY) return refuse(res, 403, "This launch's key is missing; reload the page.");
      touch();
      return send(res, 204, "text/plain", "");
    }
    if (req.method === "POST" && url.pathname === "/api/bye") {
      // the page's goodbye as it closes; a beacon cannot carry a header, so the key is its body
      let body = "";
      try { body = await readBody(req, 1 * KB); } catch { /* too large: not this page's goodbye */ }
      if (body.trim() !== KEY) return refuse(res, 403, "This launch's key is missing.");
      if (EXIT_WHEN_CLOSED && !byeTimer) byeTimer = setTimeout(() => shutdown("its page was closed"), BYE_MS);
      return send(res, 204, "text/plain", "");
    }
    if (req.method === "POST" && url.pathname === "/api/stop") {
      if (req.headers["x-bench-key"] !== KEY) return refuse(res, 403, "This launch's key is missing; reload the page.");
      res.on("finish", () => shutdown("stopped from the page"));
      return json(res, 200, { stopping: true });
    }
    if (req.method === "GET" && url.pathname.startsWith("/assets/")) {
      const name = decodeURIComponent(url.pathname.slice("/assets/".length));
      if (!ASSETS.has(name) || name !== path.basename(name)) return refuse(res, 404, "No such asset.");
      return send(res, 200, TYPES[path.extname(name).toLowerCase()] || "application/octet-stream",
        fs.readFileSync(path.join(HERE, "assets", name)), { "Cache-Control": "max-age=3600" });
    }
    if (req.method === "POST" && url.pathname === "/api/inbox") {
      if (req.headers["x-bench-key"] !== KEY) return refuse(res, 403, "This launch's key is missing; reload the page.");
      let text;
      try { text = JSON.parse(await readBody(req, 32 * KB)).text; } catch { return refuse(res, 400, "The message could not be read."); }
      if (typeof text !== "string" || !text.trim()) return refuse(res, 400, "An empty message is not sent.");
      if (text.length > 4000) return refuse(res, 400, "A message is at most 4,000 characters.");
      touch();
      return json(res, 200, appendInbox(text));
    }
    return refuse(res, 404, "Nothing here.");
  } catch (e) {
    return refuse(res, 500, `The bench hit an error: ${e.message}`);
  }
});

function listen(port, triesLeft) {
  server.once("error", (e) => {
    if (e.code === "EADDRINUSE" && triesLeft > 0) return listen(port + 1, triesLeft - 1);
    console.error(`REFUSED: the bench could not listen on ${HOST}:${port} (${e.code}).`);
    process.exit(3);
  });
  server.listen(port, HOST, () => {
    PORT = port;
    const url = `http://${HOST}:${port}/`;
    console.log(`CorvusWing bench for ${PROJECT}`);
    console.log(`  open ${url}`);
    if (port !== FIRST_PORT) console.log(`  (port ${FIRST_PORT} was taken, so this one is ${port})`);
    console.log("  this machine only; the page's Stop button or Ctrl+C stops it" +
      (EXIT_WHEN_CLOSED ? ", and it stops by itself once its page has been closed" : ""));
    if (OPEN) openBrowser(url);
  });
}

// A bench already running for this project, on the ports this one would try: its port, or null.
async function runningBench() {
  for (let p = FIRST_PORT; p <= FIRST_PORT + 10; p++) {
    try {
      const r = await fetch(`http://${HOST}:${p}/api/hello`, { signal: AbortSignal.timeout(800) });
      const h = r.ok ? await r.json() : null;
      if (h && h.bench === "corvuswing" && h.project === PROJECT) return p;
    } catch { /* nothing there, or not a bench */ }
  }
  return null;
}

// --check: the same reading the page gets (collect), said panel by panel, with what an empty panel is read from. An EMPTY panel is
// the bench telling the truth; this report is how an agent finds which file to bring into the template's shape, and checks it after.
async function checkReport() {
  const s = await collect();
  const rows = [];
  const add = (panel, state, what) => rows.push(`  ${state.padEnd(7)} ${panel.padEnd(16)} ${what}`);
  const hidden = (n) => (n ? ` (${n} "Example:" row${n === 1 ? "" : "s"} hidden)` : "");
  let filled = 0;

  if (s.state.absent) add("What's true now", "EMPTY", s.state.absent);
  else {
    const lacks = [];
    if (!s.state.sentence) lacks.push('text under "## The project in one sentence"');
    if (!s.state.done) lacks.push('text under "## Done looks like"');
    if (!s.state.checked) lacks.push("the line: Last checked at commit `<hash>` on branch `<branch>` (<date>)");
    if (!s.state.works.length) lacks.push('rows in the table under "## What works now" (Area | Status | How we know)' + hidden(s.state.examplesHidden));
    if (!lacks.length) { filled++; add("What's true now", "FILLED", `STATE.md, ${s.state.works.length} rows in "What works now"`); }
    else add("What's true now", lacks.length === 4 ? "EMPTY" : "PARTLY", "STATE.md lacks " + lacks.join("; "));
  }

  if (s.next.absent) add("Next", "EMPTY", s.next.absent + " (under \"## Next\": Id | Task | Done when | Cancel if | Size | Status)");
  else if (!s.next.total) add("Next", "EMPTY", 'HANDOFF.md: no rows in the table under "## Next"' + hidden(s.next.examplesHidden));
  else { filled++; add("Next", "FILLED", `HANDOFF.md, ${s.next.total} next, ${s.next.blocked} blocked`); }

  const lanes = s.tasks.lanes ? Object.values(s.tasks.lanes).reduce((n, l) => n + l.length, 0) : 0;
  if (s.tasks.absent) add("Tasks", "EMPTY", s.tasks.absent + " (for example Id | Milestone | Task | Done when | Cancel if | Size | Status)");
  else if (!lanes) add("Tasks", "EMPTY", "PLAN.md: the table with Task and Status columns has no rows" + hidden(s.tasks.examplesHidden));
  else {
    filled++;
    const l = s.tasks.lanes;
    add("Tasks", "FILLED", `PLAN.md, ${l.open.length} open, ${l.upcoming.length} upcoming, ${l.closed.length} closed`);
  }

  if (s.decisions.absent) add("Decisions", "EMPTY", s.decisions.absent + " (Id | Date | Decision | Why | What was rejected | Reversal cost)");
  else if (!s.decisions.total) add("Decisions", "EMPTY", "DECISIONS.md: the table has no rows" + hidden(s.decisions.examplesHidden));
  else { filled++; add("Decisions", "FILLED", `DECISIONS.md, ${s.decisions.total} decisions`); }

  const lineShape = "each line one JSON object with a name (or gate, id) and a result (or status); seconds, a time and the commit if known";
  if (s.checks.absent) {
    add("Checks", "EMPTY", s.checks.absent + " If the project's checks keep their record under another name, start the bench with" +
      " --ledger FILE (and make the icon with the same flag).");
  } else if (!s.checks.runs) add("Checks", "EMPTY", `${s.checks.ledger} has no line the bench can read (${s.checks.unparsed} unreadable): ${lineShape}`);
  else if (s.checks.unparsed) add("Checks", "PARTLY", `${s.checks.ledger}, ${s.checks.gates.length} checks; ${s.checks.unparsed} lines unreadable: ${lineShape}`);
  else { filled++; add("Checks", "FILLED", `${s.checks.ledger}, ${s.checks.gates.length} checks over ${s.checks.runs} runs`); }

  if (s.git.absent) add("Git", "EMPTY", s.git.absent);
  else { filled++; add("Git", "FILLED", `branch ${s.git.branch}, ${s.git.uncommitted} uncommitted`); }

  add("Messages", "READY", s.inbox.total ? `INBOX.md, ${s.inbox.total} messages, ${s.inbox.waiting} waiting` : "no messages yet (INBOX.md is made by the first Send)");

  return [`CorvusWing bench check: ${PROJECT}`, ...rows, "",
    `${filled} of 6 panels filled. An EMPTY or PARTLY panel is read from the file, heading or table named beside it; SKILL.md's`,
    '"Fit the project to the bench" says how to bring a file into that shape without inventing anything.'].join("\n");
}

if (CHECK) {
  console.log(await checkReport());
  process.exit(0);
} else if (DETACH) {
  // The desktop icon's way in: one bench per project, in the background, with no window, its output in a log file.
  const running = await runningBench();
  if (running) {
    console.log(`The bench for ${PROJECT} is already running: http://${HOST}:${running}/`);
    if (OPEN) openBrowser(`http://${HOST}:${running}/`);
  } else {
    const id = crypto.createHash("sha1").update(PROJECT).digest("hex").slice(0, 8);
    const log = path.join(os.tmpdir(), `corvuswing-bench-${id}.log`);
    const fd = fs.openSync(log, "a");
    const args = process.argv.slice(2).filter((a) => a !== "--detach");
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), ...args],
      { detached: true, windowsHide: true, stdio: ["ignore", fd, fd] });
    child.unref();
    console.log(`The bench for ${PROJECT} is starting in the background; its log is ${log}`);
  }
  setTimeout(() => process.exit(0), 50);
} else {
  listen(FIRST_PORT, 10);
}
