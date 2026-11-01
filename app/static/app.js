/* DayForge frontend — vanilla JS, no build step. */
const $ = (id) => document.getElementById(id);
let token = localStorage.getItem("dayforge_token") || "";
let currentDate = new Date().toISOString().slice(0, 10);
let currentDay = null;

function headers() { return { "Content-Type": "application/json", Authorization: "Bearer " + token }; }
async function api(path, method = "GET", body) {
  const r = await fetch(path, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || ("Request failed: " + r.status));
  return data;
}
function fmt(mins) { let h = Math.floor(mins / 60), m = mins % 60; const ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12; return `${h}:${String(m).padStart(2, "0")} ${ap}`; }
function dur(s, e) { const d = e - s; return d >= 60 ? `${Math.floor(d / 60)}h ${d % 60}m` : `${d}m`; }

/* ---- Time picker with a truly clearable Custom minute field ----
   The custom input starts EMPTY (value=""), never "0", so backspace/delete
   can clear it completely. An empty custom value means 0 minutes. */
function buildTimePicker(el) {
  el.innerHTML = "";
  const hour = document.createElement("select");
  for (let h = 1; h <= 12; h++) { const o = document.createElement("option"); o.value = h; o.textContent = h; hour.appendChild(o); }
  const ap = document.createElement("select");
  ["AM", "PM"].forEach((v) => { const o = document.createElement("option"); o.value = v; o.textContent = v; ap.appendChild(o); });
  const minMode = document.createElement("select");
  ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "Custom…"].forEach((v) => {
    const o = document.createElement("option"); o.value = v; o.textContent = v === "Custom…" ? "Custom…" : v; minMode.appendChild(o);
  });
  const custom = document.createElement("input");
  custom.type = "text"; custom.inputMode = "numeric"; custom.placeholder = "e.g. 38";
  custom.value = ""; custom.className = "hidden"; custom.setAttribute("aria-label", "Custom minutes");
  custom.addEventListener("input", () => { custom.value = custom.value.replace(/[^0-9]/g, "").slice(0, 2); });
  minMode.addEventListener("change", () => custom.classList.toggle("hidden", minMode.value !== "Custom…"));
  el.append(hour, minMode, custom, ap);
  return { get() {
    let h = parseInt(hour.value, 10); if (ap.value === "PM" && h !== 12) h += 12; if (ap.value === "AM" && h === 12) h = 0;
    let m = 0;
    if (minMode.value === "Custom…") { const v = custom.value.trim(); m = v === "" ? 0 : parseInt(v, 10); }
    else m = parseInt(minMode.value, 10);
    if (isNaN(m) || m < 0 || m > 59) throw new Error("Minutes must be 0–59");
    return h * 60 + m;
  }, set(total) { let h24 = Math.floor(total / 60); const apv = h24 >= 12 ? "PM" : "AM"; let h = h24 % 12 || 12; hour.value = h; ap.value = apv; const m = total % 60; minMode.value = String(m).padStart(2, "0"); custom.classList.add("hidden"); } };
}
const startPicker = buildTimePicker($("start-picker"));
const endPicker = buildTimePicker($("end-picker"));
startPicker.set(540); endPicker.set(600);

function show(view) {
  ["auth", "onboarding", "dashboard", "profile", "weekly", "monthly", "calendar", "templates", "notifications", "settings"].forEach((v) => $("view-" + v).classList.add("hidden"));
  $("view-" + view).classList.remove("hidden");
}
function applyTheme(theme) {
  const t = theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("dayforge_theme", theme);
}
document.querySelectorAll("[data-theme-btn]").forEach((b) => b.addEventListener("click", async () => {
  applyTheme(b.dataset.themeBtn);
  try { await api("/api/settings", "PATCH", { theme: b.dataset.themeBtn }); $("set-msg").textContent = "Theme saved."; } catch (e) { $("set-msg").textContent = e.message; }
}));
document.querySelectorAll("[data-nav]").forEach((b) => b.addEventListener("click", () => {
  const v = b.dataset.nav; show(v);
  if (v === "weekly") loadWeekly(); if (v === "monthly") loadMonthly(); if (v === "calendar") loadCalendar();
  if (v === "templates") loadTemplates(); if (v === "notifications") loadNotifs(); if (v === "settings") loadSettings();
}));
$("open-profile-btn").addEventListener("click", loadProfile);
$("logout-btn").addEventListener("click", async () => { try { await api("/api/auth/logout", "POST"); } catch (e) {} token = ""; localStorage.removeItem("dayforge_token"); show("auth"); $("profile-strip-text").textContent = "Not signed in"; });

