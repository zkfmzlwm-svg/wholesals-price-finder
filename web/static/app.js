"use strict";
// 도매 최저가 비교 — 웹 UI (데스크탑 App 클래스의 탭/동작을 그대로 옮김)

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const won = (n) => "₩" + Number(n).toLocaleString("ko-KR");

const S = {
  info: null,
  sites: [], favorites: [], settings: {},
  allProducts: [], lastQuery: "", lastErrors: [],
  rows: [],            // 현재 표시 중인 [{rank, idx, p}] (컬럼 정렬 반영)
  sortCol: null, sortAsc: true,
  selSite: null, selFav: null,
  ctx: { idx: -1, cell: "" },
};

// ═══════════ API ═══════════
async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  if (r.status === 401 && path !== "/api/auth") {
    await askPassword();
    return api(method, path, body);
  }
  let data = {};
  try { data = await r.json(); } catch { /* 빈 응답 */ }
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

function askPassword() {
  const dlg = $("#auth-dlg"), form = $("#auth-form");
  return new Promise((resolve) => {
    $("#auth-err").textContent = "";
    form.password.value = "";
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("POST", "/api/auth", { password: form.password.value });
        dlg.close(); resolve();
      } catch (err) { $("#auth-err").textContent = err.message; }
    };
    dlg.addEventListener("cancel", (e) => e.preventDefault(), { once: true });
    dlg.showModal();
    form.password.focus();
  });
}

// ═══════════ 공통 UI ═══════════
function msg(title, body, { confirm = false, html = false } = {}) {
  const dlg = $("#msg-dlg");
  $("#msg-title").textContent = title;
  $("#msg-body")[html ? "innerHTML" : "textContent"] = body;
  $("#msg-cancel").hidden = !confirm;
  return new Promise((resolve) => {
    dlg.onclose = () => resolve(dlg.returnValue === "ok");
    dlg.returnValue = "";
    dlg.showModal();
    $("#msg-ok").focus();
  });
}
const confirmBox = (title, body) => msg(title, body, { confirm: true });

let toastTimer;
function toast(text) {
  const t = $("#toast");
  t.textContent = text; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
  toast("📋 복사됨: " + (text.length > 40 ? text.slice(0, 40) + "…" : text));
}

function openUrl(url) {
  if (url && url.startsWith("http")) window.open(url, "_blank", "noopener");
}

function selectRow(tbody, tr) {
  $$("tr.sel", tbody).forEach((r) => r.classList.remove("sel"));
  tr?.classList.add("sel");
}

// ═══════════ 탭 ═══════════
$$(".tab").forEach((b) => b.addEventListener("click", () => {
  $$(".tab").forEach((x) => x.classList.toggle("active", x === b));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
  if (b.dataset.tab === "settings") loadDebug();
}));

// ═══════════ 상태 불러오기 ═══════════
async function loadState() {
  const st = await api("GET", "/api/state");
  S.sites = st.sites; S.favorites = st.favorites; S.settings = st.settings || {};
  renderSites(); renderFavorites();
}

