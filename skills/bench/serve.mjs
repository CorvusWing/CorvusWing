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
//   --rooms DIR     the folder of extra rooms (default: rooms/ beside this file); each room is one .js file, and only the .js and
//                   .css files found there at start are ever served
//   --self-test     start the real bench on scratch projects in the temp folder, check each row by name, and exit 0 when every
//                   row is as expected (1 when one is not, 78 when it cannot look); --break NAME switches one guard off to prove
//                   its row turns red
//
// What it reads, and only this: STATE.md, HANDOFF.md, PLAN.md, DECISIONS.md, INBOX.md, QUESTIONS.md and its pictures in
// .bench/pictures/<Q-id>/ (PNG, JPEG and WebP names only), the read-path files' sizes, the checks
// ledger (.gates.jsonl unless --ledger names another), and `git` for the branch, the last commit and the uncommitted count;
// and from the kit itself, the rooms folder's .js and .css files.
// What it writes, and only this: INBOX.md, one appended message per Send, per answer to a question or per set of picture verdicts.
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
const ROOMS = path.resolve(arg("--rooms", path.join(HERE, "rooms")));
const SELF_TEST = process.argv.includes("--self-test");
const SELF_TEST_CHILD = process.argv.includes("--self-test-child"); // a bench the self-test started; only it may run broken
const BREAKS = ["no-host-check", "no-origin-check", "no-key-check", "room-path-escape", "second-write",
  "two-recommended-shown", "answered-from-click", "answer-any-option", "picture-path-escape", "missing-as-blank", "verdict-dropped",
  "refused-as-fail", "refused-as-pass", "missing-as-pass", "pill-missing-as-pass"];
// A fault, unlike a break, plants a failure the self-test must REFUSE on (exit 78, "could not look"), never print as rows.
const FAULTS = ["git-denied", "git-index-held"];
const BREAK = arg("--break", "");

if (BREAK && ![...BREAKS, ...FAULTS].includes(BREAK)) {
  console.error(`REFUSED: --break ${BREAK} is not one of: ${[...BREAKS, ...FAULTS].join(", ")}.`);
  process.exit(2);
}
if (BREAK && !SELF_TEST && !SELF_TEST_CHILD) {
  console.error("REFUSED: --break goes with --self-test only; a real bench never runs with a guard switched off.");
  process.exit(2);
}
if (Number(process.versions.node.split(".")[0]) < 18) {
  console.error(`REFUSED: the bench needs Node 18 or newer; this is ${process.versions.node}.`);
  process.exit(2);
}
if (!fs.existsSync(PROJECT) || !fs.statSync(PROJECT).isDirectory()) {
  console.error(`REFUSED: the project folder ${PROJECT} does not exist.`);
  process.exit(2);
}
// port 0 (the system picks a free one) only for a bench the self-test started, so its runs side by side never share a port
if (!(SELF_TEST_CHILD && FIRST_PORT === 0) && (!Number.isInteger(FIRST_PORT) || FIRST_PORT < 1024 || FIRST_PORT > 65535)) {
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
  let newestCommit = null;
  for (const raw of text.split(/\r?\n/)) {
    if (!raw.trim()) continue;
    let o;
    try { o = JSON.parse(raw); } catch { unparsed++; continue; }
    const name = o && (o.name ?? o.gate ?? o.id);
    if (name == null) { unparsed++; continue; }
    runs++;
    const result = String(o.result ?? o.status ?? o.outcome ?? "").toUpperCase();
    const seconds = Number(o.seconds ?? o.secs ?? o.duration);
    if (o.commit) newestCommit = String(o.commit);
    last.set(String(name), {
      name: String(name), result: result || null, seconds: Number.isFinite(seconds) ? seconds : null,
      at: when(o.time ?? o.at ?? o.ts ?? o.when ?? o.date), commit: o.commit ? String(o.commit) : null,
    });
  }
  const gates = [...last.values()].map((g) => ({
    ...g,
    atHead: head && g.commit ? head.startsWith(g.commit) || g.commit.startsWith(head) : null,
    notRunAtNewest: BREAK === "pill-missing-as-pass" ? false : notRunAt(g.commit, newestCommit),
  }));
  // the header pill's count: a check passes only by a PASS at the ledger's newest commit; one with no line there is "not run"
  const current = gates.filter((g) => !g.notRunAtNewest);
  const pill = {
    total: gates.length, newestCommit,
    passed: current.filter((g) => markOf(g.result) === "pass").length,
    failing: current.filter((g) => markOf(g.result) === "fail").length,
    notRun: gates.length - current.length,
  };
  return { ledger: LEDGER, gates, runs, unparsed, newestCommit, pill };
}