async function afterLogin() {
  const me = await api("/api/auth/me");
  $("profile-strip-text").textContent = `${me.name || me.email} · Day ${me.journey_start_date ? 1 : "?"} · ${me.xp} XP`;
  applyTheme(me.theme || localStorage.getItem("dayforge_theme") || "system");
  if (!me.journey_start_date) { $("ob-name").value = me.name || ""; $("ob-tz").value = me.timezone || "Asia/Karachi"; show("onboarding"); }
  else await loadDashboard();
}
$("login-btn").addEventListener("click", async () => {
  try { const d = await api("/api/auth/login", "POST", { email: $("auth-email").value, password: $("auth-pass").value }); token = d.access_token; localStorage.setItem("dayforge_token", token); await afterLogin(); }
  catch (e) { $("auth-msg").textContent = e.message; }
});
$("register-btn").addEventListener("click", async () => {
  try { const d = await api("/api/auth/register", "POST", { email: $("auth-email").value, password: $("auth-pass").value, name: $("auth-name").value || "Friend" }); token = d.access_token; localStorage.setItem("dayforge_token", token); await afterLogin(); }
  catch (e) { $("auth-msg").textContent = e.message; }
});
$("forgot-btn").addEventListener("click", async () => {
  try { const d = await api("/api/auth/forgot-password", "POST", { email: $("forgot-email").value }); $("forgot-msg").textContent = d.detail + (d.reset_token ? " (dev token: " + d.reset_token + ")" : ""); }
  catch (e) { $("forgot-msg").textContent = e.message; }
});
$("ob-btn").addEventListener("click", async () => {
  try { await api("/api/onboarding", "POST", { name: $("ob-name").value, age: $("ob-age").value ? parseInt($("ob-age").value, 10) : null, timezone: $("ob-tz").value || "UTC", notification_prefs: {}, auto_confirm: $("ob-auto").checked }); await loadDashboard(); }
  catch (e) { alert(e.message); }
});

async function loadDashboard() {
  show("dashboard");
  const d = await api(`/api/dashboard?date_str=${currentDate}`);
  currentDay = d.day;
  $("dash-date").textContent = d.date; $("dash-weekday").textContent = d.weekday; $("dash-daynum").textContent = d.day_number;
  $("dash-streak").textContent = d.streak; $("dash-xp").textContent = d.xp; $("dash-level").textContent = d.level;
  $("dash-ring").textContent = d.day.percent + "%";
  $("dash-stats").textContent = `${d.day.completed} completed · ${d.day.missed} missed · ${d.day.total} total · ${d.day.on_holiday} on holiday`;
  $("dash-status").textContent = d.day.status === "open" ? "Open day" : (d.day.status === "confirmed" ? "✓ Confirmed (locked)" : "Automatically Confirmed");
  $("confirm-history").textContent = d.confirmations.length ? "Confirmation history: " + d.confirmations.map((c) => `${c.action} ${c.final_percent ?? ""}%`).join(" → ") : "";
  const area = $("complete-area"); area.innerHTML = "";
  if (d.day.status === "open") {
    const b = document.createElement("button"); b.textContent = "Complete Day"; b.onclick = () => {
      $("complete-text").textContent = `Completed ${d.day.completed}, incomplete ${d.day.missed}. Expected final: ${d.day.percent}%. This will lock the day.`;
      $("complete-modal").classList.remove("hidden");
    }; area.appendChild(b);
  } else {
    const undo = document.createElement("button"); undo.className = "secondary"; undo.textContent = "Undo Confirmation";
    undo.onclick = async () => { await api(`/api/days/${d.day.id}/undo`, "POST"); await loadDashboard(); }; area.appendChild(undo);
    const plan = document.createElement("button"); plan.textContent = "Plan next day";
    plan.onclick = async () => { const r = await api(`/api/days/${d.day.id}/copy-to-next`, "POST"); currentDate = r.next_day.date; await loadDashboard(); alert(`Copied ${r.copied} goals — you're now on the next day.`); }; area.appendChild(plan);
    const copy = document.createElement("button"); copy.className = "secondary"; copy.textContent = "Copy this day";
    copy.onclick = async () => { const r = await api(`/api/days/${d.day.id}/copy-to-next`, "POST"); currentDate = r.next_day.date; await loadDashboard(); }; area.appendChild(copy);
  }
  renderGoals(d.day);
  loadHistory(); loadCategories();
}
$("confirm-complete").addEventListener("click", async () => {
  $("complete-modal").classList.add("hidden");
  try { const r = await api(`/api/days/${currentDay.id}/complete`, "POST"); alert(`🎉 Day completed at ${r.final_percent}%! Streak: ${r.streak}, XP: ${r.xp}`); await loadDashboard(); } catch (e) { alert(e.message); }
});
$("cancel-complete").addEventListener("click", () => $("complete-modal").classList.add("hidden"));
$("prev-day").addEventListener("click", () => { const dt = new Date(currentDate); dt.setDate(dt.getDate() - 1); currentDate = dt.toISOString().slice(0, 10); loadDashboard(); });
$("next-day").addEventListener("click", () => { const dt = new Date(currentDate); dt.setDate(dt.getDate() + 1); currentDate = dt.toISOString().slice(0, 10); loadDashboard(); });
setInterval(() => { if ($("dash-clock")) $("dash-clock").textContent = new Date().toLocaleTimeString(); }, 1000);

