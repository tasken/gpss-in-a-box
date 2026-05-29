/* GPSS.viewer — power-user UI (vanilla, server-backed) */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const GEN_LABEL = { "3.1": "COLO", "3.2": "XD" };
const STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"];
const STAT_LABELS = { hp: "HP", atk: "ATK", def: "DEF", spa: "SPA", spd: "SPD", spe: "SPE" };
const STAT_LABELS_NATURE = { atk: "Atk", def: "Def", spe: "Spe", spa: "SpA", spd: "SpD", hp: "HP" };
const TYPE_COLORS = {
  Normal:"#A8A77A", Fire:"#EE8130", Water:"#6390F0", Electric:"#F7D02C",
  Grass:"#7AC74C", Ice:"#96D9D6", Fighting:"#C22E28", Poison:"#A33EA1",
  Ground:"#E2BF65", Flying:"#A98FF3", Psychic:"#F95587", Bug:"#A6B91A",
  Rock:"#B6A136", Ghost:"#735797", Dragon:"#6F35FC", Dark:"#705746",
  Steel:"#B7B7CE", Fairy:"#D685AD",
};
const FALLBACK_SPRITE = "/sprites/pokemon-gen8/unknown.png";
const EGG_SPRITE = "/sprites/pokemon-gen8/egg.png";

const state = {
  stats: { total: 0, legal_count: 0, generations: [] },
  list: [],
  page: 1,
  pages: 0,
  total: 0,
  selectedId: null,
  view: "list",
  legal: "any",
  shiny: "any",
  gen: "",
  sort: "recent",
  legalityCache: new Map(),
  focusedId: null,
};

const mobileQuery = window.matchMedia("(max-width: 900px)");
let isMobile = mobileQuery.matches;
mobileQuery.addEventListener("change", (e) => { isMobile = e.matches; });

const el = {
  q: $("#q"),
  results: $("#results"),
  detail: $("#detail"),
  detailEmpty: $("#detail-empty"),
  detailContent: $("#detail-content"),
  brandSub: $("#brand-sub"),
  matchCount: $("#match-count"),
  matchTotal: $("#match-total"),
  genGrid: $("#gen-grid"),
  bcrumbs: $("#bcrumbs"),
  pager: $("#pager"),
  prev: $("#prev"),
  next: $("#next"),
  pageNum: $("#page-num"),
  pagesTotal: $("#pages-total"),
  pageJump: $("#page-jump"),
  pagerMeta: $("#pager-meta"),
  resetFilters: $("#reset-filters"),
  sort: $("#sort"),
  sxFiltered: $("#sx-filtered"),
  sxPage: $("#sx-page"),
  sxCoverage: $("#sx-coverage"),
  statusGpss: $("#status-gpss"),
  statusDb: $("#status-db"),
  statusLegality: $("#status-legality"),
  statusSprites: $("#status-sprites"),
  railStatus: $("#rail-status"),
  page: $("#page"),
};

function fmtInt(n) {
  return Number(n).toLocaleString("en-US");
}

function typeBadge(type) {
  const bg = TYPE_COLORS[type] || "#888";
  return `<span class="type-badge" style="background:${bg}">${esc(type)}</span>`;
}

function typeBadges(types) {
  if (!types || !types.length) return "";
  return `<span class="type-badges">${types.map(typeBadge).join("")}</span>`;
}

function natureModifiers(p) {
  if (!p.nature_plus) return "";
  return ` <span class="nature-plus">+${STAT_LABELS_NATURE[p.nature_plus] || p.nature_plus}</span> <span class="nature-minus">-${STAT_LABELS_NATURE[p.nature_minus] || p.nature_minus}</span>`;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s ?? "");
  return d.innerHTML;
}

function genShort(g) {
  return GEN_LABEL[g] || `G${g}`;
}

const GEN_COLORS = {
  "1": "#E53935", "2": "#F9A825", "3": "#43A047", "4": "#1E88E5",
  "5": "#6D4C41", "6": "#5E35B1", "7": "#F4511E", "8": "#00897B",
  "9": "#C62828",
};

function genBadge(gen) {
  const major = String(gen).split(".")[0];
  const bg = GEN_COLORS[major] || "#555";
  const label = String(gen).startsWith("3.1") ? "GC" : String(gen).startsWith("3.2") ? "XD" : `G${major}`;
  return `<span class="gen-badge" style="background:${bg}">${esc(label)}</span>`;
}

function hasNickname(p) {
  return Boolean(p.nickname && p.nickname.trim());
}

function displayName(p) {
  return hasNickname(p) ? p.nickname : p.species_name;
}

function genderGlyph(g, gen) {
  if (g === 1) return { g: "♀", c: "var(--pink)" };
  if (g === 2) return { g: "—", c: "var(--mut)" };
  const major = String(gen).split(".")[0];
  if (["1", "2", "3"].includes(major)) return { g: "?", c: "var(--mut)" };
  return { g: "♂", c: "var(--blu)" };
}

function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s.replace(" +0000 UTC", "Z").replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return s.slice(0, 10);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" });
}

const TAG = {
  legal: { cls: "tag-ok", label: "legal" },
  illegal: { cls: "tag-err", label: "illegal" },
  shiny: { cls: "tag-shiny", label: "shiny" },
  egg: { cls: "tag-warn", label: "egg" },
  pkhex: { cls: "tag-info", label: "pkhex" },
  db: { cls: "tag-neutral", label: "database" },
  drift: { cls: "tag-warn", label: "drift" },
  info: { cls: "tag-info", label: "note" },
};

/** Uniform status tag markup. */
function tag(kind, label) {
  const def = TAG[kind] || { cls: "tag-neutral", label: String(kind) };
  const text = (label ?? def.label).toLowerCase();
  return `<span class="tag ${def.cls}">${esc(text)}</span>`;
}

function lgBanner(kind, text) {
  return `<div class="lg-banner lg-banner-${esc(kind)}">${tag(kind)} ${esc(text)}</div>`;
}