// The checks history: every check's results in ledger order (oldest first, the newest HISTORY_RUNS kept), each a PASS, FAIL or
// REFUSED mark -- REFUSED is its own mark, never a pass and never a fail -- and whether the check has a line at the ledger's newest
// commit. A check with none there is "not run at the newest commit", never shown as passing. The bench does not recompute a gate's
// fingerprint (that needs the files each gate reads); the gates skill's --status stays the word on STALE.
const HISTORY_RUNS = 20;
// The ONE definition of "not run at the newest commit", for the header pill (readChecks) and the history room (readHistory) alike:
// the ledger has a newest commit, and this check's last line names another one, or none.
function notRunAt(lastCommit, newestCommit) {
  return Boolean(newestCommit && lastCommit !== newestCommit);
}
function markOf(result) {
  const r = String(result || "").toUpperCase();
  if (/^(PASS|PASSED|OK|GREEN|SUCCESS)$/.test(r)) return "pass";
  if (/^(FAIL|FAILED|RED|ERROR)$/.test(r)) return "fail";
  if (/^REFUSED$/.test(r)) return BREAK === "refused-as-fail" ? "fail" : BREAK === "refused-as-pass" ? "pass" : "refused";
  return "other";
}
function readHistory() {
  let text;
  try { text = fs.readFileSync(path.resolve(PROJECT, LEDGER), "utf8"); } catch {
    return { absent: `No checks ledger in this project yet (${LEDGER}). The gates skill builds one.`, ledger: LEDGER };
  }
  const by = new Map();
  let unparsed = 0;
  let lines = 0;
  let newestCommit = null;
  for (const raw of text.split(/\r?\n/)) {
    if (!raw.trim()) continue;
    let o;
    try { o = JSON.parse(raw); } catch { unparsed++; continue; }
    const name = o && (o.name ?? o.gate ?? o.id);
    if (name == null) { unparsed++; continue; }
    lines++;
    const seconds = Number(o.seconds ?? o.secs ?? o.duration);
    const commit = o.commit ? String(o.commit) : null;
    if (commit) newestCommit = commit;
    if (!by.has(String(name))) by.set(String(name), []);
    by.get(String(name)).push({ result: String(o.result ?? o.status ?? o.outcome ?? "").toUpperCase() || null,
      mark: markOf(o.result ?? o.status ?? o.outcome), seconds: Number.isFinite(seconds) ? seconds : null,
      at: when(o.time ?? o.at ?? o.ts ?? o.when ?? o.date), commit });
  }
  const checks = [...by.entries()].map(([name, all]) => {
    const marks = all.slice(-HISTORY_RUNS);
    const times = all.map((m) => m.seconds).filter((s) => s != null);
    const last = all[all.length - 1];
    return {
      name, marks, runs: all.length, newest: last,
      slowest: times.length ? Math.max(...times) : null,
      notRunAtNewest: BREAK === "missing-as-pass" ? false : notRunAt(last.commit, newestCommit),
    };
  });
  return { ledger: LEDGER, checks, lines, unparsed, newestCommit, kept: HISTORY_RUNS };
}

function readNotes() {
  const files = READ_PATH.map((name) => {
    const d = readDoc(name);
    return { name, bytes: d ? d.bytes : null };
  });
  return { files, total: files.reduce((s, f) => s + (f.bytes || 0), 0), warn: 300 * KB, budget: 400 * KB, ceiling: 500 * KB };
}

