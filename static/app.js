const $ = (id) => document.getElementById(id);
let current = null; // {name,country,admin1,latitude,longitude,timezone}
let charts = {};

function msg(text, error = false) {
  $("msg").textContent = text;
  $("msg").className = "msg" + (error ? " error" : "");
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Помилка ${r.status}`);
  return data;
}

const label = (c) => [c.name, c.admin1, c.country].filter(Boolean).join(", ");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

async function search() {
  const q = $("q").value.trim();
  if (q.length < 2) return msg("Введіть щонайменше 2 символи", true);
  msg("Шукаю…");
  $("suggestions").innerHTML = "";
  try {
    const cities = await api("/api/cities/search?q=" + encodeURIComponent(q));
    msg("");
    if (cities.length === 1) return choose(cities[0]);
    $("suggestions").innerHTML = cities.map((c, i) => `<li data-i="${i}">${esc(label(c))}</li>`).join("");
    $("suggestions").onclick = (e) => {
      const li = e.target.closest("li");
      if (li) choose(cities[li.dataset.i]);
    };
  } catch (e) { msg(e.message, true); }
}

async function choose(city) {
  current = city;
  $("suggestions").innerHTML = "";
  msg("Отримую погоду і поради… (перший запит може тривати кілька секунд)");
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    const res = await api("/api/advice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...city,
        profile: { activity: $("activity").value, cold_sensitivity: $("cold").value },
      }),
    });
    render(res);
    msg("");
    loadDashboard();
  } catch (e) { msg(e.message, true); }
  finally { document.querySelectorAll("button").forEach((b) => (b.disabled = false)); }
}

function render(res) {
  const w = res.weather, c = w.current, a = res.advice;
  $("result").classList.remove("hidden");
  $("cityName").textContent = label(res.city);
  $("temp").textContent = Math.round(c.temperature) + "°C";
  $("desc").textContent = c.description;
  $("feels").textContent = Math.round(c.feels_like) + "°C";
  $("wind").textContent = c.wind_speed + " км/год";
  $("precip").textContent = (w.today.precip_probability ?? "–") + "%";
  $("uv").textContent = w.today.uv_index ?? "–";
  $("days").innerHTML = w.daily.map((d) => {
    const name = new Date(d.date).toLocaleDateString("uk-UA", { weekday: "short", day: "numeric", month: "short" });
    return `<div class="day"><b>${esc(name)}</b>${esc(d.description)}<br>${Math.round(d.temp_min)}…${Math.round(d.temp_max)}°C<br>☔ ${d.precip_probability ?? "–"}%</div>`;
  }).join("");
  $("summary").textContent = a.summary;
  const parts = [["Голова", a.outfit.head], ["Верх", a.outfit.top], ["Низ", a.outfit.bottom], ["Взуття", a.outfit.shoes]];
  $("outfit").innerHTML = parts.map(([k, v]) => `<div><small>${k}</small>${esc(v)}</div>`).join("");
  $("badges").innerHTML =
    `<span class="badge ${a.umbrella ? "on" : ""}">☂ Парасоля: ${a.umbrella ? "так" : "ні"}</span>` +
    `<span class="badge ${a.sunscreen ? "on" : ""}">🧴 Крем від сонця: ${a.sunscreen ? "так" : "ні"}</span>`;
  $("warnings").innerHTML = a.warnings.map((x) => `<li>⚠ ${esc(x)}</li>`).join("");
  $("tips").innerHTML = a.tips.map((x) => `<li>💡 ${esc(x)}</li>`).join("");
  const src = res.model_used === "rules" ? "правила (Gemini недоступний)" : res.model_used;
  $("meta").textContent = `Джерело порад: ${src} · ${res.latency_ms} мс`;
  $("result").scrollIntoView({ behavior: "smooth" });
}

async function loadFavorites() {
  try {
    const favs = await api("/api/favorites");
    $("favs").innerHTML = favs.map((c, i) => `<span class="chip" data-i="${i}">★ ${esc(c.name)}</span>`).join("");
    $("favs").onclick = (e) => {
      const chip = e.target.closest(".chip");
      if (chip) choose(favs[chip.dataset.i]);
    };
    return favs;
  } catch { return []; }
}

async function toggleFavorite() {
  if (!current) return;
  try {
    const favs = await api("/api/favorites");
    const same = favs.find((f) => Math.abs(f.latitude - current.latitude) < 1e-3 && Math.abs(f.longitude - current.longitude) < 1e-3);
    if (same) await api("/api/favorites/" + same.id, { method: "DELETE" });
    else await api("/api/favorites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(current) });
    await loadFavorites();
    msg(same ? "Прибрано з улюблених" : "Додано в улюблені");
  } catch (e) { msg(e.message, true); }
}

function chart(id, type, labels, data, title) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), {
    type, data: { labels, datasets: [{ label: title, data, backgroundColor: "#2f7cf6", borderColor: "#2f7cf6" }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}

async function loadDashboard() {
  try {
    const [s, h] = await Promise.all([api("/api/stats"), api("/api/history?limit=10")]);
    $("kpis").innerHTML = [
      [s.total_requests, "запитів усього"],
      [Math.round(s.rainy_share * 100) + "%", "запитів з дощем (≥50%)"],
      [s.avg_latency_ms != null ? s.avg_latency_ms + " мс" : "–", "середня відповідь"],
    ].map(([v, l]) => `<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join("");
    if (window.Chart) {
      chart("topChart", "bar", s.top_cities.map((c) => c.name), s.top_cities.map((c) => c.requests), "Запити");
      chart("dayChart", "line", s.requests_per_day.map((d) => d.day), s.requests_per_day.map((d) => d.count), "Запити");
    }
    $("history").querySelector("tbody").innerHTML = h.map((r) =>
      `<tr><td>${new Date(r.created_at).toLocaleString("uk-UA")}</td><td>${esc(r.city)}</td><td>${r.temperature ?? "–"}</td><td>${r.feels_like ?? "–"}</td><td>${esc(r.model_used)}</td><td>${r.latency_ms ?? "–"}</td></tr>`
    ).join("");
  } catch { /* дашборд не критичний */ }
}

$("searchBtn").onclick = search;
$("q").addEventListener("keydown", (e) => e.key === "Enter" && search());
$("favBtn").onclick = toggleFavorite;
$("geoBtn").onclick = () => {
  if (!navigator.geolocation) return msg("Геолокація недоступна", true);
  msg("Визначаю місцезнаходження…");
  navigator.geolocation.getCurrentPosition(
    (p) => choose({ name: "Моє місце", latitude: +p.coords.latitude.toFixed(4), longitude: +p.coords.longitude.toFixed(4) }),
    () => msg("Не вдалося отримати геолокацію", true),
  );
};

loadFavorites();
loadDashboard();