function renderGoals(day) {
  const list = $("goal-list"); list.innerHTML = "";
  day.goals.forEach((g, i) => {
    const div = document.createElement("div"); div.className = "goal";
    div.innerHTML = `<input type="checkbox" ${g.completed ? "checked" : ""} ${g.on_holiday || day.status !== "open" ? "disabled" : ""}>
      <div style="flex:1"><strong>${g.name}</strong> <span class="muted">${fmt(g.start_minutes)} – ${fmt(g.end_minutes)} · ${dur(g.start_minutes, g.end_minutes)} · ${g.category}</span>
      ${g.notes ? `<div class="muted">${g.notes}</div>` : ""} ${g.on_holiday ? `<span class="badge">On holiday</span>` : ""}</div>`;
    div.querySelector("input").addEventListener("change", async (e) => {
      try { await api(`/api/goals/${g.id}`, "PATCH", { completed: e.target.checked }); await loadDashboard(); } catch (err) { alert(err.message); }
    });
    const mk = (label, fn) => { const b = document.createElement("button"); b.className = "secondary"; b.textContent = label; b.onclick = fn; div.appendChild(b); };
    if (day.status === "open") {
      mk(g.on_holiday ? "End holiday" : "Holiday", async () => { await api(`/api/goals/${g.id}`, "PATCH", { on_holiday: !g.on_holiday }); await loadDashboard(); });
      mk("↑", async () => { if (i > 0) { const ids = day.goals.map((x) => x.id); [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]; await api(`/api/days/${day.id}/goals/reorder`, "POST", ids); await loadDashboard(); } });
      mk("Delete", async () => { if (confirm("Delete this goal?")) { await api(`/api/goals/${g.id}`, "DELETE"); await loadDashboard(); } });
    }
    list.appendChild(div);
  });
}
async function loadHistory() {
  const box = $("history-box");
  try {
    const d = await api("/api/goals/history");
    if (!d.history.length) { box.innerHTML = ""; return; }
    box.innerHTML = "<strong>Add again from your history</strong><div class='row' style='margin:8px 0'></div>";
    const row = box.querySelector(".row");
    d.history.slice(0, 8).forEach((g) => {
      const b = document.createElement("button"); b.className = "secondary"; b.textContent = `+ Add ${g.name} again (${fmt(g.start_minutes)}–${fmt(g.end_minutes)})`;
      b.onclick = async () => { await api(`/api/days/${currentDay.id}/goals/quick-add`, "POST", { source_goal_id: g.id }); await loadDashboard(); };
      row.appendChild(b);
    });
  } catch (e) { box.innerHTML = ""; }
}
async function loadCategories() {
  try {
    const d = await api("/api/categories");
    $("goal-cat").innerHTML = d.categories.map((c) => `<option>${c}</option>`).join("");
    $("search-cat").innerHTML = `<option value="">All categories</option>` + d.categories.map((c) => `<option>${c}</option>`).join("");
    $("cat-list").textContent = d.categories.join(", ");
  } catch (e) {}
}
$("add-goal-btn").addEventListener("click", async () => {
  try {
    const s = startPicker.get(), e = endPicker.get();
    const r = await api(`/api/days/${currentDay.id}/goals`, "POST", { name: $("goal-name").value.trim(), start_minutes: s, end_minutes: e, category: $("goal-cat").value, notes: $("goal-notes").value, on_holiday: $("goal-holiday").checked });
    $("goal-msg").textContent = r.overlap_warnings.length ? "Warning: " + r.overlap_warnings.join("; ") : "Goal added.";
    await loadDashboard();
  } catch (err) { $("goal-msg").textContent = err.message; }
});