// Every message in INBOX.md, oldest first, each with its id, time, status, body and line.
function inboxMessages() {
  const doc = readDoc(INBOX);
  if (!doc) return [];
  const lines = doc.text.split("\n");
  const msgs = [];
  let cur = null;
  for (let i = 0; i < lines.length; i++) {
    const m = ENTRY.exec(lines[i]);
    if (m) { cur = { id: m[1], at: m[2].trim(), status: m[3].trim(), body: [], line: i + 1 }; msgs.push(cur); continue; }
    if (/^#{1,2}\s/.test(lines[i])) { cur = null; continue; }
    if (cur) cur.body.push(lines[i].replace(/^\\#/, "#"));
  }
  return msgs.map((m) => ({ ...m, body: m.body.join("\n").trim() }));
}

function readInbox() {
  const msgs = inboxMessages();
  return {
    messages: msgs.slice(-8).reverse(),
    total: msgs.length,
    waiting: msgs.filter((m) => /^waiting/i.test(m.status)).length,
  };
}

// ---------------------------------------------------------------- questions: decisions only the developer can make
// QUESTIONS.md holds one "## Q-nnn · title" section per question, with "What it is:", "The question:" and "Options:" followed by a
// numbered list, exactly one option marked "(recommended)". A question may also list "Pictures:" ("- file.png -- caption" lines),
// kept in .bench/pictures/Q-nnn/; a question with pictures and no options is answered picture by picture. The bench never edits
// QUESTIONS.md. A question is answered when INBOX.md holds a message starting "Answer to Q-nnn:" (or, for a pictures-only question,
// "Pictures for Q-nnn:") -- the click's own message, or one written by hand; the newest answer wins.
const QUESTIONS = "QUESTIONS.md";
const QUESTION_HEAD = /^##\s+(Q-\d+)\s*(?:·\s*(.*))?$/;
const ANSWER_LINE = /^(Answer|Pictures) (?:to|for) (Q-\d+):\s*(.*)$/m;
const PICTURES = path.join(".bench", "pictures");
const PICTURE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpe?g|webp)$/i;
const VERDICTS = { yes: "yes", no: "no", more: "say more" };
const clicked = new Map(); // answered-from-click break only: what this launch was clicked, instead of what INBOX.md holds

function questionFields(id, title, body, line) {
  const field = {};
  const options = [];
  const pictures = [];
  let cur = null;
  for (const raw of body) {
    const l = raw.replace(/\*\*/g, "");
    const label = /^(What it is|The question|Options|Pictures)\s*:\s*(.*)$/i.exec(l.trim());
    const opt = /^\s*(\d+)[.)]\s+(.*)$/.exec(l);
    const pic = /^\s*[-*]\s+(\S+)(?:\s+--\s+(.*))?$/.exec(l);
    if (label) { cur = label[1].toLowerCase(); field[cur] = label[2].trim(); continue; }
    if (cur === "options" && opt) { options.push({ n: Number(opt[1]), text: opt[2].trim() }); continue; }
    if (cur === "pictures" && pic) { pictures.push({ file: pic[1], caption: (pic[2] || "").trim() }); continue; }
    if (!l.trim()) { if (cur !== "options" && cur !== "pictures") cur = null; continue; }
    if (cur && cur !== "options" && cur !== "pictures") field[cur] = `${field[cur]} ${l.trim()}`.trim();
  }
  for (const o of options) {
    o.recommended = /\(recommended\)/i.test(o.text);
    o.text = o.text.replace(/\s*\(recommended\)\s*/i, " ").replace(/\s+/g, " ").trim();
  }
  for (const p of pictures) {
    if (!PICTURE_NAME.test(p.file)) { p.problem = "not a picture name (a .png, .jpg or .webp file in this question's folder)"; continue; }
    p.missing = BREAK === "missing-as-blank" ? false : !fs.existsSync(path.join(PROJECT, PICTURES, id, p.file));
    p.url = `/pictures/${id}/${encodeURIComponent(p.file)}`;
  }
  const q = { id, title: title || "", what: field["what it is"] || "", question: field["the question"] || "", options, pictures, line };
  const recs = options.filter((o) => o.recommended).length;
  const picturesOnly = pictures.length > 0 && options.length === 0;
  if (!q.question) q.refused = `${id} (line ${line}) has no "The question:" line.`;
  else if (picturesOnly) q.picturesOnly = true;
  else if (options.length < 2) q.refused = `${id} (line ${line}) lists ${options.length} option${options.length === 1 ? "" : "s"}; a choice needs at least two, numbered under "Options:".`;
  else if (recs !== 1 && BREAK !== "two-recommended-shown") q.refused = `${id} (line ${line}) marks ${recs} options "(recommended)"; exactly one must be.`;
  return q;
}

function readQuestions() {
  const doc = readDoc(QUESTIONS);
  if (!doc) return { absent: "QUESTIONS.md is not in this project yet. The agent writes a question there when a decision is the developer's (templates/QUESTIONS.md)." };
  const lines = doc.text.split("\n");
  const found = [];
  let cur = null;
  for (let i = 0; i < lines.length; i++) {
    const h = QUESTION_HEAD.exec(lines[i].trim());
    if (h) { cur = { id: h[1], title: (h[2] || "").trim(), body: [], line: i + 1 }; found.push(cur); continue; }
    if (/^#{1,2}\s/.test(lines[i])) { cur = null; continue; }
    if (cur) cur.body.push(lines[i]);
  }
  const answers = new Map();
  if (BREAK === "answered-from-click") for (const [id, a] of clicked) answers.set(id, a);
  else {
    for (const m of inboxMessages()) {
      const a = ANSWER_LINE.exec(m.body);
      if (!a) continue;
      const verdicts = a[1] === "Pictures" ? [...m.body.matchAll(/^- (\S+): (.*)$/gm)].map((v) => ({ file: v[1], verdict: v[2].trim() })) : null;
      answers.set(`${a[1]}:${a[2]}`, { choice: a[3].trim(), verdicts, message: m.id, at: m.at, status: m.status });
    }
  }
  // a question titled "Example: ..." is the template's illustration, hidden like the tables' "Example:" rows, and counted
  const real = found.filter((q) => !/^example:/i.test(q.title));
  const questions = real.map((q) => {
    const f = questionFields(q.id, q.title, q.body, q.line);
    // a pictures-only question is answered by its pictures' message; any other by its "Answer to" line
    return { ...f, answer: answers.get(`${f.picturesOnly ? "Pictures" : "Answer"}:${q.id}`) || null,
      pictureVerdicts: (answers.get(`Pictures:${q.id}`) || {}).verdicts || null };
  });
  return {
    questions,
    examplesHidden: found.length - real.length,
    waiting: questions.filter((q) => !q.refused && !q.answer).length,
    answered: questions.filter((q) => !q.refused && q.answer).length,
    refused: questions.filter((q) => q.refused).length,
  };
}

// One click: the question must be in QUESTIONS.md and not refused, the option one it lists (or "ask"). Returns the message's text,
// or { refused } in words.
function answerText(body) {
  const qs = readQuestions();
  if (qs.absent) return { refused: qs.absent };
  const q = qs.questions.find((x) => x.id === body.question);
  if (!q) return { refused: `There is no question ${String(body.question).slice(0, 20)} in QUESTIONS.md.` };
  if (q.refused) return { refused: `${q.id} cannot be answered until it is fixed: ${q.refused}` };
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 2000) : "";
  let choice;
  if (body.option === "ask") choice = "ask me first -- talk it through with me before deciding";
  else {
    const o = q.options.find((x) => x.n === Number(body.option));
    if (!o && BREAK !== "answer-any-option") return { refused: `${q.id} has no option ${String(body.option).slice(0, 10)}.` };
    choice = o ? `${o.n}. ${o.text}${o.recommended ? " (the recommended one)" : ""}` : `${body.option}.`;
  }
  return { id: q.id, choice, text: `Answer to ${q.id}: ${choice}` + (note ? `\n\nNote: ${note}` : "") };
}

// One Send from the pictures tray: every picture the question lists gets its line -- yes, no, say more, or "no verdict" -- in one
// message, so a picture left unmarked is said, never silently dropped.
function picturesText(body) {
  const qs = readQuestions();
  if (qs.absent) return { refused: qs.absent };
  const q = qs.questions.find((x) => x.id === body.question);
  if (!q) return { refused: `There is no question ${String(body.question).slice(0, 20)} in QUESTIONS.md.` };
  if (q.refused) return { refused: `${q.id} cannot be answered until it is fixed: ${q.refused}` };
  if (!q.pictures.length) return { refused: `${q.id} lists no pictures.` };
  const given = body.verdicts && typeof body.verdicts === "object" ? body.verdicts : {};
  const listed = new Set(q.pictures.map((p) => p.file));
  for (const [file, v] of Object.entries(given)) {
    if (!listed.has(file)) return { refused: `${q.id} lists no picture named ${String(file).slice(0, 60)}.` };
    if (!VERDICTS[v]) return { refused: `A picture's verdict is yes, no or more, not ${String(v).slice(0, 20)}.` };
    if (q.pictures.find((p) => p.file === file).missing) return { refused: `${file} is missing, so it cannot be judged.` };
  }
  if (!Object.keys(given).length) return { refused: "No picture was marked; nothing is sent." };
  const lines = q.pictures
    .filter((p) => BREAK !== "verdict-dropped" || given[p.file])
    .map((p) => `- ${p.file}: ${given[p.file] ? VERDICTS[given[p.file]] : "no verdict"}${p.missing ? " (the picture is missing)" : ""}`);
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 2000) : "";
  const marked = Object.keys(given).length;
  const choice = `${marked} of ${q.pictures.length} picture${q.pictures.length === 1 ? "" : "s"} marked`;
  return { id: q.id, choice, text: `Pictures for ${q.id}: ${choice}\n\n${lines.join("\n")}` + (note ? `\n\nNote: ${note}` : "") };
}

// A question's picture, by its question and its name only, from .bench/pictures/<Q-id>/; anything else is "no such picture".
function pictureFile(qid, name) {
  if (BREAK === "picture-path-escape") return path.join(PROJECT, PICTURES, qid, name);
  if (!/^Q-\d+$/.test(qid) || !PICTURE_NAME.test(name) || name !== path.basename(name)) return null;
  return path.join(PROJECT, PICTURES, qid, name);
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
  if (BREAK === "second-write") fs.writeFileSync(path.join(PROJECT, ".bench-last.json"), JSON.stringify({ id, at }));
  return { id, at };
}