// ═══════════ 검색 ═══════════
$("#search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("#q").value.trim();
  if (!query) return msg("알림", "검색어를 입력하세요");
  const active = S.sites.filter((s) => s.enabled);
  if (!active.length) return msg("알림", "활성 사이트가 없습니다.\n'사이트 관리' 탭에서 사이트를 추가하세요.");

  const btn = $("#search-btn");
  btn.disabled = true;
  $("#status").innerHTML = `<span class="spin"></span>🔍 '${esc(query)}' 검색 중... (${active.length}개 사이트)`;
  $("#site-status").textContent = "";
  $("#errors").hidden = true;
  $("#summary").innerHTML = "";
  $("#result-table tbody").innerHTML = "";
  try {
    const res = await api("POST", "/api/search", { query });
    showResults(res.results, res.query);
  } catch (err) {
    $("#status").textContent = "⚠ 검색 실패: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

function showResults(results, query) {
  S.allProducts = [];
  const errors = [], summary = [];
  for (const r of results) {
    if (r.error) {
      errors.push(`${r.site_name}: ${r.error}`);
      summary.push(`<span class="err" title="${esc(r.error)}">${esc(r.site_name)}:오류⚠</span>`);
    } else if (!r.products.length) {
      summary.push(`<span class="warn">${esc(r.site_name)}:0건⚠</span>`);
    } else {
      S.allProducts.push(...r.products);
      summary.push(`${esc(r.site_name)}:${r.products.length}건`);
    }
  }
  $("#site-status").innerHTML = "사이트별 결과&nbsp; " + summary.join(" &nbsp;·&nbsp; ");
  sortAllProducts();
  S.lastQuery = query;
  S.lastErrors = errors;
  renderProducts();
}

function sortAllProducts() {
  const key = $("input[name=sort]:checked").value;
  if (key === "name") S.allProducts.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  else S.allProducts.sort((a, b) => (a.price > 0 ? a.price : 999999999) - (b.price > 0 ? b.price : 999999999));
}

$$("input[name=sort]").forEach((r) => r.addEventListener("change", () => {
  if (!S.lastQuery) return;
  sortAllProducts(); renderProducts();
}));

$("#hide-soldout").addEventListener("change", async (e) => {
  S.settings.hide_soldout = e.target.checked;
  try { await api("PUT", "/api/settings", { hide_soldout: e.target.checked }); } catch (err) { toast("⚠ " + err.message); }
  if (S.lastQuery) renderProducts();
});

const cellText = (p, col, rank) => ({
  rank: String(rank),
  site: p.site_name,
  name: p.name,
  price: p.price > 0 ? won(p.price) : "가격문의",
  unit_price: p.unit_price || "-",
  maker: p.maker || "",
  stock: p.in_stock ? "✓" : "품절",
}[col]);
const COLS = ["rank", "site", "name", "price", "unit_price", "maker", "stock"];

function renderProducts() {
  const hide = $("#hide-soldout").checked;
  // idx는 allProducts 인덱스 — 더블클릭/우클릭/즐겨찾기가 맞는 상품을 가리키도록 유지
  const visible = S.allProducts.map((p, idx) => ({ idx, p })).filter(({ p }) => !hide || p.in_stock);
  const hiddenCnt = S.allProducts.length - visible.length;
  S.rows = visible.map((v, i) => ({ rank: i + 1, ...v }));

  // 요약 카드
  const priced = visible.map((v) => v.p).filter((p) => p.price > 0);
  let cards = "";
  if (visible.length) {
    const low = priced.length ? priced.reduce((a, b) => (b.price < a.price ? b : a)) : null;
    cards = [
      ["총 검색 결과", `${visible.length}개`, "var(--text)"],
      ["최저가", low ? won(low.price) : "-", "var(--green)"],
      ["최저가 사이트", low ? low.site_name : "-", "var(--yellow)"],
      ["최저가 상품", low ? low.name.slice(0, 20) : "-", "var(--text)"],
    ].map(([t, v, c]) => `<div class="card"><div class="t">${t}</div><div class="v" style="color:${c}" title="${esc(v)}">${esc(v)}</div></div>`).join("");
  }
  $("#summary").innerHTML = cards;

  S.sortCol = null;
  drawRows();

  const errTxt = S.lastErrors.length ? `  |  ⚠ 오류 ${S.lastErrors.length}개 사이트` : "";
  const hiddenTxt = hiddenCnt ? ` (품절 ${hiddenCnt}개 숨김)` : "";
  $("#status").textContent = `✓ '${S.lastQuery}' 검색 완료 — ${visible.length}개 결과${hiddenTxt}${errTxt}`;
  // 오류 상세는 접어서 표시 (사이트가 많으면 상태 줄이 너무 길어짐)
  const det = $("#errors");
  det.hidden = !S.lastErrors.length;
  $("summary", det).textContent = `⚠ 오류 상세 (${S.lastErrors.length})`;
  $("ul", det).innerHTML = S.lastErrors.map((e) => `<li>${esc(e)}</li>`).join("");
}

function drawRows() {
  const tbody = $("#result-table tbody");
  if (!S.rows.length) {
    tbody.innerHTML = S.lastQuery ? `<tr><td colspan="8" class="empty">검색 결과가 없습니다</td></tr>` : "";
  } else {
    tbody.innerHTML = S.rows.map(({ rank, idx, p }) => `
      <tr data-idx="${idx}">
        <td class="c">${rank}</td>
        <td class="nowrap">${esc(p.site_name)}</td>
        <td class="name">${esc(p.name)}</td>
        <td class="r">${esc(cellText(p, "price"))}</td>
        <td>${esc(cellText(p, "unit_price"))}</td>
        <td>${esc(p.maker || "")}</td>
        <td class="c ${p.in_stock ? "instock" : "soldout"}">${p.in_stock ? "✓" : "품절"}</td>
        <td class="c act"><button class="btn flat mini more" title="메뉴">⋯</button></td>
      </tr>`).join("");
  }
  // 헤딩 ▲/▼
  $$("#result-table th[data-col]").forEach((th) => {
    const base = th.dataset.base ?? (th.dataset.base = th.textContent);
    th.textContent = base + (th.dataset.col === S.sortCol ? (S.sortAsc ? " ▲" : " ▼") : "");
  });
}

// 컬럼 클릭 → 오름차순/내림차순 토글 정렬
$$("#result-table th[data-col]").forEach((th) => th.addEventListener("click", () => {
  if (!S.rows.length) return;
  const col = th.dataset.col;
  if (S.sortCol === col) S.sortAsc = !S.sortAsc;
  else { S.sortCol = col; S.sortAsc = true; }
  const dir = S.sortAsc ? 1 : -1;
  if (col === "rank" || col === "price") {
    const num = (r) => {
      const d = cellText(r.p, col, r.rank).replace(/[^\d]/g, "");
      return d ? parseInt(d, 10) : (S.sortAsc ? 999999999 : -1);
    };
    S.rows.sort((a, b) => (num(a) - num(b)) * dir);
  } else {
    const txt = (r) => cellText(r.p, col, r.rank).toLowerCase();
    S.rows.sort((a, b) => txt(a).localeCompare(txt(b), "ko") * dir);
  }
  drawRows();
}));

const resultBody = $("#result-table tbody");
resultBody.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (!tr) return;
  selectRow(resultBody, tr);
  if (e.target.closest(".more")) {
    const r = e.target.closest(".more").getBoundingClientRect();
    showCtx(+tr.dataset.idx, S.allProducts[+tr.dataset.idx].name, r.left, r.bottom);
  }
});
resultBody.addEventListener("dblclick", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (tr && !e.target.closest(".more")) openUrl(S.allProducts[+tr.dataset.idx].open_url);
});
resultBody.addEventListener("contextmenu", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  const td = e.target.closest("td");
  if (!tr || !td) return;
  e.preventDefault();
  selectRow(resultBody, tr);
  const ci = [...tr.children].indexOf(td);
  const idx = +tr.dataset.idx;
  const row = S.rows.find((r) => r.idx === idx);
  const cell = ci < COLS.length ? cellText(row.p, COLS[ci], row.rank) : row.p.name;
  showCtx(idx, cell, e.clientX, e.clientY);
});