/** Render a row of tags for a pokémon entry. */
function pokemonTags(p, opts = {}) {
  const { legal = true, shiny = true, egg = true } = opts;
  const parts = [];
  if (legal) parts.push(tag(p.legal ? "legal" : "illegal"));
  if (shiny && p.shiny) parts.push(tag("shiny"));
  if (egg && p.is_egg) parts.push(tag("egg"));
  if (!parts.length) return "";
  return `<span class="tags">${parts.join("")}</span>`;
}

function anyFilter() {
  return (
    el.q.value.trim() ||
    state.gen ||
    state.legal !== "any" ||
    state.shiny !== "any" ||
    state.sort !== "recent"
  );
}

function pageLimit() {
  if (state.view !== "grid") return 24;
  const grid = $(".results");
  if (!grid) return 18;
  const w = grid.clientWidth - 32;
  const h = grid.clientHeight - 28;
  if (w <= 0 || h <= 0) return 18;
  const cols = Math.max(1, Math.floor(w / 171));
  const rows = Math.max(1, Math.floor(h / 180));
  return Math.max(cols * rows, 6);
}

function apiParams() {
  const p = new URLSearchParams({
    page: String(state.page),
    limit: String(pageLimit()),
    sort: state.sort,
  });
  const q = el.q.value.trim();
  if (q) p.set("q", q);
  if (state.gen) p.set("gen", state.gen);
  if (state.legal === "legal") p.set("legal", "1");
  else if (state.legal === "illegal") p.set("legal", "0");
  if (state.shiny === "shiny") p.set("shiny", "1");
  else if (state.shiny === "regular") p.set("shiny", "0");
  return p;
}

function updateChrome() {
  const { total, stats } = state;
  el.matchCount.innerHTML = `${fmtInt(total)}<span class="meta-sub">/${fmtInt(stats.total)}</span>`;
  el.sxFiltered.textContent = fmtInt(total);
  el.sxPage.textContent = state.pages ? `${state.page}/${state.pages}` : "—";
  const cov =
    stats.total > 0
      ? ((stats.legal_count / stats.total) * 100).toFixed(2) + "%"
      : "—";
  el.sxCoverage.textContent = cov;
  el.resetFilters.hidden = !anyFilter();

  const crumbs = ["all"];
  if (state.gen) crumbs.push(`gen ${state.gen}`);
  if (state.legal !== "any") crumbs.push(state.legal);
  if (state.shiny !== "any") crumbs.push(state.shiny);
  if (el.q.value.trim()) crumbs.push(`"${el.q.value.trim()}"`);
  el.bcrumbs.innerHTML = crumbs
    .map((c, i) =>
      i === 0
        ? `<span>${esc(c)}</span>`
        : `<span class="bsep">›</span><span>${esc(c)}</span>`
    )
    .join("");

  el.pageNum.textContent = String(state.page);
  el.pagesTotal.textContent = String(state.pages || 1);
  el.pageJump.value = String(state.page);
  el.pageJump.max = String(state.pages || 1);
  el.prev.disabled = state.page <= 1;
  el.next.disabled = state.page >= state.pages;
  el.pagerMeta.textContent = state.pages
    ? `${fmtInt(total)} rows · ${pageLimit()}/page`
    : "";
}

function statusStrong(label, tone) {
  return `${label} <strong class="${tone}">${tone === "ok" ? "online" : tone === "err" ? "offline" : "—"}</strong>`;
}

function renderServices(svc) {
  if (!svc) return;
  const gpss = svc.gpss || {};
  if (gpss.online) {
    el.statusGpss.innerHTML = statusStrong("gpss", "ok");
  } else if (!gpss.configured) {
    el.statusGpss.innerHTML =
      'gpss <strong class="err">offline</strong> <span class="mut">(viewer only)</span>';
  } else {
    el.statusGpss.innerHTML =
      'gpss <strong class="err">unreachable</strong>';
  }

  const leg = svc.legality || {};
  if (leg.mode === "gpss") {
    el.statusLegality.innerHTML =
      'legality <strong class="ok">live</strong> <span class="mut">(gpss api)</span>';
  } else if (leg.mode === "console") {
    el.statusLegality.innerHTML =
      'legality <strong class="ok">pkhex</strong> <span class="mut">(no gpss api)</span>';
  } else {
    el.statusLegality.innerHTML =
      'legality <strong class="err">unavailable</strong>';
  }

  const spr = svc.sprites || {};
  if (spr.online) {
    el.statusSprites.innerHTML =
      `sprites <strong class="ok">${esc(spr.source || "local")}</strong>`;
  } else {
    el.statusSprites.innerHTML =
      'sprites <strong class="err">missing</strong>';
  }

  if (el.railStatus) {
    const bits = [];
    if (gpss.online) bits.push("gpss api");
    else if (leg.mode === "console") bits.push("pkhex local");
    bits.push("index ready");
    el.railStatus.textContent = bits.join(" · ");
  }
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const data = await res.json();
  state.stats = data;
  el.brandSub.textContent = `${fmtInt(data.total)} entries · indexed`;
  el.statusDb.innerHTML = `db <strong class="ok">${fmtInt(data.total)}</strong>`;
  renderServices(data.services);

  el.genGrid.innerHTML = "";
  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.className = "gen-cell" + (state.gen === "" ? " active" : "");
  allBtn.dataset.gen = "";
  allBtn.innerHTML =
    '<span class="gen-name">ALL</span><span class="gen-count">' +
    fmtInt(data.total) +
    "</span>";
  allBtn.addEventListener("click", () => setGen(""));
  el.genGrid.appendChild(allBtn);

  for (const { g, n } of data.generations) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "gen-cell" + (state.gen === g ? " active" : "");
    btn.dataset.gen = g;
    btn.innerHTML = `<span class="gen-name">${esc(genShort(g))}</span><span class="gen-count">${fmtInt(n)}</span>`;
    btn.addEventListener("click", () => setGen(g));
    el.genGrid.appendChild(btn);
  }
}

function setGen(g) {
  state.gen = g;
  state.page = 1;
  $$(".gen-cell").forEach((c) =>
    c.classList.toggle("active", c.dataset.gen === g)
  );
  search();
}