let gitSlow = false; // the last git call was stopped by its timeout: slow is not the same as absent
function git(args) {
  return new Promise((resolve) => {
    execFile("git", ["-C", PROJECT, ...args], { windowsHide: true, timeout: 4000 }, (err, out) => {
      gitSlow = Boolean(err && err.killed);
      resolve(err ? null : out.trim());
    });
  });
}

async function readGit() {
  if ((await git(["rev-parse", "--is-inside-work-tree"])) !== "true") {
    if (gitSlow) return { absent: "git did not answer within 4 seconds (the machine may be busy); this panel fills on the next read." };
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
const TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
  ".webp": "image/webp", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };
// The rooms: the .js and .css files in ROOMS when the bench starts, by name only. A room is one .js file whose tab the page adds.
const ROOM_NAME = /^[a-z0-9][a-z0-9-]*\.(js|css)$/;
const ROOM_FILES = new Set(fs.existsSync(ROOMS) ? fs.readdirSync(ROOMS).filter((n) => ROOM_NAME.test(n)) : []);
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

const hostOk = (req) => BREAK === "no-host-check" ||
  [`127.0.0.1:${PORT}`, `localhost:${PORT}`].includes(String(req.headers.host || "").toLowerCase());
const originOk = (req) => BREAK === "no-origin-check" ||
  !req.headers.origin || [`http://127.0.0.1:${PORT}`, `http://localhost:${PORT}`].includes(req.headers.origin);
const keyOk = (req) => BREAK === "no-key-check" || req.headers["x-bench-key"] === KEY;

function page(res) {
  let html;
  try { html = fs.readFileSync(path.join(HERE, "bench.html"), "utf8"); } catch {
    return send(res, 500, "text/plain; charset=utf-8", `REFUSED: bench.html is missing beside ${path.join(HERE, "serve.mjs")}.`);
  }
  const nonce = crypto.randomBytes(16).toString("base64");
  html = html.replaceAll("__NONCE__", nonce).replace("__KEY__", KEY);
  send(res, 200, "text/html; charset=utf-8", html, {
    // 'self' lets the page load its rooms from /rooms/, which serves only the allow-listed files; nothing from elsewhere
    "Content-Security-Policy": `default-src 'none'; script-src 'self' 'nonce-${nonce}'; style-src 'self' 'nonce-${nonce}'; img-src 'self'; ` +
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
    if (req.method === "GET" && url.pathname === "/api/rooms") {
      return json(res, 200, { rooms: [...ROOM_FILES].filter((n) => n.endsWith(".js")).map((n) => n.slice(0, -3)).sort() });
    }
    if (req.method === "GET" && url.pathname.startsWith("/rooms/")) {
      const name = decodeURIComponent(url.pathname.slice("/rooms/".length));
      const p = path.join(ROOMS, name);
      if (BREAK === "room-path-escape" ? !fs.existsSync(p) : !ROOM_FILES.has(name) || name !== path.basename(name)) {
        return refuse(res, 404, "No such room.");
      }
      return send(res, 200, TYPES[path.extname(name).toLowerCase()] || "application/octet-stream", fs.readFileSync(p));
    }
    if (req.method === "POST" && url.pathname === "/api/alive") {
      if (!keyOk(req)) return refuse(res, 403, "This launch's key is missing; reload the page.");
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
      if (!keyOk(req)) return refuse(res, 403, "This launch's key is missing; reload the page.");
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
      if (!keyOk(req)) return refuse(res, 403, "This launch's key is missing; reload the page.");
      let text;
      try { text = JSON.parse(await readBody(req, 32 * KB)).text; } catch { return refuse(res, 400, "The message could not be read."); }
      if (typeof text !== "string" || !text.trim()) return refuse(res, 400, "An empty message is not sent.");
      if (text.length > 4000) return refuse(res, 400, "A message is at most 4,000 characters.");
      touch();
      return json(res, 200, appendInbox(text));
    }
    if (req.method === "GET" && url.pathname === "/api/questions") { touch(); return json(res, 200, readQuestions()); }
    if (req.method === "GET" && url.pathname === "/api/history") { touch(); return json(res, 200, readHistory()); }
    if (req.method === "GET" && url.pathname.startsWith("/pictures/")) {
      const [qid, ...rest] = url.pathname.slice("/pictures/".length).split("/");
      const p = pictureFile(decodeURIComponent(qid), decodeURIComponent(rest.join("/")));
      if (!p || !fs.existsSync(p) || !fs.statSync(p).isFile()) return refuse(res, 404, "No such picture.");
      return send(res, 200, TYPES[path.extname(p).toLowerCase()] || "application/octet-stream", fs.readFileSync(p));
    }
    if (req.method === "POST" && url.pathname === "/api/pictures") {
      if (!keyOk(req)) return refuse(res, 403, "This launch's key is missing; reload the page.");
      let body;
      try { body = JSON.parse(await readBody(req, 16 * KB)); } catch { return refuse(res, 400, "The verdicts could not be read."); }
      const a = picturesText(body || {});
      if (a.refused) return refuse(res, 400, a.refused);
      touch();
      const sent = appendInbox(a.text);
      if (BREAK === "answered-from-click") clicked.set(`Pictures:${a.id}`, { choice: a.choice, message: sent.id, at: sent.at, status: "waiting" });
      return json(res, 200, { ...sent, question: a.id, choice: a.choice });
    }
    if (req.method === "POST" && url.pathname === "/api/answer") {
      if (!keyOk(req)) return refuse(res, 403, "This launch's key is missing; reload the page.");
      let body;
      try { body = JSON.parse(await readBody(req, 8 * KB)); } catch { return refuse(res, 400, "The answer could not be read."); }
      const a = answerText(body || {});
      if (a.refused) return refuse(res, 400, a.refused);
      touch();
      const sent = appendInbox(a.text);
      if (BREAK === "answered-from-click") clicked.set(`Answer:${a.id}`, { choice: a.choice, message: sent.id, at: sent.at, status: "waiting" });
      return json(res, 200, { ...sent, question: a.id, choice: a.choice });
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
    PORT = server.address().port;
    const url = `http://${HOST}:${PORT}/`;
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

// ---------------------------------------------------------------- the self-test: the real bench, on scratch projects

const SCRATCH_FILES = {
  "STATE.md": ["# State", "", "## The project in one sentence", "", "A small tool that counts the words in a file.", "",
    "## Done looks like", "", "It prints the word count of any text file.", "",
    "Last checked at commit `abc1234` on branch `main` (2026-01-01)", "", "## What works now", "",
    "| Area | Status | How we know |", "|---|---|---|", "| Counting | works | the unit tests |", ""],
  "HANDOFF.md": ["# Handoff", "", "## Next", "", "| Id | Task | Done when | Cancel if | Size | Status |", "|---|---|---|---|---|---|",
    "| T-2 | Count lines too | its test passes | nobody needs it | 1 sitting | ready |", ""],
  "PLAN.md": ["# Plan", "", "| Id | Milestone | Task | Done when | Cancel if | Size | Status |", "|---|---|---|---|---|---|---|",
    "| T-1 | M-1 | Count words | it prints the total | never | 1 sitting | done |", ""],
  "DECISIONS.md": ["# Decisions", "", "| Id | Date | Decision | Why | What was rejected | Reversal cost |", "|---|---|---|---|---|---|",
    "| D-001 | 2026-01-01 | Plain Node, no packages | nothing to install | a framework | low |", ""],
  ".gates.jsonl": ['{"name":"unit tests","result":"PASS","seconds":1.2,"time":"2026-01-01T00:00:00Z","commit":"abc1234"}', ""],
  "QUESTIONS.md": ["# Questions", "",
    "## Q-001 · Where the counts are kept", "", "What it is: the counter can keep its totals in memory or in a file.",
    "The question: Should the totals survive a restart?", "Options:", "1. Keep them in a file (recommended) -- a few lines of code",
    "2. Keep them in memory -- lost on every restart", "",
    "## Q-002 · Two picks", "", "The question: Which output format?", "Options:", "1. Plain text (recommended)", "2. JSON (recommended)", "",
    "## Q-003 · One option", "", "The question: Ship it?", "Options:", "1. Yes (recommended)", "",
    "## Q-004 · Already answered", "", "The question: Count hyphenated words as one?", "Options:", "1. As one (recommended)",
    "2. As two", "",
    "## Q-005 · Example: the template's illustration", "", "The question: Shown?", "Options:", "1. No (recommended)", "2. Yes", "",
    "## Q-006 · The new screens", "", "The question: Do these screens look right?", "Pictures:", "- home.png -- the home screen",
    "- menu.png -- the menu, open", "- gone.png -- a picture nobody saved", ""],
  "INBOX.md": ["# INBOX", "", "## M-001 · 2026-01-01 09:00 · read 09:05", "", "Answer to Q-004: 1. As one (the recommended one)", ""],
};

// The self-test's waits are generous, because a busy machine is slow, not wrong; anything that still fails to answer is a
// refusal (exit 78, "could not look"), never a red row: a check that did not happen must never read as a result.
const SELF_TEST_WAIT_MS = 60 * 1000;

// Another run of this script (--check); it rejects when that run did not finish cleanly.
function runNode(args) {
  return new Promise((resolve, reject) => {
    execFile(process.execPath, [fileURLToPath(import.meta.url), ...args], { windowsHide: true, timeout: SELF_TEST_WAIT_MS },
      (err, out, errOut) => (err ? reject(new Error(`serve.mjs ${args.join(" ")} did not finish` +
        `${err.killed ? ` within ${SELF_TEST_WAIT_MS / 1000} s` : ` (exit ${err.code})`}: ${String(errOut).trim().slice(-200)}`))
        : resolve(String(out))));
  });
}

// null when git did it; otherwise what git said (its last lines, past any warnings), how long it took, and whether the wait ended it
function gitIn(dir, args) {
  const t0 = Date.now();
  return new Promise((resolve) => {
    execFile("git", ["-C", dir, "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
      "-c", "core.autocrlf=false", ...args], { windowsHide: true, timeout: SELF_TEST_WAIT_MS }, (err, out, errOut) => {
      if (!err) return resolve(null);
      const said = String(errOut || err.message).split(/\r?\n/).filter((l) => l.trim() && !/^warning:/.test(l)).join(" / ");
      resolve(`git ${args[0]} failed after ${Date.now() - t0} ms${err.killed ? ` (stopped after ${SELF_TEST_WAIT_MS / 1000} s)` : ""}, ` +
        `exit ${err.code}: ${said.slice(-300) || "it printed nothing"}`);
    });
  });
}

// Every file in a folder (not .git) and a hash of its bytes, to see exactly which files a request changed.
function snapshot(dir) {
  const out = new Map();
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === ".git") continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else out.set(path.relative(dir, p), crypto.createHash("sha1").update(fs.readFileSync(p)).digest("hex"));
    }
  };
  walk(dir);
  return out;
}
const changed = (a, b) => [...new Set([...a.keys(), ...b.keys()])].filter((k) => a.get(k) !== b.get(k)).sort();

// One request to the scratch bench; it rejects (could not look) when the bench does not answer at all.
function request(port, method, where, { host, origin, key, body } = {}) {
  return new Promise((resolve, reject) => {
    const headers = { host: host || `127.0.0.1:${port}` };
    if (origin) headers.origin = origin;
    if (key) headers["x-bench-key"] = key;
    if (body != null) headers["content-type"] = "application/json";
    const req = http.request({ host: HOST, port, method, path: where, headers }, (res) => {
      const parts = [];
      res.on("data", (c) => parts.push(c));
      res.on("end", () => resolve({ code: res.statusCode, headers: res.headers, text: Buffer.concat(parts).toString("utf8") }));
    });
    req.setTimeout(SELF_TEST_WAIT_MS, () => req.destroy(new Error(`no answer within ${SELF_TEST_WAIT_MS / 1000} s`)));
    req.on("error", (e) => reject(new Error(`${method} ${where} got no answer from the scratch bench: ${e.code || ""} ${e.message}`)));
    if (body != null) req.write(body);
    req.end();
  });
}

// A bench of its own, as a child process on a free port, with the break (if any) switched on in it alone.
function startBench(project, rooms) {
  return new Promise((resolve, reject) => {
    const args = [fileURLToPath(import.meta.url), "--project", project, "--rooms", rooms, "--port", "0", "--keep-running",
      "--self-test-child", ...(BREAK ? ["--break", BREAK] : [])];
    const child = spawn(process.execPath, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`no bench listening after ${SELF_TEST_WAIT_MS / 1000} s: ${out.slice(-200)}`));
    }, SELF_TEST_WAIT_MS);
    const hear = (c) => {
      out += c;
      const m = /open http:\/\/127\.0\.0\.1:(\d+)\//.exec(out);
      if (m) { clearTimeout(timer); resolve({ child, port: Number(m[1]) }); }
    };
    child.stdout.on("data", hear);
    child.stderr.on("data", hear);
    child.on("exit", (code) => { clearTimeout(timer); reject(new Error(`the bench exited (${code}) before listening: ${out.slice(-200)}`)); });
  });
}