// ═══════════ 우클릭 메뉴 ═══════════
function showCtx(idx, cell, x, y) {
  S.ctx = { idx, cell };
  const preview = cell.length > 28 ? cell.slice(0, 28) + "…" : cell;
  $("#ctx-copy").textContent = `📋  복사:  ${preview}`;
  const m = $("#ctx");
  m.hidden = false;
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = Math.max(4, Math.min(x, innerWidth - w - 4)) + "px";
  m.style.top = Math.max(4, Math.min(y, innerHeight - h - 4)) + "px";
}
const hideCtx = () => ($("#ctx").hidden = true);
document.addEventListener("click", (e) => { if (!e.target.closest("#ctx") && !e.target.closest(".more")) hideCtx(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideCtx(); });
addEventListener("scroll", hideCtx, true);
addEventListener("resize", hideCtx);

$("#ctx").addEventListener("click", async (e) => {
  const act = e.target.closest("button")?.dataset.act;
  if (!act) return;
  hideCtx();
  const p = S.allProducts[S.ctx.idx];
  if (!p) return;
  if (act === "copy") copyText(S.ctx.cell);
  else if (act === "open") openUrl(p.open_url);
  else if (act === "fav") addFavorite(p);
});

async function addFavorite(p) {
  try {
    await api("POST", "/api/favorites", {
      site_name: p.site_name, name: p.name, price: p.price,
      unit_price: p.unit_price || "", maker: p.maker || "", url: p.url,
    });
    await loadState();
    $("#status").textContent = `⭐ '${p.name.slice(0, 25)}' 즐겨찾기 추가됨`;
    toast(`⭐ '${p.name.slice(0, 25)}' 즐겨찾기 추가됨`);
  } catch (err) {
    msg("알림", err.message);
  }
}

// ═══════════ 즐겨찾기 ═══════════
function renderFavorites() {
  const tbody = $("#fav-table tbody");
  S.selFav = null;
  if (!S.favorites.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">즐겨찾기가 없습니다</td></tr>`;
    return;
  }
  tbody.innerHTML = S.favorites.map((f) => `
    <tr data-idx="${f.idx}">
      <td class="nowrap">${esc(f.site_name)}</td>
      <td class="name">${esc(f.name)}</td>
      <td class="r">${f.price > 0 ? won(f.price) : "-"}</td>
      <td>${esc(f.unit_price || "-")}</td>
      <td>${esc(f.maker || "")}</td>
      <td class="nowrap">${esc(f.added_at || "")}</td>
    </tr>`).join("");
}
const favBody = $("#fav-table tbody");
favBody.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (!tr) return;
  selectRow(favBody, tr); S.selFav = +tr.dataset.idx;
});
favBody.addEventListener("dblclick", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (tr) openUrl(S.favorites[+tr.dataset.idx]?.open_url);
});
$("#fav-delete").addEventListener("click", async () => {
  if (S.selFav == null) return msg("알림", "삭제할 항목을 선택하세요");
  const f = S.favorites[S.selFav];
  if (!(await confirmBox("삭제 확인", `'${f.name.slice(0, 30)}'\n즐겨찾기에서 삭제할까요?`))) return;
  try { await api("DELETE", `/api/favorites/${S.selFav}`); await loadState(); }
  catch (err) { msg("오류", err.message); }
});

