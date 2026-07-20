// Same-origin backend — no base URL needed, frontend and API share one deployment.

const state = {
  schema: [],
  lastResult: null,
};

const HISTORY_KEY = "querypal_history";

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveHistory(list) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(-10)));
}

async function fetchSchema() {
  try {
    const res = await fetch("/schema");
    const data = await res.json();
    state.schema = data.schema || [];
  } catch {
    state.schema = [];
  }
  renderSchemaPanel();
  renderTableOptions();
}

function renderSchemaPanel() {
  const el = document.getElementById("schema-panel");
  if (!state.schema.length) {
    el.innerHTML = "<p class='muted'>No tables found. Upload a dataset to get started.</p>";
    return;
  }
  el.innerHTML = state.schema.map(t => `
    <div class="schema-table-name">▸ ${escapeHtml(t.table)}</div>
    ${t.columns.map(c => `
      <div class="schema-col-row">
        <span class="schema-col-name">${escapeHtml(c.name)}
          ${c.is_pk ? '<span class="badge-pk">PK</span>' : ''}
          ${c.is_fk ? '<span class="badge-fk">FK</span>' : ''}
        </span>
        <span class="schema-col-type">${escapeHtml(c.type)}</span>
      </div>`).join("")}
  `).join("");
}

function renderTableOptions() {
  const sel = document.getElementById("table-select");
  const current = sel.value;
  sel.innerHTML = '<option value="">Select a table…</option>' +
    state.schema.map(t => `<option value="${escapeHtml(t.table)}">${escapeHtml(t.table)}</option>`).join("");
  if (state.schema.some(t => t.table === current)) sel.value = current;
}

function renderHistory() {
  const el = document.getElementById("history-list");
  const history = getHistory();
  if (!history.length) {
    el.innerHTML = "<p class='muted'>No queries yet.</p>";
    return;
  }
  el.innerHTML = history.slice().reverse().map((item, i) => {
    const label = item.question.length > 40 ? item.question.slice(0, 40) + "…" : item.question;
    return `<button type="button" class="list-group-item list-group-item-action history-item" data-idx="${history.length - 1 - i}">↩ ${escapeHtml(label)}</button>`;
  }).join("");
  el.querySelectorAll(".history-item").forEach(node => {
    node.addEventListener("click", () => {
      const item = history[parseInt(node.dataset.idx, 10)];
      document.getElementById("question-input").value = item.question;
      document.getElementById("table-select").value = item.table;
      if (item.result) {
        state.lastResult = item.result;
        renderResults(item.result);
      }
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

// ── Upload ────────────────────────────────────────────────────────────
document.getElementById("upload-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const stem = file.name.replace(/\.[^/.]+$/, "");
  const sanitized = stem.toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "uploaded_table";
  document.getElementById("upload-table-name").value = sanitized;
});

document.getElementById("upload-btn").addEventListener("click", async () => {
  const fileInput = document.getElementById("upload-file");
  const tableName = document.getElementById("upload-table-name").value.trim();
  const ifExists = document.getElementById("upload-mode").value;
  const statusEl = document.getElementById("upload-status");

  if (!fileInput.files[0] || !tableName) {
    statusEl.className = "error";
    statusEl.textContent = "Choose a file and a table name first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("table_name", tableName);
  formData.append("if_exists", ifExists);

  statusEl.className = "";
  statusEl.textContent = "Uploading…";

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    statusEl.className = "success";
    statusEl.textContent = `Loaded ${data.row_count} rows into '${data.table}' (${data.columns.length} columns).`;
    await fetchSchema();
    document.getElementById("table-select").value = data.table;
  } catch (err) {
    statusEl.className = "error";
    statusEl.textContent = `Upload failed: ${err.message}`;
  }
});

// ── Query execution ──────────────────────────────────────────────────
document.getElementById("run-btn").addEventListener("click", async () => {
  const question = document.getElementById("question-input").value.trim();
  const table = document.getElementById("table-select").value;
  const warningEl = document.getElementById("warning");
  const errorBox = document.getElementById("error-box");

  warningEl.textContent = "";
  errorBox.style.display = "none";

  if (!question || !table) {
    warningEl.textContent = "Please select a table and type a question first.";
    return;
  }

  document.getElementById("results").style.display = "none";
  const runBtn = document.getElementById("run-btn");
  runBtn.disabled = true;
  runBtn.textContent = "Thinking…";

  try {
    const res = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, table })
    });
    const data = await res.json();

    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : (data.detail?.error || "Unknown error");
      throw new Error(detail);
    }

    data.timestamp = new Date().toLocaleTimeString();
    state.lastResult = data;
    renderResults(data);

    const history = getHistory();
    history.push({ question, table, result: data });
    saveHistory(history);
    renderHistory();
  } catch (err) {
    errorBox.style.display = "block";
    errorBox.textContent = `⚠ ${err.message}`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "⚡ Run Query";
  }
});

