/**
 * UI Components for AI Architect Demo
 */

export function renderMessage(role, content) {
  const isAssistant = role === 'assistant' || role === 'system';
  const roleName = isAssistant ? 'AI' : 'You';
  const className = isAssistant ? 'msg-assistant' : 'msg-user';

  return `
    <div class="msg-bubble ${className}">
      <div class="msg-role">${escapeHtml(roleName)}</div>
      <div class="msg-content">${escapeHtml(content || '')}</div>
    </div>
  `;
}

export function renderBundleCard(recommendation, onConfirm) {
  const bundleKey = recommendation?.primary_bundle_key || 'Unknown';
  const reasoning = recommendation?.reasoning || 'Based on your needs, we suggest this bundle.';
  const modules = (recommendation?.inferred_modules || []).join(', ');

  return `
    <div class="bundle-confirmation-card">
      <div class="card-title">Proposed Bundle: ${escapeHtml(bundleKey)}</div>
      <div class="card-reasoning">${escapeHtml(reasoning)}</div>
      <div class="card-modules"><strong>Included Modules:</strong> ${escapeHtml(modules)}</div>
      <div class="card-actions">
        <button id="confirmBundleBtn" class="primary-btn">Looks Good, Confirm</button>
      </div>
    </div>
  `;
}

export function renderDashboard(payload) {
  if (!payload || !payload.dummy_data_json) {
    return `<div class="dashboard-empty">Generate a preview to see your dashboard data.</div>`;
  }

  const { dummy_data_json, generation_json, display_name } = payload;
  const stores = dummy_data_json.stores || {};
  const kpis = stores.kpis || [];

  // 1. Render KPIs
  const kpiGrid = kpis.map(kpi => `
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(kpi.label)}</div>
      <div class="kpi-value">${escapeHtml(String(kpi.sample_value))} ${kpi.type === 'percentage' ? '%' : ''}</div>
      <div class="kpi-source">${escapeHtml(kpi.source_service)}</div>
    </div>
  `).join('');

  // 2. Render Tables (Generic for any store that is an array)
  const tables = Object.entries(stores)
    .filter(([key, val]) => key !== 'kpis' && Array.isArray(val) && val.length > 0)
    .map(([key, rows]) => {
      const headers = Object.keys(rows[0]).filter(h => h !== 'id');
      return `
        <div class="dashboard-table-container">
          <h3>${escapeHtml(key.charAt(0).toUpperCase() + key.slice(1))}</h3>
          <table class="dashboard-table">
            <thead>
              <tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr>
            </thead>
            <tbody>
              ${rows.map(row => `
                <tr>${headers.map(h => `<td>${escapeHtml(String(row[h] ?? ''))}</td>`).join('')}</tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }).join('');

  return `
    <div class="dashboard">
      <header class="dashboard-header">
        <h2>${escapeHtml(display_name)} Dashboard</h2>
        <span class="badge">Preview Mode</span>
      </header>
      <div class="kpi-grid">${kpiGrid}</div>
      <div class="tables-grid">${tables}</div>
      <div class="dashboard-actions">
        <button id="deployBtn" class="success-btn">Finalize & Deploy App</button>
      </div>
    </div>
  `;
}

export function renderPipelineStatus(state) {
  const candidates = state.classification?.ranked_candidates || [];
  const candidateList = candidates.map(c => `
    <div class="candidate-row">
      <span class="candidate-name">${escapeHtml(c.display_name)}</span>
      <span class="candidate-confidence">${(c.confidence * 100).toFixed(0)}%</span>
    </div>
  `).join('');

  return `
    <div class="pipeline-status">
      <div class="status-item">
        <label>Session Status</label>
        <span class="status-pill ${state.lastStatus}">${escapeHtml(state.lastStatus || 'idle')}</span>
      </div>
      <div class="status-item">
        <label>Selected Bundle</label>
        <span>${escapeHtml(state.recommendation?.primary_bundle_key || 'None')}</span>
      </div>
      <div class="candidate-list">
        <label>Confidence Rankings</label>
        ${candidateList || '<em>No candidates yet</em>'}
      </div>
    </div>
  `;
}

export function renderThinkingIndicator(status) {
  return `
    <div id="thinkingIndicator" class="msg-bubble msg-assistant thinking-bubble">
      <div class="msg-role">AI</div>
      <div class="msg-content">
        <span class="thinking-text">${escapeHtml(status)}</span>
        <span class="dot-flashing"></span>
      </div>
    </div>
  `;
}

export function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}
