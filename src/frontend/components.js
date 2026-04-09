export function appendMessage(container, role, content) {
  const el = document.createElement('article');
  el.className = 'msg';
  el.innerHTML = `
    <div class="msg-role">${escapeHtml(role)}</div>
    <div class="msg-content">${escapeHtml(content || '')}</div>
  `;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

export function renderPipeline(panel, state) {
  panel.innerHTML = `
    <div class="card">
      <h3>Status</h3>
      <p class="kv">status: ${escapeHtml(state.lastStatus || 'n/a')}</p>
      <p class="kv">preview_type: ${escapeHtml(state.previewType || 'n/a')}</p>
      <p class="kv">warning: ${escapeHtml(state.warning || 'none')}</p>
    </div>
    <div class="card">
      <h3>Recommendation</h3>
      <p class="kv">status: ${escapeHtml(state.recommendation?.recommendation_status || 'n/a')}</p>
      <p class="kv">primary: ${escapeHtml(state.recommendation?.primary_bundle_key || 'n/a')}</p>
      <p class="kv">fallbacks: ${escapeHtml((state.recommendation?.fallback_bundle_keys || []).join(', ') || 'none')}</p>
    </div>
  `;
}

export function renderExtraction(panel, debug) {
  if (!debug) {
    panel.innerHTML = '<div class="card"><h3>Extraction</h3><p class="kv">No extraction data yet.</p></div>';
    return;
  }

  panel.innerHTML = `
    <div class="card"><h3>Keywords</h3><pre>${escapeHtml((debug.extracted_keywords || []).join('\n'))}</pre></div>
    <div class="card"><h3>Entities</h3><pre>${escapeHtml((debug.extracted_entities || []).join('\n'))}</pre></div>
    <div class="card"><h3>Intents</h3><pre>${escapeHtml((debug.extracted_intents || []).join('\n'))}</pre></div>
    <div class="card"><h3>Missing Fields</h3><pre>${escapeHtml((debug.missing_fields || []).join('\n'))}</pre></div>
    <div class="card"><h3>Personalization</h3><pre>${escapeHtml(JSON.stringify(debug.personalization || {}, null, 2))}</pre></div>
  `;
}

export function renderClassification(panel, classification) {
  if (!classification) {
    panel.innerHTML = '<div class="card"><h3>Classification</h3><p class="kv">No classification yet.</p></div>';
    return;
  }

  const candidates = (classification.ranked_candidates || [])
    .map(
      (c) => `
      <li>
        <strong>${escapeHtml(c.display_name)}</strong>
        <span class="kv"> (${escapeHtml(c.bundle_key)}) confidence=${Number(c.confidence).toFixed(2)}</span>
      </li>`
    )
    .join('');

  panel.innerHTML = `
    <div class="card">
      <h3>Decision</h3>
      <p class="kv">confidence_status: ${escapeHtml(classification.confidence_status)}</p>
      <p class="kv">top_bundle_key: ${escapeHtml(classification.top_bundle_key || 'n/a')}</p>
      <p class="kv">top_confidence: ${Number(classification.top_confidence || 0).toFixed(2)}</p>
      <p class="kv">score_gap: ${Number(classification.score_gap || 0).toFixed(2)}</p>
      <p class="kv">missing_context: ${escapeHtml((classification.missing_context || []).join(', ') || 'none')}</p>
      <p class="kv">reasoning: ${escapeHtml(classification.reasoning || 'n/a')}</p>
    </div>
    <div class="card">
      <h3>Candidates</h3>
      <ol>${candidates}</ol>
    </div>
  `;
}

export function renderMetadata(panel, metadata, error = '') {
  if (error) {
    panel.innerHTML = `<div class="card"><h3>Metadata</h3><p class="kv">${escapeHtml(error)}</p></div>`;
    return;
  }
  if (!metadata) {
    panel.innerHTML = '<div class="card"><h3>Metadata</h3><p class="kv">No metadata loaded yet.</p></div>';
    return;
  }

  panel.innerHTML = `
    <div class="card"><h3>Bundle</h3><pre>${escapeHtml(JSON.stringify(metadata, null, 2))}</pre></div>
  `;
}

export function renderFooter(footer, state) {
  footer.textContent = `session_id=${state.sessionId || 'none'} | turns=${state.turnCount} | status=${state.lastStatus || 'idle'}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}