document.getElementById("clear-btn").addEventListener("click", () => {
  document.getElementById("question-input").value = "";
  document.getElementById("table-select").value = "";
  document.getElementById("results").style.display = "none";
  document.getElementById("error-box").style.display = "none";
  document.getElementById("warning").textContent = "";
});

document.getElementById("refresh-schema-btn").addEventListener("click", fetchSchema);

// ── Tabs ─────────────────────────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

// ── Rendering results ───────────────────────────────────────────────
function renderResults(data) {
  document.getElementById("results").style.display = "block";
  document.getElementById("metric-rows").textContent = data.row_count ?? 0;
  document.getElementById("metric-cols").textContent = (data.columns || []).length;
  document.getElementById("metric-time").textContent = data.timestamp || "—";
  document.getElementById("sql-block").textContent = data.generated_sql || "";

  renderTable(data.columns || [], data.rows || []);
  renderChart(data.chart || {}, data.columns || [], data.rows || []);
}

function renderTable(columns, rows) {
  const el = document.getElementById("results-table");
  if (!rows.length) {
    el.innerHTML = "<p class='muted' style='padding:16px'>Query returned 0 rows.</p>";
    return;
  }
  el.innerHTML = `
    <table class="data-table">
      <thead><tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows.map(r => `<tr>${columns.map(c => `<td>${escapeHtml(r[c])}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>`;
}

function renderChart(chart, columns, rows) {
  const insightBox = document.getElementById("insight-box");
  const chartDiv = document.getElementById("chart-div");

  if (chart.insight) {
    insightBox.style.display = "block";
    insightBox.innerHTML = `<span class="label">Analyst Insight</span><span class="text">${escapeHtml(chart.insight)}</span>`;
  } else {
    insightBox.style.display = "none";
  }

  const type = chart.chart_type || "none";
  if (type === "none" || !rows.length) {
    Plotly.purge(chartDiv);
    chartDiv.innerHTML = "<p class='muted' style='padding:16px'>No chart available for this result.</p>";
    return;
  }

  const x = rows.map(r => r[chart.x_col]);
  const y = chart.y_col ? rows.map(r => r[chart.y_col]) : undefined;
  const colors = ["#4f8ef7", "#7c5cfc", "#38bdf8", "#4ade80", "#fb923c"];
  let traces = [];

  if (type === "bar") {
    traces = [{ x, y, type: "bar", marker: { color: colors[0] } }];
  } else if (type === "line") {
    traces = [{ x, y, type: "scatter", mode: "lines+markers", marker: { color: colors[0] } }];
  } else if (type === "pie") {
    traces = [{ labels: x, values: y, type: "pie", marker: { colors } }];
  } else if (type === "scatter") {
    traces = [{ x, y, type: "scatter", mode: "markers", marker: { color: colors[0] } }];
  } else if (type === "histogram") {
    traces = [{ x, type: "histogram", marker: { color: colors[0] } }];
  }

  const layout = {
    title: chart.title || "",
    paper_bgcolor: "#0d0f12",
    plot_bgcolor: "#151820",
    font: { color: "#cbd5e1", family: "Syne", size: 13 },
    margin: { l: 40, r: 20, t: 50, b: 40 },
    xaxis: { gridcolor: "#1e2330", linecolor: "#1e2330" },
    yaxis: { gridcolor: "#1e2330", linecolor: "#1e2330" },
  };

  Plotly.newPlot(chartDiv, traces, layout, { responsive: true, displaylogo: false });
}

// ── Init ─────────────────────────────────────────────────────────────
renderHistory();
fetchSchema();