// ═══════════ 사이트 관리 ═══════════
function renderSites() {
  const tbody = $("#site-table tbody");
  S.selSite = null;
  tbody.innerHTML = S.sites.map((s) => {
    const login = s.requires_login ? (s.username ? `🔒 ${esc(s.username)}` : "🔑 미설정") : "🔓 불필요";
    return `
    <tr data-idx="${s.idx}">
      <td class="nowrap">${s.builtin ? "📌 " : ""}${esc(s.name)}</td>
      <td>${esc(s.base_url)}</td>
      <td>${esc(s.crawler_type)}</td>
      <td class="nowrap">${login}</td>
      <td class="c nowrap"><label class="chk"><input type="checkbox" class="en" ${s.enabled ? "checked" : ""}>
        ${s.enabled ? "✓ 활성" : "✗ 비활성"}</label></td>
    </tr>`;
  }).join("") || `<tr><td colspan="5" class="empty">사이트가 없습니다</td></tr>`;
}
const siteBody = $("#site-table tbody");
siteBody.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (!tr) return;
  selectRow(siteBody, tr); S.selSite = +tr.dataset.idx;
});
siteBody.addEventListener("change", async (e) => {
  if (!e.target.classList.contains("en")) return;
  const idx = +e.target.closest("tr").dataset.idx;
  try { await api("PUT", `/api/sites/${idx}/enabled`, { enabled: e.target.checked }); await loadState(); }
  catch (err) { msg("오류", err.message); }
});
siteBody.addEventListener("dblclick", (e) => {
  if (e.target.closest("label.chk")) return;
  const tr = e.target.closest("tr[data-idx]");
  if (tr) openSiteDialog(+tr.dataset.idx);
});
function selectedSite() {
  if (S.selSite == null) { msg("알림", "사이트를 선택하세요"); return null; }
  return S.selSite;
}

$("#site-edit").addEventListener("click", () => { const i = selectedSite(); if (i != null) openSiteDialog(i); });
$("#site-cred").addEventListener("click", () => { const i = selectedSite(); if (i != null) openCredDialog(i); });
$("#site-delete").addEventListener("click", async () => {
  const i = selectedSite(); if (i == null) return;
  if (!(await confirmBox("삭제 확인", `'${S.sites[i].name}' 사이트를 삭제하시겠습니까?`))) return;
  try { await api("DELETE", `/api/sites/${i}`); await loadState(); }
  catch (err) { msg("오류", err.message); }
});

