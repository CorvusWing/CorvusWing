// The Questions room: each decision the agent left for the developer in QUESTIONS.md, as a card with the recommendation first and
// one button per option. A click sends one message to INBOX.md ("Answer to Q-nnn: ..."); the bench never edits QUESTIONS.md, and a
// question reads answered only once INBOX.md holds its answer. Text always goes in as text, never as markup.

// read when a message is sent, so the bench's self-test can import this file's key table and tab counts without a page
const benchKey = () => document.querySelector('meta[name="bench-key"]').content;

// For the bench's self-test only: it switches one rule below off to prove its row turns red. The page never sets it.
export const TEST = { break: "" };

// ---------------------------------------------------------------- keyboard keys: each calls its button's own handler
export const KEYS = [
  ["j", "next", "move to the next card"], ["k", "prev", "move to the previous card"],
  ["a", "approve", "approve: the recommended choice"], ["1-9", "pick", "pick that numbered option"],
  ["b", "batch", "turn Collect a batch on or off"], ["n", "note", "write a note on this card"],
  ["/", "search", "search the questions"], ["?", "help", "show or hide this list"],
];

// The action a key stands for, or null. Nothing happens while the developer is typing in a box, or with a modifier held.
export function keyAction(key, typing, modified = false) {
  if ((typing && TEST.break !== "keys-while-typing") || modified) return null;
  if (/^[1-9]$/.test(key)) return { act: "pick", n: Number(key) };
  const hit = KEYS.find(([k]) => k === key);
  return hit ? { act: hit[1] } : null;
}

// Runs a key: ctx.cards holds each card's own button handlers ({ approve, pick(n), note }), ctx.focus the focused card's place,
// and ctx.page the page's own (setFocus, batch, search, help). Returns what was called, or null when the key does nothing here:
// an Approve on a card with no recommendation, or a number no option carries, is never guessed.
export function dispatch(key, typing, ctx, modified = false) {
  const a = keyAction(key, typing, modified);
  if (!a) return null;
  const n = ctx.cards.length;
  const here = ctx.cards[ctx.focus];
  if (a.act === "next" || a.act === "prev") {
    if (!n) return null;
    const to = ctx.focus < 0 ? 0 : Math.min(n - 1, Math.max(0, ctx.focus + (a.act === "next" ? 1 : -1)));
    ctx.page.setFocus(to);
    return `focus ${to}`;
  }
  if (a.act === "batch" || a.act === "search" || a.act === "help") { ctx.page[a.act](); return a.act; }
  if (!here) return null;
  if (a.act === "pick") {
    const pick = here.picks && here.picks.get(TEST.break === "keys-off-by-one" ? a.n + 1 : a.n);
    if (!pick) return null;
    pick();
    return `pick ${a.n}`;
  }
  if (!here[a.act]) return null;
  here[a.act]();
  return a.act;
}

// ---------------------------------------------------------------- the tabs: every count from the list the cards come from
const isWaiting = (q) => !q.refused && !q.answer;
const TABS = [["waiting", "Waiting", isWaiting], ["answered", "Answered", (q) => Boolean(q.answer)], ["all", "All", () => true]];
let firstCounts = null; // kept only for the self-test's break, which counts from the first list ever read

// What a search matches: the id, the title and the text of the question, without regard to case.
function matches(q, query) {
  const want = query.trim().toLowerCase();
  if (!want) return true;
  const fields = TEST.break === "search-id-only" ? [q.id] : [q.id, q.title, q.what, q.question, ...(q.options || []).map((o) => o.text)];
  return fields
    .some((t) => typeof t === "string" && t.toLowerCase().includes(want));
}