function setSegment(group, val) {
  state[group] = val;
  $$(`#seg-${group} .seg-btn`).forEach((b) =>
    b.classList.toggle("active", b.dataset.val === val)
  );
  state.page = 1;
  search();
}

function setView(v) {
  state.view = v;
  $$(".view-toggle button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === v)
  );
  state.page = 1;
  search();
}

function clearFilters() {
  el.q.value = "";
  state.gen = "";
  state.legal = "any";
  state.shiny = "any";
  state.sort = "recent";
  el.sort.value = "recent";
  setSegment("legal", "any");
  setSegment("shiny", "any");
  $$(".gen-cell").forEach((c) =>
    c.classList.toggle("active", c.dataset.gen === "")
  );
  state.page = 1;
  search();
}

async function search(skipHash) {
  el.results.innerHTML = '<div class="loading-pane">loading…</div>';
  updateChrome();
  try {
    const res = await fetch(`/api/pokemon?${apiParams()}`);
    const data = await res.json();
    state.list = data.pokemon || [];
    state.total = data.total;
    state.page = data.page;
    state.pages = data.pages;
    renderResults();
    updateChrome();
    if (state.selectedId && !state.list.some((p) => p.id === state.selectedId)) {
      if (state.list.length) select(state.list[0].id, false);
      else clearSelection();
    } else if (state.selectedId) {
      highlightRow(state.selectedId);
    }
    if (!skipHash) pushHash();
  } catch {
    el.results.innerHTML =
      '<div class="empty-state"><p class="empty-headline">search failed</p></div>';
  }
}

function renderResults() {
  if (!state.list.length) {
    el.results.innerHTML = `
      <div class="empty-state">
        <div class="empty-glyph"><span class="micon">search_off</span></div>
        <p class="empty-headline">no matches</p>
        <p class="empty-q mut">try clearing filters or broadening search</p>
      </div>`;
    return;
  }
  if (state.view === "grid") renderGrid();
  else renderList();
}

function spriteImg(p, slot) {
  return `<img src="${esc(p.sprite_url)}" alt=""
    class="sprite sprite--${slot}" data-static="${esc(p.sprite_url_static || "")}"
    onerror="spriteFallback(this)" loading="lazy" />`;
}

function renderGrid() {
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const p of state.list) {
    const card = document.createElement("button");
    card.type = "button";
    card.className =
      "card" +
      (p.id === state.selectedId ? " active" : "") +
      (!p.legal ? " card-illegal" : "");
    card.dataset.id = p.id;
    const gg = genderGlyph(p.gender, p.generation);
    const dlBadge = (p.download_count > 100)
      ? `<span class="dl-badge">${fmtInt(p.download_count)} dl</span>`
      : "";
    card.innerHTML = `
      <div class="card-head">
        <span class="card-id mono">#${p.id}</span>
        ${genBadge(p.generation)}
      </div>
      <div class="card-sprite-wrap">
        ${spriteImg(p, "card")}
      </div>
      <div class="card-body">
        <div class="card-title">${esc(displayName(p))}</div>
        ${hasNickname(p) ? `<div class="card-sub card-species">${esc(p.species_name)}</div>` : ""}
        <div class="card-meta mono">
          <span>Lv.${p.level}</span><span class="sep">·</span>
          <span style="color:${gg.c}">${gg.g}</span>
          ${dlBadge}
        </div>
      </div>
      <div class="card-foot">${pokemonTags(p)}</div>`;
    card.addEventListener("click", () => select(p.id));
    card.addEventListener("dblclick", () => openDetailPage(p.id));
    grid.appendChild(card);
  }
  el.results.innerHTML = "";
  el.results.appendChild(grid);
}

function renderList() {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "table mono";
  table.innerHTML = `
    <thead><tr>
      <th>id</th><th></th><th>name</th><th>#</th><th>gen</th>
      <th>lv</th><th>♂♀</th><th>ot</th><th>tid</th><th>nature</th>
      <th>legal</th><th>dl</th><th>code</th><th>date</th>
    </tr></thead><tbody></tbody>`;
  const tbody = table.querySelector("tbody");
  for (const p of state.list) {
    const tr = document.createElement("tr");
    tr.dataset.id = p.id;
    tr.className =
      (p.id === state.selectedId ? "row-active " : "") +
      (!p.legal ? "row-illegal" : "");
    const gg = genderGlyph(p.gender, p.generation);
    const sub = hasNickname(p)
      ? `<div class="t-name-sub">${esc(p.species_name)}</div>`
      : "";
    tr.innerHTML = `
      <td class="t-id">#${p.id}</td>
      <td class="t-sprite">${spriteImg(p, "list")}</td>
      <td>
        <div class="t-name-main">${esc(displayName(p))} ${typeBadges(p.types?.slice(0, 1))}${pokemonTags(p, { legal: false })}</div>
        ${sub}
      </td>
      <td class="t-num">${p.species_id}</td>
      <td class="t-gen">${genBadge(p.generation)}</td>
      <td class="t-lv">${p.level}</td>
      <td class="t-gender" style="color:${gg.c}">${gg.g}</td>
      <td class="t-ot">${esc(p.original_trainer || "—")}</td>
      <td class="t-tid mut">${p.tid}/${p.sid}</td>
      <td class="t-nature">${esc(p.nature || "—")}</td>
      <td class="t-legal">${pokemonTags(p, { shiny: false, egg: false })}</td>
      <td class="t-dl">${fmtInt(p.download_count)}</td>
      <td class="t-code">${esc(p.download_code)}</td>
      <td class="t-date mut">${fmtDate(p.upload_datetime)}</td>`;
    tr.addEventListener("click", () => select(p.id));
    tr.addEventListener("dblclick", () => openDetailPage(p.id));
    tbody.appendChild(tr);
  }
  wrap.appendChild(table);
  el.results.innerHTML = "";
  el.results.appendChild(wrap);
}

function highlightRow(id) {
  $$(".card, .table tbody tr").forEach((n) => {
    const active = Number(n.dataset.id) === id;
    n.classList.toggle("active", active);
    n.classList.toggle("row-active", active);
  });
}

