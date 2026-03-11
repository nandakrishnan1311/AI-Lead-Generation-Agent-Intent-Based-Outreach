/**
 * script.js — Dashboard logic for AI Lead Generation Agent
 */

const API_BASE = "http://127.0.0.1:8000";

let allLeads = [];
let pollInterval = null;

// ── Utilities ──────────────────────────────────────────────────────────────

function showToast(msg, type = "info") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove("hidden");
  clearTimeout(t._timeout);
  t._timeout = setTimeout(() => t.classList.add("hidden"), 4000);
}

function setStatus(state) {
  const dot   = document.getElementById("statusDot");
  const label = document.getElementById("statusLabel");
  dot.className = `status-dot ${state}`;
  const labels = { idle: "Idle", running: "Running…", done: "Done", error: "Error" };
  label.textContent = labels[state] || state;
}

function setProgress(pct, msg) {
  const wrap = document.getElementById("progressBar");
  const fill = document.getElementById("progressFill");
  const msgEl = document.getElementById("progressMsg");
  if (pct === null) { wrap.classList.add("hidden"); return; }
  wrap.classList.remove("hidden");
  fill.style.width = pct + "%";
  msgEl.textContent = msg || "";
}

function scoreBadge(score) {
  const cls = score >= 7 ? "score-high" : score >= 4 ? "score-med" : "score-low";
  return `<span class="score-badge ${cls}">${score.toFixed(1)}</span>`;
}

function linkCell(url, label) {
  if (!url) return '<span style="color:#555">—</span>';
  const display = label || (url.length > 30 ? url.slice(0, 28) + "…" : url);
  return `<div class="cell-link"><a href="${url}" target="_blank" rel="noopener">${display}</a></div>`;
}

// ── Render table ───────────────────────────────────────────────────────────

function renderLeads(leads) {
  const tbody = document.getElementById("leadsBody");
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No leads found yet. Run the agent to discover leads.</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map((l, i) => `
    <tr>
      <td style="color:var(--text-muted)">${l.id}</td>
      <td class="cell-company">${escHtml(l.company)}</td>
      <td>${escHtml(l.contact) || '<span style="color:#555">—</span>'}</td>
      <td>${escHtml(l.title)   || '<span style="color:#555">—</span>'}</td>
      <td>${linkCell(l.linkedin, "LinkedIn")}</td>
      <td>${linkCell(l.website)}</td>
      <td class="cell-signal"><p>${escHtml(l.signal)}</p></td>
      <td>${scoreBadge(l.score || 0)}</td>
      <td class="cell-date">${escHtml(l.date_found)}</td>
      <td><button class="del-btn" title="Delete lead" onclick="deleteLead(${l.id})">🗑</button></td>
    </tr>
  `).join("");
}

function escHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Load leads + stats ─────────────────────────────────────────────────────

async function loadLeads() {
  try {
    const [leadsRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/leads`),
      fetch(`${API_BASE}/stats`),
    ]);

    allLeads = await leadsRes.json();
    const stats = await statsRes.json();

    renderLeads(allLeads);
    document.getElementById("statTotal").textContent    = stats.total_leads    ?? "—";
    document.getElementById("statHigh").textContent     = stats.high_intent    ?? "—";
    document.getElementById("statMed").textContent      = stats.medium_intent  ?? "—";
    document.getElementById("statLow").textContent      = stats.low_intent     ?? "—";
    document.getElementById("statContacts").textContent = stats.contacts_found ?? "—";
    document.getElementById("statAvg").textContent      = stats.avg_score      ?? "—";
  } catch (err) {
    showToast("Could not reach API. Is the backend running?", "error");
    console.error(err);
  }
}

// ── Filter ─────────────────────────────────────────────────────────────────

function filterLeads() {
  const q = document.getElementById("searchBox").value.toLowerCase();
  if (!q) { renderLeads(allLeads); return; }
  const filtered = allLeads.filter(l =>
    (l.company  || "").toLowerCase().includes(q) ||
    (l.contact  || "").toLowerCase().includes(q) ||
    (l.signal   || "").toLowerCase().includes(q) ||
    (l.title    || "").toLowerCase().includes(q)
  );
  renderLeads(filtered);
}

// ── Run agent ──────────────────────────────────────────────────────────────

async function runAgent() {
  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  setStatus("running");
  setProgress(10, "Starting lead agent pipeline…");
  showToast("Agent started! This may take a few minutes.", "info");

  try {
    const res = await fetch(`${API_BASE}/run-agent`, { method: "POST" });
    const data = await res.json();

    if (data.running) {
      // Poll for completion
      let pct = 10;
      const msgs = [
        "Collecting news signals…",
        "Classifying signals with AI…",
        "Discovering contacts…",
        "Saving leads to database…",
        "Generating Excel report…",
      ];
      let msgIdx = 0;

      pollInterval = setInterval(async () => {
        pct = Math.min(pct + 12, 92);
        if (msgIdx < msgs.length) { setProgress(pct, msgs[msgIdx++]); }

        try {
          const statusRes = await fetch(`${API_BASE}/run-status`);
          const status = await statusRes.json();

          if (!status.running) {
            clearInterval(pollInterval);
            setProgress(100, "Pipeline complete!");
            setTimeout(() => setProgress(null), 1500);

            if (status.last_result?.error) {
              setStatus("error");
              showToast("Pipeline error: " + status.last_result.error, "error");
            } else {
              setStatus("done");
              const r = status.last_result || {};
              showToast(
                `Done! ${r.new_leads_saved ?? "?"} new leads saved, ${r.signals_qualified ?? "?"} signals qualified.`,
                "success"
              );
              await loadLeads();
            }
            btn.disabled = false;
          }
        } catch {/* ignore poll errors */}
      }, 3000);

    } else {
      showToast(data.message || "Agent already running.", "info");
      btn.disabled = false;
      setProgress(null);
      setStatus("running");
    }
  } catch (err) {
    setStatus("error");
    setProgress(null);
    showToast("Failed to reach API. Is the backend running on port 8000?", "error");
    btn.disabled = false;
    console.error(err);
  }
}

// ── Download report ────────────────────────────────────────────────────────

function downloadReport() {
  showToast("Generating report…", "info");
  window.location.href = `${API_BASE}/download-report`;
}

// ── Delete lead ────────────────────────────────────────────────────────────

async function deleteLead(id) {
  if (!confirm(`Delete lead #${id}?`)) return;
  try {
    await fetch(`${API_BASE}/leads/${id}`, { method: "DELETE" });
    showToast(`Lead #${id} deleted.`, "success");
    await loadLeads();
  } catch (err) {
    showToast("Delete failed.", "error");
    console.error(err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────

window.addEventListener("DOMContentLoaded", loadLeads);
