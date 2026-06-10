const state = {
  activeTab: "agent",
  activeSourceView: "evidence",
  evidenceSources: [],
  rawSources: [],
  answer: "",
};

const $ = (id) => document.getElementById(id);

function setStatus(text, kind = "normal") {
  const el = $("status");
  el.textContent = text;
  el.style.color = kind === "error" ? "#f87171" : kind === "ok" ? "#86efac" : "#94a3b8";
}

function escapeHtml(text = "") {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAnswer(text) {
  const el = $("answer");
  state.answer = text || "";
  if (!text) {
    el.textContent = "还没有答案。";
    el.classList.add("empty");
    return;
  }
  el.classList.remove("empty");
  el.innerHTML = escapeHtml(text)
    .replace(/\n/g, "<br>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
}

function renderQueries(queries = []) {
  const el = $("queries");
  if (!queries.length) {
    el.innerHTML = '<span class="muted">无</span>';
    return;
  }
  el.innerHTML = queries.map(q => `<span class="chip">${escapeHtml(q)}</span>`).join("");
}

function renderErrors(errors = []) {
  const el = $("errors");
  if (!errors.length) {
    el.textContent = "无";
    el.classList.add("muted");
    return;
  }
  el.classList.remove("muted");
  el.innerHTML = errors.map(e => `• ${escapeHtml(e)}`).join("<br>");
}

function normalizeSource(item, idx, type) {
  return {
    type,
    index: idx + 1,
    source_id: item.source_id || item.engine || "",
    title: item.title || "未命名来源",
    url: item.url || "",
    snippet: item.snippet || item.quote_or_summary || "",
    supports: item.supports || "",
    engine: item.engine || "",
    score: item.score ?? "",
  };
}

function renderSources() {
  const el = $("sources");
  const list = state.activeSourceView === "evidence" ? state.evidenceSources : state.rawSources;
  if (!list.length) {
    el.textContent = state.activeSourceView === "evidence" ? "暂无引用来源。" : "暂无搜索结果。";
    el.classList.add("empty");
    return;
  }
  el.classList.remove("empty");
  el.innerHTML = list.map((s, i) => `
    <article class="source-card" data-index="${i}">
      <span class="badge">${escapeHtml(s.type === "evidence" ? `引用 ${s.source_id || s.index}` : s.engine || "搜索结果")}</span>
      <div class="source-title">${escapeHtml(s.title)}</div>
      <div class="source-url">${escapeHtml(s.url)}</div>
      ${s.supports ? `<div class="source-supports">支持：${escapeHtml(s.supports)}</div>` : ""}
      ${s.snippet ? `<div class="source-snippet">${escapeHtml(s.snippet.slice(0, 220))}</div>` : ""}
    </article>
  `).join("");

  el.querySelectorAll(".source-card").forEach(card => {
    card.addEventListener("click", () => {
      const idx = Number(card.dataset.index);
      fetchPage(list[idx]);
    });
  });
}

async function postJson(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text.slice(0, 500)}`);
  }
  return resp.json();
}

async function runAgentSearch() {
  const question = $("question").value.trim();
  if (!question) {
    setStatus("请输入搜索问题。", "error");
    return;
  }

  $("searchBtn").disabled = true;
  setStatus("正在规划查询词、搜索数据源、抓取网页、检索 BGE 并生成答案……");
  renderAnswer("搜索中，请稍候……");
  renderQueries([]);
  renderErrors([]);
  state.evidenceSources = [];
  state.rawSources = [];
  renderSources();

  try {
    const data = await postJson("/search-agent", {
      question,
      mode: $("mode").value,
    });

    renderAnswer(data.answer || "未生成答案。");
    renderQueries(data.queries || []);
    renderErrors(data.errors || []);
    state.evidenceSources = (data.sources || []).map((item, idx) => normalizeSource(item, idx, "evidence"));
    state.rawSources = (data.search_results || []).map((item, idx) => normalizeSource(item, idx, "raw"));
    state.activeSourceView = state.evidenceSources.length ? "evidence" : "raw";
    syncSourceButtons();
    renderSources();
    setStatus(`完成。引用来源 ${state.evidenceSources.length} 条，搜索结果 ${state.rawSources.length} 条。`, "ok");
  } catch (err) {
    setStatus(`搜索失败：${err.message}`, "error");
    renderAnswer("");
  } finally {
    $("searchBtn").disabled = false;
  }
}

async function runSourceSearch() {
  const query = $("question").value.trim();
  if (!query) {
    setStatus("请输入关键词。", "error");
    return;
  }

  $("searchBtn").disabled = true;
  setStatus("正在通过 SearXNG 查找数据源……");
  renderAnswer("只找数据源模式不会生成答案。请在下方点击数据源查看网页正文。");
  renderQueries([query]);
  renderErrors([]);
  state.evidenceSources = [];
  state.rawSources = [];
  state.activeSourceView = "raw";
  syncSourceButtons();
  renderSources();

  try {
    const data = await postJson("/search-sources", { query });
    state.rawSources = (data.results || []).map((item, idx) => normalizeSource(item, idx, "raw"));
    renderSources();
    setStatus(`完成。找到 ${state.rawSources.length} 条数据源。`, "ok");
  } catch (err) {
    setStatus(`查找数据源失败：${err.message}`, "error");
  } finally {
    $("searchBtn").disabled = false;
  }
}

async function fetchPage(source) {
  if (!source || !source.url) {
    setStatus("这个来源没有 URL，无法抓取。", "error");
    return;
  }
  $("pageInfo").innerHTML = `正在抓取：<br>${escapeHtml(source.title)}<br><span class="source-url">${escapeHtml(source.url)}</span>`;
  $("pageContent").textContent = "抓取中……";
  $("openUrl").classList.remove("hidden");
  $("openUrl").href = source.url;

  try {
    const data = await postJson("/fetch-page", {
      url: source.url,
      title: source.title,
      snippet: source.snippet,
    });
    $("pageInfo").innerHTML = `
      <strong>${escapeHtml(data.title || source.title)}</strong><br>
      <span class="source-url">${escapeHtml(data.url || source.url)}</span>
      ${data.error ? `<br><span style="color:#f87171">抓取提示：${escapeHtml(data.error)}</span>` : ""}
    `;
    $("pageContent").textContent = data.content || "没有抓取到正文。可以点击右上角“打开原网页”查看。";
  } catch (err) {
    $("pageContent").textContent = `抓取失败：${err.message}`;
  }
}

function syncTabs() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === state.activeTab);
  });
  $("agentOptions").style.display = state.activeTab === "agent" ? "block" : "none";
  $("searchBtn").textContent = state.activeTab === "agent" ? "开始智能搜索" : "查找数据源";
}

function syncSourceButtons() {
  $("showEvidenceBtn").classList.toggle("active", state.activeSourceView === "evidence");
  $("showRawBtn").classList.toggle("active", state.activeSourceView === "raw");
}

async function checkHealth() {
  setStatus("正在检查服务状态……");
  try {
    const resp = await fetch("/health");
    const data = await resp.json();
    renderErrors([]);
    setStatus(`服务正常。模型：${data.vllm_model}；SearXNG：${data.searxng_url}；BGE：${data.bge_db_enabled ? data.bge_db_base_url : "未启用"}`, "ok");
  } catch (err) {
    setStatus(`服务检查失败：${err.message}`, "error");
  }
}

function init() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      syncTabs();
      setStatus(state.activeTab === "agent" ? "智能搜索模式。" : "只找数据源模式。", "ok");
    });
  });

  $("searchBtn").addEventListener("click", () => {
    if (state.activeTab === "agent") runAgentSearch();
    else runSourceSearch();
  });

  $("question").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      $("searchBtn").click();
    }
  });

  $("showEvidenceBtn").addEventListener("click", () => {
    state.activeSourceView = "evidence";
    syncSourceButtons();
    renderSources();
  });

  $("showRawBtn").addEventListener("click", () => {
    state.activeSourceView = "raw";
    syncSourceButtons();
    renderSources();
  });

  $("copyAnswerBtn").addEventListener("click", async () => {
    if (!state.answer) return;
    await navigator.clipboard.writeText(state.answer);
    setStatus("答案已复制。", "ok");
  });

  $("healthBtn").addEventListener("click", checkHealth);

  syncTabs();
  syncSourceButtons();
  renderSources();
}

init();
