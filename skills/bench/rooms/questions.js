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
  if (q.answer) {
    c.append(el("p", "qdone", `Your answer: ${q.answer.choice}`),
      el("p", "src", `INBOX.md ${q.answer.message} · ${q.answer.at} · ${q.answer.status}`));
    return c;
  }
  const opts = [...q.options].sort((a, b) => Number(b.recommended) - Number(a.recommended));
  const note = el("textarea", "qnotebox");
  note.placeholder = "A note with your answer (optional)";
  note.maxLength = 2000;
  const status = el("p", "qnote");
  const buttons = el("div", "qopts");
  for (const o of opts) {
    const b = el("button", o.recommended ? "btn qopt" : "qopt plain", `${o.n}. ${o.text}`);
    if (o.recommended) b.append(el("span", "qrec", "recommended"));
    b.addEventListener("click", async () => { if (await send(q, o.n, note, status)) redraw(); });
    buttons.append(b);
  }
  const ask = el("button", "qopt plain qask-first", "Ask me first");
  ask.addEventListener("click", async () => { if (await send(q, "ask", note, status)) redraw(); });
  buttons.append(ask);
  c.append(buttons, note, status);
  return c;
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
    view.replaceChildren(head, ...(cards.length ? cards : [absent("QUESTIONS.md holds no questions.")]));
  };
  await draw();
}