function clearSelection() {
  state.selectedId = null;
  el.detail.classList.add("empty");
  if (isMobile) {
    el.detail.classList.remove("mobile-open");
  }
  el.detailEmpty.hidden = false;
  el.detailContent.hidden = true;
  el.detailContent.innerHTML = "";
  highlightRow(-1);
  document.title = "GPSS-in-a-Box";
}

async function select(id, fetchDetail = true) {
  state.selectedId = id;
  highlightRow(id);
  el.detail.classList.remove("empty");
  if (isMobile) {
    el.detail.classList.add("mobile-open");
  }
  el.detailEmpty.hidden = true;
  el.detailContent.hidden = false;
  el.detailContent.innerHTML =
    '<div class="lg-loading"><span class="lg-spinner"></span> loading detail…</div>';

  if (!fetchDetail) return;
  try {
    const res = await fetch(`/api/pokemon/${id}`);
    if (!res.ok) throw new Error("not found");
    const p = await res.json();
    renderDetail(p);
    loadLegality(id);
    document.title = `${p.species_name} #${id} — GPSS-in-a-Box`;
  } catch {
    el.detailContent.innerHTML =
      '<p class="empty-text">could not load pokémon</p>';
  }
}

function statBar(val, max = 31) {
  const segs = 8;
  const on = Math.round((val / max) * segs);
  let bars = "";
  for (let i = 0; i < segs; i++) {
    bars += `<span class="seg${i < on ? " on" : ""}"></span>`;
  }
  const cls =
    val === 31 ? " perfect" : val === 0 && max === 31 ? " zero" : "";
  return `<div class="stat-bar">${bars}</div>`;
}

function statBlock(stats, max, naturePlus, natureMinus) {
  return STAT_KEYS.map((k) => {
    const v = stats[k] ?? 0;
    let cls = v === 31 && max === 31 ? " perfect" : v === 0 && max === 31 ? " zero" : "";
    if (naturePlus === k) cls += " nature-boosted";
    if (natureMinus === k) cls += " nature-hindered";
    return `<div class="stat-row${cls}">
      <span class="stat-label">${STAT_LABELS[k]}</span>
      ${statBar(v, max)}
      <span class="stat-val mono">${v}</span>
    </div>`;
  }).join("");
}