$("#site-test").addEventListener("click", async () => {
  const n = S.sites.filter((s) => s.username).length;
  if (!n) return msg("알림", "로그인 정보가 설정된 사이트가 없습니다.\n'🔑 로그인 설정'으로 먼저 설정하세요.");
  const btn = $("#site-test");
  btn.disabled = true;
  const old = btn.textContent;
  btn.innerHTML = `<span class="spin"></span>테스트 중... (${n}개)`;
  $("#status").textContent = `🔐 로그인 테스트 중... (${n}개 사이트)`;
  try {
    const { results } = await api("POST", "/api/login-test");
    const ok = results.filter((r) => r.ok).length;
    $("#status").textContent = `🔐 로그인 테스트 완료 — ${ok}/${results.length} 성공`;
    const body = results.map((r) =>
      `<div class="${r.ok ? "ok" : "ng"}">${r.ok ? "✅" : "❌"} ${esc(r.site_name)}: ${esc(r.message)}</div>`).join("");
    msg(`로그인 테스트 결과 (${ok}/${results.length})`, body, { html: true });
  } catch (err) {
    msg("알림", err.message);
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
});

$("#site-demo").addEventListener("click", async () => {
  if (S.sites.length && !(await confirmBox("확인", "사용자 추가 사이트를 제거하고 데모를 불러올까요?\n(내장 사이트는 유지됩니다)"))) return;
  try {
    await api("POST", "/api/demo"); await loadState();
    msg("완료", "데모 사이트 2개가 추가되었습니다.\n내장 사이트의 로그인 정보는 유지됩니다.");
  } catch (err) { msg("오류", err.message); }
});

// ── 사이트 수정 다이얼로그 ──
const siteDlg = $("#site-dlg"), siteForm = $("#site-form");
let siteEditIdx = null;
function openSiteDialog(idx) {
  siteEditIdx = idx;
  const s = idx != null ? S.sites[idx] : null;
  const sel = siteForm.crawler_type;
  sel.innerHTML = S.info.crawler_types.map((t) => `<option>${esc(t)}</option>`).join("");
  const f = siteForm.elements;
  f.name.value = s?.name ?? "";
  f.base_url.value = s?.base_url ?? "https://";
  sel.value = s?.crawler_type ?? "generic";
  f.enabled.checked = s?.enabled ?? true;
  f.requires_login.checked = s?.requires_login ?? false;
  f.username.value = s?.username ?? "";
  f.password.value = "";
  f.password.placeholder = s?.has_password ? `저장됨 (${s.password_masked}) — 변경 시에만 입력` : "";
  f.login_url.value = s?.login_url ?? "/member/login";
  f.id_field.value = s?.id_field ?? "user_id";
  f.pw_field.value = s?.pw_field ?? "password";
  const ds = { search_url_pattern: "/search?q={query}", product_list: ".product-item", product_name: ".product-name", product_price: ".product-price" };
  for (const k in ds) f["sel_" + k].value = s?.selectors?.[k] ?? ds[k];
  $("#login-fs").disabled = !f.requires_login.checked;
  siteDlg.showModal();
}
$("#req-login").addEventListener("change", (e) => ($("#login-fs").disabled = !e.target.checked));
siteForm.addEventListener("submit", async (e) => {
  if (e.submitter?.value !== "save") return;
  e.preventDefault();
  const f = siteForm.elements;
  const body = {
    name: f.name.value.trim(), base_url: f.base_url.value.trim(),
    crawler_type: f.crawler_type.value, enabled: f.enabled.checked,
    requires_login: f.requires_login.checked,
    username: f.username.value, password: f.password.value,
    login_url: f.login_url.value, id_field: f.id_field.value, pw_field: f.pw_field.value,
    selectors: Object.fromEntries(["search_url_pattern", "product_list", "product_name", "product_price"].map((k) => [k, f["sel_" + k].value])),
  };
  if (!body.name || !body.base_url) return msg("알림", "사이트 이름과 URL은 필수입니다");
  try {
    await api("PUT", `/api/sites/${siteEditIdx}`, body);
    siteDlg.close();
    await loadState();
  } catch (err) { msg("오류", err.message); }
});

// ── 로그인 정보 다이얼로그 ──
const credDlg = $("#cred-dlg"), credForm = $("#cred-form");
let credIdx = null;
function openCredDialog(idx) {
  credIdx = idx;
  const s = S.sites[idx];
  $("#cred-site").textContent = `사이트: ${s.name}`;
  credForm.username.value = s.username || "";
  credForm.password.value = "";
  $("#cred-masked").textContent = s.has_password ? `현재 저장된 비밀번호: ${s.password_masked}` : "";
  credDlg.showModal();
  credForm.username.focus();
}
credForm.addEventListener("submit", async (e) => {
  if (e.submitter?.value !== "save") return;
  e.preventDefault();
  const name = S.sites[credIdx].name;
  try {
    const r = await api("PUT", `/api/sites/${credIdx}/credentials`, {
      username: credForm.username.value, password: credForm.password.value,
    });
    credDlg.close();
    await loadState();
    msg("저장 완료", `'${name}' 로그인 정보가 저장되었습니다.\n암호화: ${r.encryption}`);
  } catch (err) { msg("오류", err.message); }
});

// ═══════════ 메모장 ═══════════
async function loadMemo() {
  const { content } = await api("GET", "/api/memo");
  $("#memo").value = content;
}
async function saveMemo() {
  try {
    const r = await api("PUT", "/api/memo", { content: $("#memo").value });
    msg("저장 완료", `메모가 암호화되어 저장되었습니다.\n(${r.encryption})`);
  } catch (err) { msg("저장 실패", `메모 저장 중 오류: ${err.message}`); }
}
$("#memo-save").addEventListener("click", saveMemo);
$("#memo").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveMemo(); }
});

