// The Checks history room: every check in the gates ledger, its results oldest to newest as a strip of marks -- pass, fail, and
// refused as its own mark -- with its newest and slowest time, and "not run at the newest commit" where it has no line there.
// Read-only: it writes nothing. Text always goes in as text, never as markup.

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
const absent = (text) => el("p", "absent", text);
const WORD = { pass: "passed", fail: "failed", refused: "refused (could not look)", other: "an unknown result" };

function stylesheet() {
  if (document.getElementById("room-history-css")) return;
  const link = el("link");
  link.id = "room-history-css";
  link.rel = "stylesheet";
  link.href = "/rooms/checks-history.css";
  document.head.append(link);
}

function row(c, newestCommit) {
  const tr = el("tr");
  tr.append(el("td", "hname", c.name));
  const strip = el("td", "hstrip");
  for (const m of c.marks) {
    const s = el("span", `hmark ${m.mark}`, m.mark === "refused" ? "R" : m.mark === "other" ? "?" : "");
    s.title = `${WORD[m.mark]}${m.result && m.mark === "other" ? ` (${m.result})` : ""}` +
      `${m.commit ? ` at ${m.commit.slice(0, 9)}` : ""}${m.at ? `, ${m.at}` : ""}${m.seconds != null ? `, ${m.seconds} s` : ""}`;
    strip.append(s);
  }
  if (c.runs > c.marks.length) strip.prepend(el("span", "hmore", `+${c.runs - c.marks.length} older`));
  tr.append(strip);
  tr.append(el("td", "hnum", c.newest && c.newest.seconds != null ? `${c.newest.seconds} s` : "--"));
  tr.append(el("td", "hnum", c.slowest != null ? `${c.slowest} s` : "--"));
  const flag = el("td");
  if (c.notRunAtNewest) flag.append(el("span", "chip warn", `not run at ${String(newestCommit).slice(0, 9)}`));
  else if (c.newest) flag.append(el("span", `chip ${c.newest.mark === "pass" ? "ok" : c.newest.mark === "fail" ? "bad" : "warn"}`,
    WORD[c.newest.mark]));
  tr.append(flag);
  return tr;
}

export async function mount(view) {
  stylesheet();
  let d;
  try {
    const r = await fetch("/api/history", { cache: "no-store" });
    d = await r.json();
  } catch (e) {
    view.replaceChildren(absent(`The checks ledger could not be read: ${e.message}`));
    return;
  }
  if (d.absent) { view.replaceChildren(absent(d.absent)); return; }
  const card = el("section", "card");
  card.append(el("div", "eyebrow", `Checks history · from ${d.ledger}`));
  if (!d.checks.length) card.append(absent(`${d.ledger} has no line the bench can read.`));
  else {
    const table = el("table", "htable");
    const head = el("tr");
    for (const h of ["Check", `Results, oldest to newest (the last ${d.kept})`, "Newest", "Slowest", "Now"]) head.append(el("th", null, h));
    table.append(head);
    for (const c of d.checks) table.append(row(c, d.newestCommit));
    card.append(table);
  }
  const legend = el("p", "src");
  legend.append("Green passed, red failed, R refused (the check could not look, which is neither). Hover a mark for its commit and time. ");
  legend.append(`${d.lines} line${d.lines === 1 ? "" : "s"} read` + (d.unparsed ? `, ${d.unparsed} not readable and left out` : "") +
    (d.newestCommit ? `; the newest commit in the ledger is ${d.newestCommit.slice(0, 9)}.` : "."));
  legend.append(" Whether a result is stale (its files changed since) is the gates tool's own --status; the bench does not recompute it.");
  card.append(legend);
  view.replaceChildren(card);
}