function renderDetail(p) {
  const gg = genderGlyph(p.gender, p.generation);
  const moves = (p.moves || []).slice(0, 4);
  while (moves.length < 4) moves.push(null);

  const mobileBack = isMobile
    ? `<button type="button" class="btn mobile-back" id="mobile-back"><span class="micon">arrow_back</span> back to list</button>`
    : "";

  const typeColor = TYPE_COLORS[p.types?.[0]] || "transparent";
  const shinyStar = p.shiny ? '<span class="shiny-star micon">auto_awesome</span>' : '';
  const heroSpriteHtml = p.is_egg
    ? `<img src="${EGG_SPRITE}" alt="" class="sprite sprite--hero" loading="lazy" />`
    : spriteImg(p, "hero");
  const ballIcon = p.ball_sprite ? `<img src="${esc(p.ball_sprite)}" class="ball-icon" alt="" />` : "";

  el.detailContent.innerHTML = `${mobileBack}
    <div class="detail-bar">
      <span class="mut">#${p.id}</span>
      <button type="button" class="btn-icon icon-btn" id="detail-close" title="Close"><span class="micon">close</span></button>
    </div>
    <div class="detail-hero" style="--type-color: ${typeColor}">
      <div class="hero-sprite">
        ${heroSpriteHtml}
        ${shinyStar}
      </div>
      <div class="hero-info">
        <div class="hero-title">
          ${esc(displayName(p))}
          <span class="hero-gender" style="color:${gg.c}">${gg.g}</span>
        </div>
        <div class="hero-sub mut mono">
          ${esc(p.species_name)}${p.form_name ? ` (${esc(p.form_name)})` : ""} · #${p.species_id} · ${esc(genShort(p.generation))} · Lv.${p.level}
        </div>
        <div class="hero-types">${typeBadges(p.types)}</div>
        <div class="hero-flags">${pokemonTags(p)}</div>
      </div>
    </div>

    <section class="section section-legality">
      <div class="section-head section-head-row">
        <span>legality</span>
        <span class="engine-pill off" id="engine-pill"><span class="dot dot-off"></span> pkhex</span>
      </div>
      <div class="section-body" id="legality-panel">
        <div class="lg-loading"><span class="lg-spinner"></span> checking with PKHeX…</div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">trainer &amp; origin</div>
      <div class="section-body">
        <div class="chip-row">
          <div class="chip"><span class="chip-k">ot</span><span class="chip-v">${esc(p.original_trainer || "—")}</span></div>
          <div class="chip"><span class="chip-k">tid / sid</span><span class="chip-v mono">${p.tid} / ${p.sid}</span></div>
          <div class="chip"><span class="chip-k">met lv</span><span class="chip-v">${p.met_level}</span></div>
        </div>
        <div class="kv"><span class="kv-k">ball</span><span class="kv-v mono">${ballIcon}${esc(p.ball_name || `#${p.ball_id}`)}</span></div>
        <div class="kv"><span class="kv-k">language</span><span class="kv-v mono">${esc(p.language_name || String(p.language))}</span></div>
        <div class="kv"><span class="kv-k">nature</span><span class="kv-v">${esc(p.nature || "—")}${natureModifiers(p)}</span></div>
        <div class="kv"><span class="kv-k">ability</span><span class="kv-v">${esc(p.ability || "—")}</span></div>
        <div class="kv"><span class="kv-k">held</span><span class="kv-v">${p.held_item_sprite ? `<img src="${esc(p.held_item_sprite)}" class="item-icon" alt="" />` : ""}${esc(p.held_item || "—")}</span></div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">moves</div>
      <div class="moves">
        ${moves
          .map(
            (m, i) =>
              `<div class="move-slot${m ? "" : " empty"}">
            <span class="move-idx mono">${i + 1}</span>
            <span class="move-name">${m ? esc(m) : "—"}</span>
          </div>`
          )
          .join("")}
      </div>
    </section>

    <section class="section">
      <div class="section-head">ivs</div>
      <div class="section-body stat-block">${statBlock(p.ivs, 31, p.nature_plus, p.nature_minus)}</div>
    </section>

    <section class="section">
      <div class="section-head">evs</div>
      <div class="section-body stat-block">${statBlock(p.evs || {}, 252, p.nature_plus, p.nature_minus)}</div>
    </section>

    ${p.base_stats ? `<section class="section">
      <div class="section-head">base stats</div>
      <div class="section-body stat-block">${statBlock(p.base_stats, 255)}</div>
    </section>` : ""}

    <section class="section">
      <div class="section-head">database</div>
      <div class="section-body">
        <div class="kv"><span class="kv-k">downloads</span><span class="kv-v mono">${fmtInt(p.download_count)}</span></div>
        <div class="kv"><span class="kv-k">uploaded</span><span class="kv-v mono">${esc(fmtDate(p.upload_datetime))}</span></div>
        <div class="kv"><span class="kv-k">layout</span><span class="kv-v mono">${esc(p.parse_layout || "—")}</span></div>
        <div class="kv"><span class="kv-k">pid</span><span class="kv-v mono">${esc(p.pid)}</span></div>
        <div class="kv"><span class="kv-k">code</span><span class="kv-v mono hl">${esc(p.download_code)}</span></div>
      </div>
    </section>

    <div class="detail-footer">
      <div class="btn-row">
        <button type="button" class="btn btn-action" id="copy-paste"><span class="micon">content_copy</span> showdown set</button>
        <a href="/api/pokemon/${p.id}/download" class="btn btn-action" download><span class="micon">download</span> .pkm</a>
      </div>
    </div>`;

  $("#detail-close").addEventListener("click", clearSelection);
  if (isMobile) {
    const backBtn = document.getElementById("mobile-back");
    if (backBtn) backBtn.addEventListener("click", () => {
      el.detail.classList.remove("mobile-open");
    });
  }
  const copyBtn = $("#copy-paste");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = p.showdown_paste || "";
      if (!text) {
        flashCopyButton(copyBtn, false, "no export data");
        return;
      }
      const ok = await copyToClipboard(text);
      flashCopyButton(copyBtn, ok, ok ? "copied!" : "copy failed");
    });
  }
}

async function copyToClipboard(text) {
  if (!text) return false;
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      /* fall through — common on http:// LAN */
    }
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText =
      "position:fixed;left:-9999px;top:0;opacity:0;width:1px;height:1px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

function flashCopyButton(btn, ok, label) {
  if (!btn) return;
  clearTimeout(btn._copyFlashTimer);
  if (!btn.dataset.defaultHtml) btn.dataset.defaultHtml = btn.innerHTML;
  const icon = ok ? "check" : "error";
  btn.innerHTML = `<span class="micon">${icon}</span> ${esc(label)}`;
  btn.classList.toggle("copied", ok);
  btn.classList.toggle("copy-err", !ok);
  btn._copyFlashTimer = setTimeout(() => {
    btn.innerHTML = btn.dataset.defaultHtml;
    btn.classList.remove("copied", "copy-err");
  }, 2000);
}

async function loadLegality(id, panelSel, pillSel) {
  const panel = $(panelSel || "#legality-panel");
  const pill = $(pillSel || "#engine-pill");
  if (!panel) return;
  try {
    const res = await fetch(`/api/pokemon/${id}/legality`);
    const data = await res.json();
    if (pill) {
      pill.classList.toggle("on", res.ok && data.live);
      pill.classList.toggle("off", !(res.ok && data.live));
    }
    panel.innerHTML = renderLegality(data, res.ok);
    state.legalityCache.set(id, data);
  } catch {
    panel.innerHTML =
      '<p class="lg-note"><span class="lg-note-icon micon">warning</span> could not reach legality service.</p>';
  }
}

function legalitySeverity(line) {
  const l = line.toLowerCase();
  if (l.startsWith("fatal") || l.includes("fatal:")) return "fatal";
  if (l.startsWith("invalid") || l.includes("invalid:")) return "invalid";
  if (l.includes("warning") || l.includes("suspicious")) return "warning";
  return "info";
}

function renderLegality(data, ok) {
  if (!ok) {
    return `<p class="lg-note"><span class="lg-note-icon micon">error</span> ${esc(data.error || "Legality check failed")}</p>`;
  }
  const legal = data.legal;
  const live = data.live;
  const dbLegal = data.legal_db;
  const lines = (data.report || []).filter(
    (line) => line && line !== "Legal!" && (!data.message || line !== data.message)
  );

  let html = '<div class="lg-body"><div class="lg-badges tags">';
  html += tag(legal ? "legal" : "illegal");
  html += tag(live ? "pkhex" : "db", live ? "pkhex live" : "database");
  if (live && lines.length) {
    html += `<span class="lg-meta mut mono">${lines.length} issue${lines.length === 1 ? "" : "s"}</span>`;
  }
  html += "</div>";

  if (live && dbLegal !== legal) {
    html += lgBanner("drift", `database ${dbLegal ? "legal" : "illegal"} · pkhex ${legal ? "legal" : "illegal"}`);
  }
  if (data.gen12_note) {
    html += lgBanner("info", data.gen12_note);
  }
  if (data.message) {
    html += lgBanner("info", data.message);
  }
  if (lines.length) {
    html += '<ul class="lg-report">';
    for (const line of lines) {
      const sev = legalitySeverity(line);
      html += `<li class="lg-line lg-${sev}"><span class="lg-sev">${sev}</span><span class="lg-text">${esc(line)}</span></li>`;
    }
    html += "</ul>";
  } else if (live && legal) {
    html += '<p class="lg-empty"><span class="hl micon">check_circle</span> no issues reported by PKHeX</p>';
  }
  html += "</div>";
  return html;
}


function spriteFallback(img) {
  const step = img.dataset.fallback || "0";
  if (step === "0") {
    img.dataset.fallback = "1";
    const staticSrc = img.dataset.static;
    if (staticSrc) { img.src = staticSrc; return; }
  }
  img.src = FALLBACK_SPRITE;
}

function navigateList(delta) {
  if (!state.list.length) return;
  let idx = state.list.findIndex((p) => p.id === state.selectedId);
  if (idx < 0) idx = delta > 0 ? -1 : 0;
  idx = Math.max(0, Math.min(state.list.length - 1, idx + delta));
  select(state.list[idx].id);
}

async function openDetailPage(id) {
  state.focusedId = id;
  state.selectedId = id;
  document.querySelector(".body").style.display = "none";
  document.querySelector(".statusbar")?.classList.add("page-active");
  el.page.classList.add("open");
  el.page.innerHTML = '<div class="loading-pane">loading…</div>';
  pushHash();
  try {
    const res = await fetch(`/api/pokemon/${id}`);
    if (!res.ok) throw new Error("not found");
    const p = await res.json();
    renderDetailPage(p);
    loadLegality(id, "#page-legality-panel", "#page-engine-pill");
    document.title = `${p.species_name} #${id} — GPSS-in-a-Box`;
  } catch {
    el.page.innerHTML = '<div class="empty-state"><p class="empty-headline">could not load pokémon</p></div>';
  }
}