// ═══════════ 설정 ═══════════
function renderSettings() {
  $("#set-max").value = S.settings.max_results_per_site ?? 10;
  $("#set-timeout").value = S.settings.timeout_seconds ?? 30;
  $("#hide-soldout").checked = !!S.settings.hide_soldout;
  $("#prog-info").textContent = `버전: v${S.info.version} (웹)\n암호화: ${S.info.encryption}\n설정 파일: ${S.info.config_path}`;
}
$("#settings-save").addEventListener("click", async () => {
  const mx = $("#set-max").value, to = $("#set-timeout").value;
  if (!/^\d+$/.test(mx) || !/^\d+$/.test(to)) return msg("오류", "숫자를 입력하세요");
  try {
    const r = await api("PUT", "/api/settings", { max_results_per_site: +mx, timeout_seconds: +to });
    S.settings = r.settings;
    msg("저장", "설정이 저장되었습니다.");
  } catch (err) { msg("오류", err.message); }
});

async function loadDebug() {
  const tbody = $("#debug-table tbody");
  try {
    const { files } = await api("GET", "/api/debug");
    tbody.innerHTML = files.map((f) => `
      <tr>
        <td><a href="/api/debug/${encodeURIComponent(f.name)}" style="color:var(--text)">${esc(f.name)}</a></td>
        <td class="r">${(f.size / 1024).toFixed(1)} KB</td>
        <td class="nowrap">${esc(f.modified)}</td>
        <td class="c"><button class="btn danger mini" data-del="${esc(f.name)}">삭제</button></td>
      </tr>`).join("") || `<tr><td colspan="4" class="empty">진단 파일이 없습니다</td></tr>`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty">${esc(err.message)}</td></tr>`;
  }
}
$("#debug-refresh").addEventListener("click", loadDebug);
$("#debug-table tbody").addEventListener("click", async (e) => {
  const name = e.target.dataset?.del;
  if (!name) return;
  if (!(await confirmBox("삭제 확인", `'${name}'\n진단 파일을 삭제할까요?`))) return;
  try { await api("DELETE", `/api/debug/${encodeURIComponent(name)}`); loadDebug(); }
  catch (err) { msg("오류", err.message); }
});

// ═══════════ 시작 ═══════════
(async function init() {
  try {
    S.info = await api("GET", "/api/info");
    document.title = `도매 최저가 비교 v${S.info.version}`;
    $("#hdr-info").textContent = `v${S.info.version}  |  암호화: ${S.info.encryption}`;
    await loadState();
    renderSettings();
    await loadMemo();
    $("#q").focus();
  } catch (err) {
    $("#status").textContent = "⚠ 서버 연결 실패: " + err.message;
  }
})();
