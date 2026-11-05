// The Questions room: each decision the agent left for the developer in QUESTIONS.md, as a card with the recommendation first and
// one button per option. A click sends one message to INBOX.md ("Answer to Q-nnn: ..."); the bench never edits QUESTIONS.md, and a
// question reads answered only once INBOX.md holds its answer. Text always goes in as text, never as markup.

const KEY = document.querySelector('meta[name="bench-key"]').content;

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
      method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": KEY },
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
        method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": KEY },
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
  const rec = q.options.find((o) => o.recommended);
  if (rec) {
    const approve = el("button", "btn qopt qapprove", "Approve");
    approve.title = `Takes the recommended choice: ${rec.n}. ${rec.text}`;
    approve.addEventListener("click", () => pick("recommended", `${rec.n}. ${rec.text} (recommended)`));
    buttons.append(approve);
  }
  for (const o of opts) {
    const b = el("button", o.recommended ? "btn qopt" : "qopt plain", `${o.n}. ${o.text}`);
    if (o.recommended) b.append(el("span", "qrec", "recommended"));
    b.addEventListener("click", () => pick(o.n, `${o.n}. ${o.text}`));
    buttons.append(b);
  }
  const ask = el("button", "qopt plain qask-first", "Ask me first");
  ask.addEventListener("click", () => pick("ask", "Ask me first"));
  buttons.append(ask);
  if (BATCH.items.has(q.id)) { status.textContent = `In the batch: ${BATCH.items.get(q.id).label}`; }
  c.append(buttons, note, status);
  return c;
}

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
  toggle.addEventListener("click", () => { BATCH.on = !BATCH.on; paint(); });
  clear.addEventListener("click", () => { BATCH.items.clear(); paint(); redraw(); });
  go.addEventListener("click", async () => {
    say.className = "qnote";
    say.textContent = "Sending...";
    try {
      const r = await fetch("/api/answer-batch", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Bench-Key": KEY },
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

export async function mount(view) {
  stylesheet();
  const draw = async () => {
    let d;
    try {
      const r = await fetch("/api/questions", { cache: "no-store" });
      d = await r.json();
    } catch (e) {
      view.replaceChildren(absent(`The questions could not be read: ${e.message}`));
      return;
    }
    if (d.absent) { view.replaceChildren(absent(d.absent)); return; }
    const head = el("p", "src", `QUESTIONS.md · ${d.waiting} waiting, ${d.answered} answered` +
      (d.refused ? `, ${d.refused} that cannot be answered yet` : "") + " · a click writes one message to INBOX.md");
    const order = (q) => (q.refused ? 1 : q.answer ? 2 : 0);
    const cards = [...d.questions].sort((a, b) => order(a) - order(b)).map((q) => card(q, draw));
    view.replaceChildren(head, bar, ...(cards.length ? cards : [absent("QUESTIONS.md holds no questions.")]));
  };
  const bar = batchBar(() => draw());
  await draw();
}