// The cards one tab shows, and each tab's count: { shown, counts: { waiting: { n, of }, ... }, searching }. While a search is on,
// n is how many of the tab's M questions match it ("N of M"); with no search, n and of are the same.
export function tabView(questions, tab, query = "") {
  const counts = {};
  for (const [id, , keep] of TABS) {
    const inTab = questions.filter(keep);
    counts[id] = { n: inTab.filter((q) => matches(q, query)).length, of: inTab.length };
  }
  if (TEST.break === "counts-from-old-list") { firstCounts = firstCounts || counts; }
  const keep = (TABS.find(([id]) => id === tab) || TABS[2])[2];
  return { shown: questions.filter((q) => keep(q) && matches(q, query)), counts: firstCounts || counts, searching: Boolean(query.trim()) };
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
const absent = (text) => el("p", "absent", text);

function stylesheet() {
  if (document.getElementById("room-questions-css")) return;
  const link = el("link");
  link.id = "room-questions-css";
  link.rel = "stylesheet";
  link.href = "/rooms/questions.css";
  document.head.append(link);
}

async function send(q, option, note, status) {
  status.className = "qnote";
  status.textContent = "Sending...";
  try {
    const r = await fetch("/api/answer", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": benchKey() },
      body: JSON.stringify({ question: q.id, option, note: note.value }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.refused || `HTTP ${r.status}`);
    return true;
  } catch (e) {
    status.className = "qnote bad";
    status.textContent = `Not sent: ${e.message}`;
    return false;
  }
}

// The pictures tray: each picture with yes / no / say more; one Send writes every picture's line, an unmarked one as "no verdict".
// A picture the question names but the folder lacks is shown as missing, never as a blank tile.
function tray(q, redraw) {
  const box = el("div", "qtray");
  const given = {};
  const past = new Map((q.pictureVerdicts || []).map((v) => [v.file, v.verdict]));
  for (const p of q.pictures) {
    const tile = el("figure", "qpic");
    if (p.problem) tile.append(el("div", "qpic-missing", `${p.file}: ${p.problem}`));
    else if (p.missing) tile.append(el("div", "qpic-missing", `missing: ${p.file} is not in .bench/pictures/${q.id}/`));
    else {
      const img = el("img");
      img.src = p.url;
      img.alt = p.caption || p.file;
      img.loading = "lazy";
      const open = el("a");
      open.href = p.url;
      open.target = "_blank";
      open.rel = "noopener";
      open.append(img);
      tile.append(open);
    }
    tile.append(el("figcaption", null, p.caption ? `${p.file} · ${p.caption}` : p.file));
    if (past.has(p.file)) tile.append(el("p", "src", `sent: ${past.get(p.file)}`));
    if (!p.problem && !p.missing) {
      const row = el("div", "qverdicts");
      for (const [v, label] of [["yes", "Yes"], ["no", "No"], ["more", "Say more"]]) {
        const b = el("button", "qopt plain qv", label);
        b.addEventListener("click", () => {
          given[p.file] = given[p.file] === v ? undefined : v;
          if (!given[p.file]) delete given[p.file];
          for (const x of row.children) x.classList.toggle("on", x === b && given[p.file] === v);
        });
        row.append(b);
      }
      tile.append(row);
    }
    box.append(tile);
  }
  const note = el("textarea", "qnotebox");
  note.placeholder = "A note with your verdicts (optional)";
  note.maxLength = 2000;
  const status = el("p", "qnote");
  const go = el("button", "btn", "Send verdicts");
  go.addEventListener("click", async () => {
    status.className = "qnote";
    status.textContent = "Sending...";
    try {
      const r = await fetch("/api/pictures", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": benchKey() },
        body: JSON.stringify({ question: q.id, verdicts: given, note: note.value }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.refused || `HTTP ${r.status}`);
      redraw();
    } catch (e) {
      status.className = "qnote bad";
      status.textContent = `Not sent: ${e.message}`;
    }
  });
  const foot = el("div", "send");
  foot.append(go, el("small", null, "every picture gets a line; one you leave unmarked is sent as \"no verdict\""));
  const wrap = el("div");
  wrap.append(box, note, foot, status);
  return wrap;
}

function card(q, redraw) {
  const c = el("section", "card qcard");
  const top = el("div", "qtop");
  top.append(el("span", "eyebrow", q.id + (q.title ? " · " + q.title : "")));
  const state = q.refused ? ["cannot be answered yet", "chip bad"] : q.answer ? ["answered", "chip ok"] : ["waiting for you", "chip live"];
  top.append(el("span", state[1], state[0]));
  c.append(top);
  if (q.refused) {
    c.append(el("p", "qwhat", q.refused), el("p", "src", "The agent fixes this in QUESTIONS.md; the bench only reads it."));
    return c;
  }
  if (q.what) c.append(el("p", "qwhat", q.what));
  c.append(el("p", "qask", q.question));
  if (q.pictures.length) c.append(tray(q, redraw));
  if (q.answer) {
    c.append(el("p", "qdone", `Your answer: ${q.answer.choice}`));
    // the agent's reply is its own line in INBOX.md ("answered HH:MM: ..."); none is ever invented
    if (q.answer.reply) c.append(el("p", "qreply", `Reply, ${q.answer.repliedAt}: ${q.answer.reply}`));
    else if (q.answer.readAt) c.append(el("p", "src", `Read at ${q.answer.readAt}, no reply yet`));
    else c.append(el("p", "src", "Not read yet"));
    c.append(el("p", "src", `INBOX.md ${q.answer.message} · ${q.answer.at} · ${q.answer.status}`));
    return c;
  }
  if (q.picturesOnly) return c;
  const opts = [...q.options].sort((a, b) => Number(b.recommended) - Number(a.recommended));
  const note = el("textarea", "qnotebox");
  note.placeholder = "A note with your answer (optional)";
  note.maxLength = 2000;
  const status = el("p", "qnote");
  const buttons = el("div", "qopts");
  // a pick either goes now, or (with "Collect a batch" on) waits in the batch until "Send batch"
  const pick = async (option, label) => {
    if (BATCH.on) {
      BATCH.items.set(q.id, { question: q.id, option, note: note.value, label });
      status.className = "qnote";
      status.textContent = `In the batch: ${label}`;
      BATCH.changed();
      return;
    }
    if (await send(q, option, note, status)) redraw();
  };
  // each button's handler is also the one its key calls (KEYS above), so a key can never do something its button does not
  const keys = { picks: new Map(), note: () => note.focus() };
  const rec = q.options.find((o) => o.recommended);
  if (rec) {
    const approve = el("button", "btn qopt qapprove", "Approve");
    approve.title = `Takes the recommended choice: ${rec.n}. ${rec.text} (key: a)`;
    keys.approve = () => pick("recommended", `${rec.n}. ${rec.text} (recommended)`);
    approve.addEventListener("click", keys.approve);
    buttons.append(approve);
  }
  for (const o of opts) {
    const b = el("button", o.recommended ? "btn qopt" : "qopt plain", `${o.n}. ${o.text}`);
    if (o.recommended) b.append(el("span", "qrec", "recommended"));
    const choose = () => pick(o.n, `${o.n}. ${o.text}`);
    if (o.n >= 1 && o.n <= 9) keys.picks.set(o.n, choose);
    b.addEventListener("click", choose);
    buttons.append(b);
  }
  const ask = el("button", "qopt plain qask-first", "Ask me first");
  ask.addEventListener("click", () => pick("ask", "Ask me first"));
  buttons.append(ask);
  if (BATCH.items.has(q.id)) { status.textContent = `In the batch: ${BATCH.items.get(q.id).label}`; }
  c.append(buttons, note, status);
  HANDLERS.set(c, keys);
  return c;
}
const HANDLERS = new WeakMap(); // card element -> its buttons' handlers; only cards still waiting for an answer have them

// The batch lives in this page only (a reload empties it, and the bar says so); nothing is written until "Send batch", which sends
// ONE message holding every saved answer. The server checks each answer and refuses the whole batch if any one would be refused.
const BATCH = { on: false, items: new Map(), changed: () => {} };

function batchBar(redraw) {
  const bar = el("div", "qbatch");
  const toggle = el("button", "qopt plain", "");
  const go = el("button", "btn", "");
  const clear = el("button", "qopt plain", "Empty the batch");
  const say = el("p", "qnote");
  const paint = () => {
    toggle.textContent = BATCH.on ? "Collect a batch: on" : "Collect a batch: off";
    toggle.classList.toggle("on", BATCH.on);
    go.textContent = `Send batch (${BATCH.items.size})`;
    go.disabled = !BATCH.items.size;
    clear.disabled = !BATCH.items.size;
  };
  BATCH.changed = paint;
  BATCH.toggle = () => { BATCH.on = !BATCH.on; paint(); };
  toggle.title = "key: b";
  toggle.addEventListener("click", BATCH.toggle);
  clear.addEventListener("click", () => { BATCH.items.clear(); paint(); redraw(); });
  go.addEventListener("click", async () => {
    say.className = "qnote";
    say.textContent = "Sending...";
    try {
      const r = await fetch("/api/answer-batch", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": benchKey() },
        body: JSON.stringify({ answers: [...BATCH.items.values()].map(({ question, option, note }) => ({ question, option, note })) }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.refused || `HTTP ${r.status}`);
      BATCH.items.clear();
      paint();
      redraw();
    } catch (e) {
      say.className = "qnote bad";
      say.textContent = `Not sent: ${e.message}`;
    }
  });
  paint();
  bar.append(toggle, go, clear, el("small", null, "a batch is held by this page only; a reload empties it"), say);
  return bar;
}

// The room's own view state: which tab, what search, which card has the keyboard. Kept across redraws, lost on a reload.
const VIEW = { tab: "waiting", query: "", focus: -1, list: [] };
let keysBound = false;
let ROOM = null;

function tabBar(counts, searching, redraw) {
  const bar = el("div", "qtabs");
  for (const [id, label] of TABS) {
    const c = counts[id];
    const b = el("button", "qopt plain qtab" + (VIEW.tab === id ? " on" : ""), `${label} (${searching ? `${c.n} of ${c.of}` : c.of})`);
    b.addEventListener("click", () => { VIEW.tab = id; VIEW.focus = -1; redraw(); });
    bar.append(b);
  }
  const search = el("input", "qsearch");
  search.type = "search";
  search.placeholder = "Search id, title or text (key: /)";
  search.value = VIEW.query;
  search.addEventListener("input", () => { VIEW.query = search.value; VIEW.focus = -1; redraw(true); });
  bar.append(search);
  return { bar, search };
}

function keyHelp() {
  const box = el("div", "card qhelp");
  box.hidden = true;
  box.append(el("p", "eyebrow", "Keys (never while typing in a box)"));
  const list = el("dl");
  for (const [k, , what] of KEYS) list.append(el("dt", null, k), el("dd", null, what));
  box.append(list);
  return box;
}

export async function mount(view) {
  stylesheet();
  const help = keyHelp();
  let search = null;
  const setFocus = (i) => {
    VIEW.focus = i;
    VIEW.list.forEach((c, n) => c.classList.toggle("qfocus", n === i));
    if (VIEW.list[i]) VIEW.list[i].scrollIntoView({ block: "nearest" });
  };
  let data = null;
  const paint = () => {
    const order = (q) => (q.refused ? 1 : q.answer ? 2 : 0);
    const v = tabView([...data.questions].sort((a, b) => order(a) - order(b)), VIEW.tab, VIEW.query);
    const head = el("p", "src", `QUESTIONS.md · ${data.waiting} waiting, ${data.answered} answered` +
      (data.refused ? `, ${data.refused} that cannot be answered yet` : "") + " · a click writes one message to INBOX.md · ? for keys");
    const tabs = tabBar(v.counts, v.searching, (keepSearch) => { paint(); if (keepSearch) ROOM.page.search(); });
    search = tabs.search;
    const cards = v.shown.map((q) => card(q, draw));
    VIEW.list = cards.filter((c) => HANDLERS.has(c));
    const none = !data.questions.length ? "QUESTIONS.md holds no questions."
      : v.searching ? "No question in this tab matches the search." : "No question in this tab.";
    view.replaceChildren(head, bar, tabs.bar, help, ...(cards.length ? cards : [absent(none)]));
    if (VIEW.focus >= 0) setFocus(Math.min(VIEW.focus, VIEW.list.length - 1));
  };
  const draw = async () => {
    try {
      const r = await fetch("/api/questions", { cache: "no-store" });
      data = await r.json();
    } catch (e) {
      view.replaceChildren(absent(`The questions could not be read: ${e.message}`));
      return;
    }
    if (data.absent) { view.replaceChildren(absent(data.absent)); data = null; return; }
    paint();
  };
  const bar = batchBar(() => draw());
  // the latest mount is the one the keys reach; the listener is added once, however often the room is opened
  ROOM = {
    view, ready: () => Boolean(data),
    page: {
      setFocus, batch: () => BATCH.toggle(), help: () => { help.hidden = !help.hidden; },
      search: () => { if (search) { search.focus(); search.setSelectionRange(search.value.length, search.value.length); } },
    },
  };
  if (!keysBound) {
    keysBound = true;
    document.addEventListener("keydown", (e) => {
      const room = ROOM;
      if (!room || !room.view.isConnected || room.view.offsetParent === null || !room.ready()) return; // this room on screen only
      const t = e.target;
      const typing = Boolean(t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)));
      const did = dispatch(e.key, typing, { cards: VIEW.list.map((c) => HANDLERS.get(c)), focus: VIEW.focus, page: room.page },
        e.ctrlKey || e.metaKey || e.altKey);
      if (did) e.preventDefault(); // "/" and "n" would otherwise type their own letter into the box they just focused
    });
  }
  await draw();
}
