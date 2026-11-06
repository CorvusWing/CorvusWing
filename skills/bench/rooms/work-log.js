// The Work log room: what got done each day, from WORKLOG.md, in day, week and month views. Every number here is the bench's
// count from the day sections (/api/worklog), never typed; a day with no section shows as no entry, never as zero. Each proof
// says whether it holds: a commit that exists in this repository, a file that exists in the project. Text goes in as text.

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
const absent = (text) => el("p", "absent", text);

function stylesheet() {
  if (document.getElementById("room-work-log-css")) return;
  const link = el("link");
  link.id = "room-work-log-css";
  link.rel = "stylesheet";
  link.href = "/rooms/work-log.css";
  document.head.append(link);
}

const VIEWS = [["day", "Day"], ["week", "Week"], ["month", "Month"]];
let view = "day";

function proofChip(e) {
  const label = e.proof.kind === "none" ? (e.proof.ref || "no proof") : `${e.proof.kind} ${e.proof.ref}`;
  const cls = e.holds === true ? "chip ok" : e.holds === false ? "chip bad" : "chip";
  const chip = el("span", `${cls} wproof`, label);
  chip.title = e.why;
  return chip;
}

function counts(r) {
  const parts = [`${r.entries} ${r.entries === 1 ? "entry" : "entries"} on ${r.daysWithWork} ${r.daysWithWork === 1 ? "day" : "days"}`,
    `${r.proven} proof${r.proven === 1 ? "" : "s"} hold`];
  if (r.failing) parts.push(`${r.failing} do not`);
  if (r.named) parts.push(`${r.named} check${r.named === 1 ? "" : "s"} named`);
  return parts.join(" · ");
}

// The newest day's week and month, as the bench counted them: shown above the days so a day is read beside its totals.
function totals(d) {
  const newest = d.days[0].date;
  const week = d.weeks.find((w) => w.days.some((x) => x.date === newest));
  const month = d.months.find((m) => m.month === newest.slice(0, 7));
  const box = el("div", "wtotals");
  if (week) box.append(el("div", "wtotal", null));
  if (week) box.lastChild.append(el("span", "eyebrow", `Week of ${week.start}`), el("p", "wsum", counts(week)));
  if (month) box.append(el("div", "wtotal", null));
  if (month) box.lastChild.append(el("span", "eyebrow", `Month ${month.month}`), el("p", "wsum", counts(month)));
  return box;
}

function dayView(d) {
  if (!d.days.length) return [absent("WORKLOG.md has no day sections yet.")];
  return [totals(d), ...d.days.map((day) => {
    const c = el("section", "card wday");
    c.append(el("span", "eyebrow", day.date));
    const t = el("table", "wtable");
    for (const e of day.entries) {
      const tr = el("tr");
      const proof = el("td");
      proof.append(proofChip(e));
      tr.append(el("td", null, e.what), proof);
      t.append(tr);
    }
    c.append(day.entries.length ? t : el("p", "src", "a section with no rows"));
    return c;
  })];
}

function weekView(d) {
  if (!d.weeks.length) return [absent("WORKLOG.md has no day sections yet.")];
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return d.weeks.map((w) => {
    const c = el("section", "card wweek");
    c.append(el("span", "eyebrow", `Week of ${w.start}`), el("p", "wsum", counts(w)));
    const strip = el("div", "wstrip");
    w.days.forEach((day, i) => {
      const cell = el("div", day.entries === null ? "wcell none" : "wcell");
      cell.title = day.date;
      cell.append(el("small", null, names[i]), el("b", null, day.entries === null ? "no entry" : String(day.entries)));
      strip.append(cell);
    });
    c.append(strip);
    return c;
  });
}

function monthView(d) {
  if (!d.months.length) return [absent("WORKLOG.md has no day sections yet.")];
  return d.months.map((m) => {
    const c = el("section", "card wmonth");
    c.append(el("span", "eyebrow", m.month), el("p", "wsum", counts(m)));
    return c;
  });
}

export async function mount(root) {
  stylesheet();
  const draw = async () => {
    let d;
    try {
      const r = await fetch("/api/worklog", { cache: "no-store" });
      d = await r.json();
    } catch (e) {
      root.replaceChildren(absent(`The work log could not be read: ${e.message}`));
      return;
    }
    if (d.absent) { root.replaceChildren(absent(d.absent)); return; }
    const head = el("p", "src", "WORKLOG.md · every count is the bench's, from the day sections · a proof holds when what it names exists");
    const tabs = el("div", "wtabs");
    for (const [id, label] of VIEWS) {
      const b = el("button", "qopt plain wtab" + (view === id ? " on" : ""), label);
      b.addEventListener("click", () => { view = id; draw(); });
      tabs.append(b);
    }
    const problems = d.problems.length ? [el("p", "qnote bad", `WORKLOG.md: ${d.problems.join("; ")}`)] : [];
    const body = view === "week" ? weekView(d) : view === "month" ? monthView(d) : dayView(d);
    root.replaceChildren(head, tabs, ...problems, ...body);
  };
  await draw();
}