async function loadProfile() {
  show("profile");
  const p = await api("/api/profile");
  $("profile-details").innerHTML = `<p><strong>${p.name}</strong> ${p.age != null ? `<span class="badge">Age ${p.age}</span>` : ""}</p>
    <p class="muted">Day ${p.day_number ?? "?"} · Level ${p.level} · ${p.xp} XP · Streak ${p.streak} days<br>
    Timezone: ${p.timezone} · Journey start: ${p.journey_start_date || "—"} · Tasks completed: ${p.total_completed_tasks}<br>
    Achievements: ${p.achievements.map((a) => a.name).join(", ") || "None yet"}</p>`;
  $("pf-name").value = p.name || ""; $("pf-age").value = p.age ?? ""; $("pf-tz").value = p.timezone || "";
}
$("pf-save").addEventListener("click", async () => {
  try { await api("/api/profile", "PATCH", { name: $("pf-name").value, age: $("pf-age").value ? parseInt($("pf-age").value, 10) : null, timezone: $("pf-tz").value }); $("pf-msg").textContent = "Profile saved."; await loadProfile(); } catch (e) { $("pf-msg").textContent = e.message; }
});

async function loadWeekly() {
  const w = await api(`/api/analytics/weekly?date_str=${currentDate}`);
  $("weekly-body").innerHTML = `<p>${w.week_start} → ${w.week_end} · ${w.percent}% · ${w.total_completed}/${w.total_scheduled} goals · Confirmed ${w.confirmed_days} · Auto ${w.auto_confirmed_days} · Open ${w.open_days}</p>
    <p>Best: ${w.best_day ? w.best_day.join(" ") + "%" : "—"} · Lowest: ${w.lowest_day ? w.lowest_day.join(" ") + "%" : "—"}</p>
    ${w.daily.map((d) => `<div>${d.weekday} ${d.date} — ${d.percent}% (${d.status})<div class="bar"><div style="width:${d.percent}%"></div></div></div>`).join("")}
    <h4>Per task</h4><p>${w.per_task.map((t) => `${t.name}: ${t.completed} done, ${t.missed} missed`).join("<br>") || "—"}</p>`;
}
async function loadMonthly() {
  const d = new Date(currentDate);
  const m = await api(`/api/analytics/monthly?year=${d.getFullYear()}&month=${d.getMonth() + 1}`);
  $("monthly-body").innerHTML = `<p>${m.month} · ${m.percent}% · Avg daily ${m.average_daily_percent}% · Consistency ${m.consistency_score}%</p>
    <p>Best: ${m.best_day ? m.best_day.join(" ") + "%" : "—"} · Weakest: ${m.lowest_day ? m.lowest_day.join(" ") + "%" : "—"}</p>
    <p>${m.review.summary}</p><p>Did well: ${m.review.did_well.join(", ") || "—"}<br>Struggled: ${m.review.struggled_with.join(", ") || "—"}<br>${m.review.habits_to_improve.join("<br>")}</p>
    <h4>Week comparison</h4><p>${m.week_comparison.map((w) => `${w.week_start}: ${w.percent}%`).join("<br>")}</p>`;
  const imp = await api("/api/analytics/improvements");
  $("improve-body").innerHTML = `<h3>Improvements (from ${imp.based_on_confirmed_days} confirmed days)</h3><p>${imp.tips.join("<br>")}</p>`;
}
async function loadCalendar() {
  const d = new Date(currentDate);
  const c = await api(`/api/analytics/calendar?year=${d.getFullYear()}&month=${d.getMonth() + 1}`);
  $("calendar-body").innerHTML = `<div class="grid">${c.days.map((x) => `<div class="cell"><strong>${x.date.slice(8)}</strong><br>${x.percent}%<br><span class="muted">${x.status}</span></div>`).join("")}</div>`;
}
async function loadTemplates() {
  const t = await api("/api/templates");
  $("tpl-list").innerHTML = t.templates.map((x) => `<div class="row"><span>${x.name} (${x.goals_json.length} goals)</span><button class="secondary" data-apply="${x.id}">Apply to current day</button></div>`).join("") || "No templates yet.";
  document.querySelectorAll("[data-apply]").forEach((b) => b.onclick = async () => { await api(`/api/templates/${b.dataset.apply}/apply?day_id=${currentDay.id}`, "POST"); await loadDashboard(); show("dashboard"); });
}
$("tpl-save").addEventListener("click", async () => {
  const goals = currentDay.goals.map((g) => ({ name: g.name, start_minutes: g.start_minutes, end_minutes: g.end_minutes, category: g.category, notes: g.notes }));
  await api("/api/templates", "POST", { name: $("tpl-name").value || "My routine", goals_json: goals });
  loadTemplates();
});
$("cat-add").addEventListener("click", async () => { await api("/api/categories", "POST", { name: $("cat-name").value }); loadCategories(); });
$("search-btn").addEventListener("click", async () => {
  const s = await api(`/api/search?q=${encodeURIComponent($("search-q").value)}&category=${encodeURIComponent($("search-cat").value)}&status=${$("search-status").value}`);
  $("search-results").innerHTML = s.results.map((g) => `<div>${g.name} · ${fmt(g.start_minutes)}–${fmt(g.end_minutes)} · ${g.category} · ${g.completed ? "done" : "pending"}</div>`).join("") || "No results.";
});
async function loadNotifs() {
  const n = await api("/api/notifications");
  $("notif-list").innerHTML = n.notifications.map((x) => `<div class="goal"><div style="flex:1"><strong>${x.title}</strong><div class="muted">${x.body}</div></div></div>`).join("") || "No notifications yet.";
}
async function loadSettings() {
  const s = await api("/api/settings");
  $("set-auto").checked = s.auto_confirm;
  document.querySelectorAll(".notif-pref").forEach((c) => c.checked = !!(s.notification_prefs || {})[c.dataset.k]);
}
$("set-save").addEventListener("click", async () => {
  const prefs = {}; document.querySelectorAll(".notif-pref").forEach((c) => prefs[c.dataset.k] = c.checked);
  await api("/api/settings", "PATCH", { auto_confirm: $("set-auto").checked, notification_prefs: prefs });
  $("set-msg").textContent = "Settings saved.";
});
$("export-csv").addEventListener("click", async () => {
  const r = await fetch("/api/export/csv", { headers: headers() }); const blob = await r.blob();
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "dayforge.csv"; a.click();
});
$("export-json").addEventListener("click", async () => {
  const d = await api("/api/export/json"); const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); a.download = "dayforge-backup.json"; a.click();
});
$("restore-file").addEventListener("change", async (e) => {
  const text = await e.target.files[0].text();
  const r = await api("/api/import/json", "POST", { data: JSON.parse(text) });
  alert(`Restored ${r.restored_goals} goals.`); await loadDashboard();
});
$("delete-account").addEventListener("click", async () => {
  if (!confirm("Delete your account and ALL data? This cannot be undone.")) return;
  await api("/api/account", "DELETE"); token = ""; localStorage.removeItem("dayforge_token"); show("auth");
});
applyTheme(localStorage.getItem("dayforge_theme") || "system");
if (token) afterLogin().catch(() => show("auth")); else show("auth");