async function selfTest() {
  if (!(await new Promise((r) => execFile("git", ["--version"], { windowsHide: true }, (e) => r(!e))))) {
    console.log("bench self-test REFUSED -- git is not installed, so the Git panel and the scratch project cannot be checked");
    return 78;
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "corvuswing_bench_"));
  const full = path.join(tmp, "full");
  const empty = path.join(tmp, "empty");
  const rooms = path.join(tmp, "rooms");
  const history = path.join(tmp, "history");
  for (const d of [full, empty, rooms, history]) fs.mkdirSync(d);
  for (const [name, lines] of Object.entries(SCRATCH_FILES)) fs.writeFileSync(path.join(full, name), lines.join("\n"));
  // a ledger of three checks over five commits: unit tests fails once, lint is REFUSED once, docs has no line at the newest
  // commit, and one line is not JSON at all
  const run = (commit, name, result, seconds) => JSON.stringify({ name, result, seconds, commit, time: `2026-01-0${commit.slice(1)}T10:00:00Z` });
  fs.writeFileSync(path.join(history, ".gates.jsonl"), [
    run("c1", "unit tests", "PASS", 1.1), run("c1", "lint", "PASS", 0.5), run("c1", "docs", "PASS", 0.2),
    run("c2", "unit tests", "FAIL", 1.3), run("c2", "lint", "PASS", 0.5), run("c2", "docs", "PASS", 0.2),
    run("c3", "unit tests", "PASS", 1.2), run("c3", "lint", "PASS", 0.6), run("c3", "docs", "FAIL", 0.3),
    run("c4", "unit tests", "PASS", 1.0), run("c4", "lint", "REFUSED", 0.1), run("c4", "docs", "PASS", 0.2),
    "this line is not a ledger entry",
    run("c5", "unit tests", "PASS", 1.4), run("c5", "lint", "PASS", 0.5), ""].join("\n"));
  // two real one-pixel pictures for Q-006; its third, gone.png, is left missing on purpose
  const pixel = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");
  fs.mkdirSync(path.join(full, PICTURES, "Q-006"), { recursive: true });
  for (const name of ["home.png", "menu.png"]) fs.writeFileSync(path.join(full, PICTURES, "Q-006", name), pixel);
  fs.writeFileSync(path.join(rooms, "hello.js"), 'export const title = "Hello";\n');
  fs.writeFileSync(path.join(rooms, "notes.txt"), "not a room\n");
  fs.writeFileSync(path.join(tmp, "secret.txt"), "outside the rooms folder\n");
  const rows = [];
  const row = (name, ok, detail) => rows.push({ name, ok: Boolean(ok), detail });
  let bench = null;
  let bench2 = null; // the checks history's own scratch project
  try {
    for (const args of [["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "start"]]) {
      // On Windows a file git has just written can be held for a moment by another program (a virus scanner, the search
      // indexer), and git stops with "Permission denied", or, when the held file is its index, "unable to write new index
      // file". The scratch project is a setup, not what is checked: those two errors, by name, are tried again, at most three times in all (waits of 0.5 s and 1 s between them), and a failure that outlasts the
      // three is refused in words, with the count. The git-denied break plants that lasting failure to prove it.
      const planted = {
        "git-denied": "error: unable to write file .git/objects/00/0: Permission denied",
        "git-index-held": "fatal: unable to write new index file",
      }[BREAK];
      const attempt = () => (planted && args[0] === "add"
        ? Promise.resolve(`git add failed, exit 128: ${planted} (planted by --break ${BREAK})`)
        : gitIn(full, args));
      let failed = await attempt();
      let tries = 1;
      for (; failed && /Permission denied|unable to write new index file/.test(failed) && tries < 3; tries++) {
        await new Promise((r) => setTimeout(r, 500 * tries));
        failed = await attempt();
      }
      if (failed) {
        console.log(`bench self-test REFUSED -- it could not look: git could not make the scratch project's first commit ` +
          `after ${tries} ${tries === 1 ? "try" : "tries"}: ${failed}`);
        return 78;
      }
    }
    const filled = await runNode(["--project", full, "--check"]);
    if (/git did not answer within/.test(filled)) throw new Error("git was too slow for the Git panel's read (the machine is busy)");
    const notFilled = filled.split("\n").filter((l) => /^\s+(EMPTY|PARTLY)\s/.test(l) && !/\sQuestions\s/.test(l))
      .map((l) => l.trim().slice(0, 60));
    row("a full project reads 6 of 6 panels filled", /6 of 6 panels filled/.test(filled),
      [(/(\d) of 6 panels filled/.exec(filled) || ["no count"])[0], ...notFilled].join("; "));
    const bare = await runNode(["--project", empty, "--check"]);
    const want = { "What's true now": "STATE.md", Next: "HANDOFF.md", Tasks: "PLAN.md", Decisions: "DECISIONS.md", Checks: ".gates.jsonl" };
    const missing = Object.entries(want).filter(([panel, file]) =>
      !bare.split("\n").some((l) => l.includes("EMPTY") && l.includes(panel) && l.includes(file))).map(([p]) => p);
    row("an empty project's panels read EMPTY, each naming its file", !missing.length && /0 of 6 panels filled/.test(bare),
      missing.length ? `not EMPTY with its file: ${missing.join(", ")}` : "five EMPTY, each with its file");

    bench = await startBench(full, rooms);
    const port = bench.port;
    const own = `http://127.0.0.1:${port}`;
    const home = await request(port, "GET", "/");
    const key = (/<meta name="bench-key" content="([0-9a-f]+)">/.exec(home.text) || [])[1];
    const csp = String(home.headers["content-security-policy"] || "");
    row("the page allows its own rooms' scripts and nothing from elsewhere",
      csp.includes("default-src 'none'") && /script-src 'self' 'nonce-/.test(csp) && !/https?:/.test(csp), csp.slice(0, 70));
    const host = await request(port, "GET", "/api/hello", { host: `evil.example:${port}` });
    row("a request naming another host is refused", host.code === 403, `HTTP ${host.code}`);
    const msg = JSON.stringify({ text: "from the self-test" });
    const away = await request(port, "POST", "/api/inbox", { origin: "http://evil.example", key, body: msg });
    row("a message from another site's page is refused", away.code === 403, `HTTP ${away.code}`);
    const nokey = await request(port, "POST", "/api/inbox", { origin: own, body: msg });
    row("a message without this launch's key is refused", nokey.code === 403, `HTTP ${nokey.code}`);
    const list = await request(port, "GET", "/api/rooms");
    row("the rooms list names each room and nothing else", list.text === '{"rooms":["hello"]}', list.text.slice(0, 60));
    const hello = await request(port, "GET", "/rooms/hello.js");
    row("a listed room file is served as a script", hello.code === 200 && /javascript/.test(hello.headers["content-type"] || ""),
      `HTTP ${hello.code} ${hello.headers["content-type"] || ""}`);
    const outside = [];
    for (const where of ["/rooms/..%2Fsecret.txt", "/rooms/notes.txt", "/rooms/missing.js", "/rooms/..%2F..%2Fsecret.txt"]) {
      const r = await request(port, "GET", where);
      if (r.code !== 404) outside.push(`${where} HTTP ${r.code}`);
    }
    row("a name outside the room list is refused", !outside.length, outside.length ? outside.join("; ") : "four names, each 404");

    const questions = async () => JSON.parse((await request(port, "GET", "/api/questions")).text).questions || [];
    const all = JSON.parse((await request(port, "GET", "/api/questions")).text);
    const qs = all.questions || [];
    const q = (id) => qs.find((x) => x.id === id) || {};
    const rec = (q("Q-001").options || []).filter((o) => o.recommended).map((o) => o.text);
    row("a waiting question is read with its one recommendation, and an Example: question is hidden",
      !q("Q-001").refused && !q("Q-001").answer && rec.length === 1 && rec[0].startsWith("Keep them in a file") &&
      !qs.some((x) => x.id === "Q-005") && all.examplesHidden === 1,
      `Q-001 ${q("Q-001").refused ? "refused" : q("Q-001").answer ? "answered" : "waiting"}, recommended: ${rec.join(" | ") || "none"}; ` +
      `${all.examplesHidden} example hidden`);
    row("a question with fewer than two options, or not exactly one recommended, is refused in words",
      /exactly one/.test(q("Q-002").refused || "") && /at least two/.test(q("Q-003").refused || ""),
      `Q-002: ${q("Q-002").refused || "not refused"} / Q-003: ${q("Q-003").refused || "not refused"}`.slice(0, 160));
    row("an answer already in INBOX.md reads as answered", q("Q-004").answer && q("Q-004").answer.message === "M-001",
      q("Q-004").answer ? `answered by ${q("Q-004").answer.message}` : "reads as waiting");
    const answer = (body) => request(port, "POST", "/api/answer", { origin: own, key, body: JSON.stringify(body) });
    const wrong = [];
    for (const [body, what] of [[{ question: "Q-999", option: 1 }, "an unknown question"], [{ question: "Q-003", option: 1 }, "a refused question"],
      [{ question: "Q-001", option: 9 }, "an option it does not list"]]) {
      const r = await answer(body);
      if (r.code !== 400) wrong.push(`${what}: HTTP ${r.code}`);
    }
    row("an answer to an unknown question, a refused one, or an option it does not list is refused", !wrong.length,
      wrong.length ? wrong.join("; ") : "three answers, each refused");
    const inboxBefore = fs.readFileSync(path.join(full, INBOX), "utf8");
    const click = await answer({ question: "Q-001", option: 1, note: "from the self-test" });
    const added = fs.readFileSync(path.join(full, INBOX), "utf8").slice(inboxBefore.length);
    const nowAnswered = (await questions()).find((x) => x.id === "Q-001");
    row("a click writes one message naming the question and its option, and the question reads answered",
      click.code === 200 && (added.match(/^## M-\d+ · /gm) || []).length === 1 &&
      added.includes("Answer to Q-001: 1. Keep them in a file") && nowAnswered && nowAnswered.answer,
      `HTTP ${click.code}; ${(added.match(/^## M-\d+ · /gm) || []).length} message(s) added; Q-001 ${nowAnswered && nowAnswered.answer ? "answered" : "not answered"}`);

    const pics = (q("Q-006").pictures || []);
    const shot = await request(port, "GET", "/pictures/Q-006/home.png");
    const gone = pics.find((p) => p.file === "gone.png") || {};
    const verdicts = (body) => request(port, "POST", "/api/pictures", { origin: own, key, body: JSON.stringify(body) });
    const judgeGone = await verdicts({ question: "Q-006", verdicts: { "gone.png": "yes" } });
    row("a question's pictures are served by name, and a missing one is shown as missing and cannot be judged",
      shot.code === 200 && shot.headers["content-type"] === "image/png" && pics.length === 3 && gone.missing === true &&
      pics.filter((p) => p.missing).length === 1 && judgeGone.code === 400,
      `home.png HTTP ${shot.code}; ${pics.length} listed, missing: ${pics.filter((p) => p.missing).map((p) => p.file).join(", ") || "none"}; ` +
      `a verdict on gone.png HTTP ${judgeGone.code}`);
    const escaped = [];
    for (const where of ["/pictures/Q-006/..%2F..%2F..%2FSTATE.md", "/pictures/Q-006/..%2F..%2F..%2FQUESTIONS.md",
      "/pictures/..%2F..%2F..%2FSTATE.md", "/pictures/Q-006/home.png%2F..%2F..%2F..%2F..%2FSTATE.md"]) {
      const r = await request(port, "GET", where);
      if (r.code !== 404) escaped.push(`${where} HTTP ${r.code}`);
    }
    row("a picture name that leaves its question's folder is refused", !escaped.length,
      escaped.length ? escaped.join("; ") : "four names, each 404");
    const badPick = await verdicts({ question: "Q-006", verdicts: { "other.png": "yes" } });
    const before3 = fs.readFileSync(path.join(full, INBOX), "utf8");
    const sentPics = await verdicts({ question: "Q-006", verdicts: { "home.png": "yes", "menu.png": "no" } });
    const msg3 = fs.readFileSync(path.join(full, INBOX), "utf8").slice(before3.length);
    const q6 = (await questions()).find((x) => x.id === "Q-006") || {};
    row("one Send names every picture, an unmarked one as 'no verdict', and a picture it does not list is refused",
      badPick.code === 400 && sentPics.code === 200 && (msg3.match(/^## M-\d+ · /gm) || []).length === 1 &&
      /- home\.png: yes/.test(msg3) && /- menu\.png: no/.test(msg3) && /- gone\.png: no verdict/.test(msg3) &&
      Boolean(q6.answer),
      `unlisted picture HTTP ${badPick.code}; send HTTP ${sentPics.code}; lines: ${(msg3.match(/^- .*$/gm) || []).join(" / ")}; ` +
      `Q-006 ${q6.answer ? "answered" : "not answered"}`);
    const before = snapshot(full);
    const sent = await request(port, "POST", "/api/inbox", { origin: own, key, body: msg });
    const diff = changed(before, snapshot(full));
    const inbox = (() => { try { return fs.readFileSync(path.join(full, INBOX), "utf8"); } catch { return ""; } })();
    row("a sent message lands in INBOX.md, the only file changed",
      sent.code === 200 && diff.length === 1 && diff[0] === INBOX && inbox.includes("from the self-test"),
      `HTTP ${sent.code}; changed: ${diff.join(", ") || "nothing"}`);

    bench2 = await startBench(history, rooms);
    const h = JSON.parse((await request(bench2.port, "GET", "/api/history")).text);
    const check = (name) => (h.checks || []).find((c) => c.name === name) || { marks: [] };
    const strip = (name) => check(name).marks.map((m) => m.mark).join(",");
    row("each check's results are drawn in ledger order, with an unreadable line counted",
      strip("unit tests") === "pass,fail,pass,pass,pass" && h.unparsed === 1 && check("unit tests").slowest === 1.4,
      `unit tests: ${strip("unit tests")}; unreadable: ${h.unparsed}; slowest ${check("unit tests").slowest} s`);
    row("a REFUSED run is its own mark, never a pass or a fail", strip("lint") === "pass,pass,pass,refused,pass",
      `lint: ${strip("lint")}`);
    row("a check with no line at the newest commit reads 'not run', never passing",
      check("docs").notRunAtNewest === true && check("unit tests").notRunAtNewest === false && h.newestCommit === "c5",
      `docs ${check("docs").notRunAtNewest ? "not run" : "shown as current"} at ${h.newestCommit}; ` +
      `unit tests ${check("unit tests").notRunAtNewest ? "not run" : "current"}`);
    const pill = (JSON.parse((await request(bench2.port, "GET", "/api/state")).text).checks || {}).pill || {};
    row("the header pill counts a check with no line at the newest commit as 'not run', never passed",
      pill.total === 3 && pill.passed === 2 && pill.notRun === 1 && pill.failing === 0 && pill.newestCommit === "c5",
      `${pill.passed} of ${pill.total} passed, ${pill.notRun} not run at ${pill.newestCommit}, ${pill.failing} failing`);
  } catch (e) {
    console.log(`bench self-test REFUSED -- it could not look: ${e.message}`);
    return 78;
  } finally {
    if (bench) bench.child.kill();
    if (bench2) bench2.child.kill();
    try { fs.rmSync(tmp, { recursive: true, force: true }); } catch { /* the temp folder is cleaned by the system */ }
  }
  for (const r of rows) console.log(`  ${r.ok ? "ok " : "RED"}  ${r.name} -- ${r.detail}`);
  const bad = rows.filter((r) => !r.ok).length;
  console.log(`bench self-test ${bad ? "RED" : "GREEN"} -- ${rows.length} case(s), ${bad} not as expected${BREAK ? ` (break ${BREAK})` : ""}`);
  return bad ? 1 : 0;
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

  // Questions are optional, like messages: a project with none is fine, and a refused question is named with its line.
  const q = readQuestions();
  if (q.absent) add("Questions", "READY", "no questions yet (QUESTIONS.md, in templates/QUESTIONS.md's shape, when a decision is the developer's)");
  else if (q.refused) {
    add("Questions", "PARTLY", `QUESTIONS.md, ${q.refused} refused: ` + q.questions.filter((x) => x.refused).map((x) => x.refused).join(" "));
  } else add("Questions", "READY", `QUESTIONS.md, ${q.waiting} waiting, ${q.answered} answered`);

  return [`CorvusWing bench check: ${PROJECT}`, ...rows, "",
    `${filled} of 6 panels filled. An EMPTY or PARTLY panel is read from the file, heading or table named beside it; SKILL.md's`,
    '"Fit the project to the bench" says how to bring a file into that shape without inventing anything.'].join("\n");
}

if (SELF_TEST) {
  process.exit(await selfTest());
} else if (CHECK) {
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