function closeDetailPage(skipHash) {
  state.focusedId = null;
  el.page.classList.remove("open");
  el.page.innerHTML = "";
  document.querySelector(".body").style.display = "";
  document.querySelector(".statusbar")?.classList.remove("page-active");
  document.title = "GPSS-in-a-Box";
  if (!skipHash) pushHash();
}

function navigateDetailPage(delta) {
  if (!state.list.length) return;
  let idx = state.list.findIndex((p) => p.id === state.focusedId);
  if (idx < 0) return;
  const next = idx + delta;
  if (next < 0 || next >= state.list.length) return;
  openDetailPage(state.list[next].id);
}

function renderDetailPage(p) {
  const gg = genderGlyph(p.gender, p.generation);
  const typeColor = TYPE_COLORS[p.types?.[0]] || "transparent";
  const typeColor2 = TYPE_COLORS[p.types?.[1]] || typeColor;
  const moves = (p.moves || []).slice(0, 4);
  while (moves.length < 4) moves.push(null);

  const idx = state.list.findIndex((x) => x.id === p.id);
  const total = state.list.length;
  const posLabel = idx >= 0 ? `${idx + 1} / ${total}` : "";
  const hasPrev = idx > 0;
  const hasNext = idx >= 0 && idx < total - 1;

  const crumbGen = p.generation ? `<span class="bsep">›</span><span>gen ${esc(String(p.generation))}</span>` : "";

  const shinyStar = p.shiny ? '<span class="page-hero-star micon">auto_awesome</span>' : '';
  const eggBadge = p.is_egg ? '<span class="page-hero-egg micon">egg_alt</span>' : '';

  const heroSpriteHtml = p.is_egg
    ? `<img src="${EGG_SPRITE}" alt="" class="sprite sprite--page" loading="lazy" />`
    : spriteImg(p, "page");

  const ballIcon = p.ball_sprite ? `<img src="${esc(p.ball_sprite)}" class="ball-icon" alt="" />` : "";
  const heldIcon = p.held_item_sprite ? `<img src="${esc(p.held_item_sprite)}" class="item-icon" alt="" />` : "";

  el.page.innerHTML = `
    <div class="page-toolbar">
      <button type="button" class="btn page-back" id="page-back">
        <span class="micon">arrow_back</span> back to results
      </button>
      <div class="page-crumbs">
        <span>browse</span>${crumbGen}
        <span class="bsep">›</span><span class="hl">#${p.id}</span>
      </div>
      <div class="page-nav">
        <button type="button" class="btn page-nav-btn" id="page-prev" ${hasPrev ? "" : "disabled"}>
          <span class="micon">chevron_left</span> prev
        </button>
        <span class="page-nav-pos mono">${esc(posLabel)}</span>
        <button type="button" class="btn page-nav-btn" id="page-next" ${hasNext ? "" : "disabled"}>
          next <span class="micon">chevron_right</span>
        </button>
      </div>
    </div>

    <div class="page-body">
      <div class="page-hero" style="--type-color: ${typeColor}; --type-color2: ${typeColor2}">
        <div class="page-hero-sprite">
          ${heroSpriteHtml}
          ${shinyStar}
          ${eggBadge}
        </div>
        <div class="page-hero-info">
          <div class="page-hero-id mono mut">#${String(p.species_id).padStart(4, "0")}</div>
          <div class="page-hero-title">
            ${esc(displayName(p))}
            <span class="page-hero-gender" style="color:${gg.c}">${gg.g}</span>
          </div>
          ${hasNickname(p) ? `<div class="page-hero-species mut">${esc(p.species_name)}${p.form_name ? ` (${esc(p.form_name)})` : ""}</div>` : (p.form_name ? `<div class="page-hero-species mut">${esc(p.form_name)}</div>` : "")}
          <div class="page-hero-stats mono">
            <span>Lv.${p.level}</span>
            <span class="sep">·</span><span>${esc(p.nature || "—")}${natureModifiers(p)}</span>
            <span class="sep">·</span><span>${esc(p.ability || "—")}</span>
            ${p.held_item ? `<span class="sep">·</span><span>${heldIcon}${esc(p.held_item)}</span>` : ""}
            ${p.ball_name ? `<span class="sep">·</span><span>${ballIcon}${esc(p.ball_name)}</span>` : ""}
          </div>
          <div class="page-hero-flags">
            ${pokemonTags(p)}
            ${genBadge(p.generation)}
            ${typeBadges(p.types)}
          </div>
        </div>
        <div class="page-hero-side">
          <div class="phs-row"><span class="phs-k">CODE</span><span class="phs-v mono hl">${esc(p.download_code)}</span></div>
          <div class="phs-row"><span class="phs-k">DOWNLOADS</span><span class="phs-v mono">${fmtInt(p.download_count)}</span></div>
          <div class="phs-row"><span class="phs-k">UPLOADED</span><span class="phs-v mono">${esc(fmtDate(p.upload_datetime))}</span></div>
          <div class="phs-row"><span class="phs-k">MET LV</span><span class="phs-v mono">${p.met_level}</span></div>
          <div class="phs-row"><span class="phs-k">LANG</span><span class="phs-v mono">${esc(p.language_name || String(p.language))}</span></div>
        </div>
      </div>

      <div class="page-grid">
        <div class="page-col">
          <section class="section">
            <div class="section-head section-head-row">
              <span>legality</span>
              <span class="engine-pill off" id="page-engine-pill"><span class="dot dot-off"></span> pkhex</span>
            </div>
            <div class="section-body" id="page-legality-panel">
              <div class="lg-loading"><span class="lg-spinner"></span> checking with PKHeX…</div>
            </div>
          </section>

          <section class="section">
            <div class="section-head">moves</div>
            <div class="moves">
              ${moves.map((m, i) => `<div class="move-slot${m ? "" : " empty"}">
                <span class="move-idx mono">${i + 1}</span>
                <span class="move-name">${m ? esc(m) : "—"}</span>
              </div>`).join("")}
            </div>
          </section>

          <section class="section">
            <div class="section-head">ivs</div>
            <div class="section-body stat-block">${statBlock(p.ivs, 31, p.nature_plus, p.nature_minus)}</div>
          </section>

          <section class="section">
            <div class="section-head">evs</div>
            <div class="section-body stat-block">${statBlock(p.evs || {}, 252, p.nature_plus, p.nature_minus)}</div>
          </section>

          ${p.base_stats ? `<section class="section">
            <div class="section-head">base stats</div>
            <div class="section-body stat-block">${statBlock(p.base_stats, 255)}</div>
          </section>` : ""}
        </div>

        <div class="page-col">
          <section class="section">
            <div class="section-head">trainer &amp; origin</div>
            <div class="section-body">
              <div class="chip-row">
                <div class="chip"><span class="chip-k">ot</span><span class="chip-v">${esc(p.original_trainer || "—")}</span></div>
                <div class="chip"><span class="chip-k">tid / sid</span><span class="chip-v mono">${p.tid} / ${p.sid}</span></div>
              </div>
              <div class="kv"><span class="kv-k">ball</span><span class="kv-v mono">${ballIcon}${esc(p.ball_name || `#${p.ball_id}`)}</span></div>
              <div class="kv"><span class="kv-k">language</span><span class="kv-v mono">${esc(p.language_name || String(p.language))}</span></div>
              <div class="kv"><span class="kv-k">nature</span><span class="kv-v">${esc(p.nature || "—")}${natureModifiers(p)}</span></div>
              <div class="kv"><span class="kv-k">ability</span><span class="kv-v">${esc(p.ability || "—")}</span></div>
              <div class="kv"><span class="kv-k">held item</span><span class="kv-v">${heldIcon}${esc(p.held_item || "—")}</span></div>
            </div>
          </section>

          <section class="section">
            <div class="section-head">database</div>
            <div class="section-body">
              <div class="kv"><span class="kv-k">db id</span><span class="kv-v mono">${p.id}</span></div>
              <div class="kv"><span class="kv-k">layout</span><span class="kv-v mono">${esc(p.parse_layout || "—")}</span></div>
              <div class="kv"><span class="kv-k">pid</span><span class="kv-v mono">${esc(p.pid)}</span></div>
              <div class="kv"><span class="kv-k">code</span><span class="kv-v mono hl">${esc(p.download_code)}</span></div>
            </div>
          </section>

          <div class="btn-row page-actions">
            <button type="button" class="btn btn-action" id="page-copy-paste"><span class="micon">content_copy</span> showdown set</button>
            <a href="/api/pokemon/${p.id}/download" class="btn btn-action" download><span class="micon">download</span> .pkm</a>
          </div>
        </div>
      </div>

      <section class="page-others" id="page-others"></section>
    </div>`;

  $("#page-back").addEventListener("click", () => closeDetailPage());
  $("#page-prev")?.addEventListener("click", () => navigateDetailPage(-1));
  $("#page-next")?.addEventListener("click", () => navigateDetailPage(1));

  const copyBtn = $("#page-copy-paste");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = p.showdown_paste || "";
      if (!text) { flashCopyButton(copyBtn, false, "no export data"); return; }
      const ok = await copyToClipboard(text);
      flashCopyButton(copyBtn, ok, ok ? "copied!" : "copy failed");
    });
  }

  loadOthers(p.id, p.species_id, p.species_name);
}

async function loadOthers(currentId, speciesId, speciesName) {
  const container = $("#page-others");
  if (!container) return;
  try {
    const res = await fetch(`/api/pokemon?species=${speciesId}&limit=7&sort=dl`);
    const data = await res.json();
    const others = (data.pokemon || []).filter((p) => p.id !== currentId).slice(0, 6);
    if (!others.length) { container.remove(); return; }
    container.innerHTML = `
      <div class="section-head">other ${esc(speciesName)} <span class="mut">(${data.total})</span></div>
      <div class="others-grid">
        ${others.map((p) => {
          const gg = genderGlyph(p.gender, p.generation);
          return `<button type="button" class="others-card" data-id="${p.id}">
            ${spriteImg(p, "others")}
            <div class="others-info">
              <span class="others-name">${esc(displayName(p))}</span>
              <span class="others-meta mono">Lv.${p.level} <span style="color:${gg.c}">${gg.g}</span></span>
              <span class="others-meta mono">${esc(p.original_trainer || "—")}</span>
            </div>
            <div class="others-tags">${pokemonTags(p)}</div>
          </button>`;
        }).join("")}
      </div>`;
    container.querySelectorAll(".others-card").forEach((card) => {
      card.addEventListener("click", () => openDetailPage(parseInt(card.dataset.id, 10)));
    });
  } catch {}
}

function bindEvents() {
  $$("#seg-legal .seg-btn").forEach((b) => {
    b.addEventListener("click", () => setSegment("legal", b.dataset.val));
  });
  $$("#seg-shiny .seg-btn").forEach((b) => {
    b.addEventListener("click", () => setSegment("shiny", b.dataset.val));
  });
  el.sort.addEventListener("change", () => {
    state.sort = el.sort.value;
    state.page = 1;
    search();
  });
  el.resetFilters.addEventListener("click", clearFilters);
  $$(".view-toggle button").forEach((b) => {
    b.addEventListener("click", () => setView(b.dataset.view));
  });
  el.prev.addEventListener("click", () => {
    if (state.page > 1) {
      state.page--;
      search();
    }
  });
  el.next.addEventListener("click", () => {
    if (state.page < state.pages) {
      state.page++;
      search();
    }
  });
  el.pageJump.addEventListener("change", () => {
    const n = parseInt(el.pageJump.value, 10);
    if (n >= 1 && n <= state.pages) {
      state.page = n;
      search();
    }
  });
  let debounce;
  el.q.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.page = 1;
      search();
    }, 300);
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) {
      if (e.key === "Escape") {
        e.target.blur();
        clearSelection();
      }
      return;
    }
    if (state.focusedId) {
      if (e.key === "Escape") { closeDetailPage(); return; }
      if (e.key === "ArrowLeft") { e.preventDefault(); navigateDetailPage(-1); return; }
      if (e.key === "ArrowRight") { e.preventDefault(); navigateDetailPage(1); return; }
      return;
    }
    if (e.key === "/") {
      e.preventDefault();
      el.q.focus();
      el.q.select();
    } else if (e.key === "g" || e.key === "G") {
      setView("grid");
    } else if (e.key === "l" || e.key === "L") {
      setView("list");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      navigateList(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      navigateList(-1);
    } else if (e.key === "Enter" && state.selectedId) {
      e.preventDefault();
      openDetailPage(state.selectedId);
    } else if (e.key === "Escape") {
      clearSelection();
    }
  });
}

window.spriteFallback = spriteFallback;

let _lastGridLimit = 0;
let _resizeDebounce;
window.addEventListener("resize", () => {
  clearTimeout(_resizeDebounce);
  _resizeDebounce = setTimeout(() => {
    if (state.view !== "grid") return;
    const lim = pageLimit();
    if (lim !== _lastGridLimit) {
      _lastGridLimit = lim;
      search();
    }
  }, 250);
});

async function checkUpdates() {
  try {
    const res = await fetch("/api/updates");
    const data = await res.json();
    if (data.update_available) {
      showUpdateBanner(data.current_version, data.latest_version);
    }
  } catch {}
}

function showUpdateBanner(current, latest) {
  const banner = document.createElement("div");
  banner.className = "update-banner";
  banner.innerHTML = `
    <span>Engine update available: ${esc(current)} → <strong>${esc(latest)}</strong></span>
    <span class="update-cmd">Run <code>./setup.sh</code> to update</span>
    <button type="button" class="btn-icon update-dismiss"><span class="micon">close</span></button>
  `;
  banner.querySelector(".update-dismiss").addEventListener("click", () => banner.remove());
  document.querySelector(".app").prepend(banner);
}

async function showStatusModal() {
  if (document.querySelector(".status-modal-overlay")) return;
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const modal = document.createElement("div");
    modal.className = "status-modal-overlay";
    modal.innerHTML = `
      <div class="status-modal">
        <div class="status-modal-head">
          <span>Server Status</span>
          <button type="button" class="btn-icon status-modal-close"><span class="micon">close</span></button>
        </div>
        <div class="status-modal-body">
          <div class="kv"><span class="kv-k">engine</span><span class="kv-v mono">${esc(data.engine_version)}</span></div>
          <div class="kv"><span class="kv-k">database</span><span class="kv-v mono">${esc(data.db_size_human)} · ${fmtInt(data.total_pokemon)} Pokémon</span></div>
          <div class="kv"><span class="kv-k">gpss</span><span class="kv-v">${data.services?.gpss?.online ? "connected" : "offline"}</span></div>
          <div class="kv"><span class="kv-k">legality</span><span class="kv-v">${data.services?.legality?.mode || "unavailable"}</span></div>
        </div>
      </div>
    `;
    modal.querySelector(".status-modal-close").addEventListener("click", () => modal.remove());
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
    document.body.appendChild(modal);
  } catch {}
}

const statusBtn = $("#status-info");
if (statusBtn) statusBtn.addEventListener("click", showStatusModal);

function pushHash() {
  const h = stateToHash();
  if ("#" + h !== location.hash) history.pushState(null, "", "#" + h);
}

function stateToHash() {
  if (state.focusedId) return `pokemon/${state.focusedId}`;
  const p = new URLSearchParams();
  const q = el.q.value.trim();
  if (q) p.set("q", q);
  if (state.gen) p.set("gen", state.gen);
  if (state.legal !== "any") p.set("legal", state.legal);
  if (state.shiny !== "any") p.set("shiny", state.shiny);
  if (state.sort !== "recent") p.set("sort", state.sort);
  if (state.page > 1) p.set("p", String(state.page));
  const s = p.toString();
  return s || "";
}

function applyHash() {
  const raw = location.hash.replace(/^#/, "");
  const pokemonMatch = raw.match(/^pokemon\/(\d+)$/);
  if (pokemonMatch) {
    openDetailPage(parseInt(pokemonMatch[1], 10));
    return;
  }
  if (state.focusedId) closeDetailPage(true);
  const p = new URLSearchParams(raw);
  el.q.value = p.get("q") || "";
  state.gen = p.get("gen") || "";
  state.legal = p.get("legal") || "any";
  state.shiny = p.get("shiny") || "any";
  state.sort = p.get("sort") || "recent";
  state.page = parseInt(p.get("p"), 10) || 1;
  el.sort.value = state.sort;
  setSegment("legal", state.legal);
  setSegment("shiny", state.shiny);
  $$(".gen-cell").forEach((c) =>
    c.classList.toggle("active", c.dataset.gen === state.gen)
  );
  state.selectedId = null;
  search(true);
}

window.addEventListener("popstate", applyHash);

bindEvents();
loadStats().then(() => {
  if (location.hash && location.hash !== "#") applyHash();
  else search();
  checkUpdates();
});
