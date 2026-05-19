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

export function renderBundleCard(recommendation) {
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

// ─── Dashboard: internal constants ───────────────────────────────────────────

const INTERNAL_STORE_KEYS = new Set([
  'kpis', 'dashboard_generation_output', 'dashboard_widgets',
]);

const PRIORITY_ORDER = ['urgent', 'critical', 'high', 'medium', 'normal', 'low'];

const STATUS_COLORS = {
  open: '#ef4444', pending: '#ef4444',
  in_progress: '#f59e0b', review: '#f59e0b', active: '#f59e0b',
  resolved: '#10b981', closed: '#6b7280', completed: '#10b981',
  approved: '#10b981', paid: '#10b981',
  scheduled: '#3b82f6', new: '#3b82f6',
};

const CHART_PALETTE = [
  '#0f172a', '#334155', '#64748b', '#94a3b8', '#cbd5e1',
  '#1e40af', '#2563eb', '#3b82f6', '#93c5fd',
];

// ─── Dashboard: utility helpers ───────────────────────────────────────────────

function titleCase(value = '') {
  return String(value).replace(/[_-]/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
}

function formatKpiValue(kpi) {
  const v = kpi.sample_value ?? kpi.value ?? kpi.metric_value;
  if (v === null || v === undefined) return '—';
  const type = (kpi.type || kpi.unit || 'count').toLowerCase();
  if (type === 'percentage') return `${v}%`;
  if (type === 'days' || type === 'duration') return `${v} days`;
  if (type === 'hours') return `${v} hrs`;
  if (type === 'currency') return `$${Number(v).toLocaleString()}`;
  if (typeof v === 'number' && v >= 1000) return Number(v).toLocaleString();
  return String(v);
}

function statusColor(status = '') {
  return STATUS_COLORS[status.toLowerCase().replace(/\s+/g, '_')] || '#94a3b8';
}

function ageInDays(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000));
}

function safeRows(arr) {
  return Array.isArray(arr) ? arr : [];
}

// ─── Dashboard: normalization layer ──────────────────────────────────────────

function getStores(payload) {
  return (
    payload?.dummy_data_json?.stores ||
    payload?.stores ||
    payload?.generation_json?.stores ||
    {}
  );
}

function normalizeKpis(kpis) {
  return safeRows(kpis).slice(0, 8).map(k => ({
    label: k.label || titleCase(k.key || 'Metric'),
    value: formatKpiValue(k),
    source: k.source_service ? titleCase(k.source_service) : '',
    type: (k.type || 'count').toLowerCase(),
  }));
}

function normalizeTickets(rows) {
  return safeRows(rows).map((r, i) => ({
    id: r.id || r.ticket_id || `ticket-${i + 1}`,
    title: r.title || r.subject || r.name || r.id || 'Untitled',
    status: r.status || 'unknown',
    priority: r.priority || 'normal',
    assignee: r.assignee || r.owner || r.assigned_to || 'Unassigned',
    queue: r.queue || r.department || r.group || r.category || '—',
    createdAt: r.created_at || r.createdAt || r.date_created || null,
  }));
}

function normalizeProjects(rows) {
  return safeRows(rows).map((r, i) => ({
    id: r.id || `proj-${i + 1}`,
    title: r.title || r.name || r.id || 'Untitled',
    status: r.status || 'unknown',
    priority: r.priority || 'normal',
    lead: r.lead || r.owner || r.manager || '—',
    completion: typeof r.completion_pct === 'number' ? r.completion_pct : null,
    dueDate: r.due_date || r.end_date || null,
  }));
}

function normalizeTasks(rows) {
  return safeRows(rows).map((r, i) => ({
    id: r.id || `task-${i + 1}`,
    title: r.title || r.name || 'Untitled',
    status: r.status || 'unknown',
    priority: r.priority || 'normal',
    assignee: r.assignee || r.assigned_to || r.owner || 'Unassigned',
    dueDate: r.due_date || null,
  }));
}

function normalizeEmployees(rows) {
  return safeRows(rows).map((r, i) => ({
    id: r.id || `emp-${i + 1}`,
    name: r.name || r.employee || 'Unknown',
    department: r.department || r.team || '—',
    role: r.job_title || r.role || r.position || '—',
    status: r.status || 'Active',
  }));
}

function buildFrequencyMap(rows, fieldFn) {
  const map = new Map();
  safeRows(rows).forEach(r => {
    const key = titleCase(fieldFn(r) || 'Unknown');
    map.set(key, (map.get(key) || 0) + 1);
  });
  return [...map.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

function buildSumMap(rows, groupFn, valueFn) {
  const map = new Map();
  safeRows(rows).forEach(r => {
    const key = titleCase(groupFn(r) || 'Unknown');
    map.set(key, (map.get(key) || 0) + (Number(valueFn(r)) || 0));
  });
  return [...map.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

function buildQueueData(queues, tickets) {
  if (safeRows(queues).length) {
    return safeRows(queues)
      .map(q => ({
        name: q.name || q.queue || q.label || 'Unknown',
        value: Number(q.ticket_count ?? q.count ?? q.value ?? 0),
      }))
      .filter(q => isFinite(q.value))
      .sort((a, b) => b.value - a.value);
  }
  return buildFrequencyMap(tickets, r => r.queue || r.category || r.department);
}

// ─── Dashboard: SVG chart renderers ──────────────────────────────────────────

function renderBarChart(data, { width = 400, height = 200, maxItems = 8 } = {}) {
  if (!data.length) return '<p class="chart-empty">No data</p>';
  const items = data.slice(0, maxItems);
  const maxVal = Math.max(...items.map(d => d.value), 1);
  const barH = Math.floor((height - 24) / items.length) - 4;
  const labelW = 110;
  const barAreaW = width - labelW - 48;

  const bars = items.map((d, i) => {
    const barW = Math.max(4, Math.round((d.value / maxVal) * barAreaW));
    const y = i * (barH + 4);
    const color = CHART_PALETTE[i % CHART_PALETTE.length];
    return `
      <g transform="translate(0,${y})">
        <text x="${labelW - 6}" y="${barH / 2 + 4}" text-anchor="end"
              font-size="11" fill="#475569"
              style="font-family:inherit">${escapeHtml(String(d.name).slice(0, 14))}</text>
        <rect x="${labelW}" y="0" width="${barW}" height="${barH}"
              rx="4" fill="${color}"></rect>
        <text x="${labelW + barW + 5}" y="${barH / 2 + 4}"
              font-size="11" fill="#0f172a" font-weight="600"
              style="font-family:inherit">${d.value}</text>
      </g>`;
  }).join('');

  const svgH = items.length * (barH + 4) + 4;
  return `<svg viewBox="0 0 ${width} ${svgH}" width="100%" style="overflow:visible">${bars}</svg>`;
}

function renderDonutChart(data, { size = 160, maxSlices = 6 } = {}) {
  if (!data.length) return '<p class="chart-empty">No data</p>';
  const items = data.slice(0, maxSlices);
  const total = items.reduce((s, d) => s + d.value, 0) || 1;
  const cx = size / 2, cy = size / 2, r = size * 0.38, inner = size * 0.22;

  let angle = -Math.PI / 2;
  const slices = items.map((d, i) => {
    const sweep = (d.value / total) * 2 * Math.PI;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle), y2 = cy + r * Math.sin(angle);
    const xi1 = cx + inner * Math.cos(angle - sweep);
    const yi1 = cy + inner * Math.sin(angle - sweep);
    const xi2 = cx + inner * Math.cos(angle);
    const yi2 = cy + inner * Math.sin(angle);
    const large = sweep > Math.PI ? 1 : 0;
    const color = CHART_PALETTE[i % CHART_PALETTE.length];
    return `<path d="M${xi1} ${yi1} L${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2}
                     L${xi2} ${yi2} A${inner} ${inner} 0 ${large} 0 ${xi1} ${yi1}Z"
                  fill="${color}" stroke="white" stroke-width="1.5">
              <title>${escapeHtml(d.name)}: ${d.value}</title>
            </path>`;
  }).join('');

  const legend = items.map((d, i) => `
    <div class="chart-legend-row">
      <span class="chart-legend-dot" style="background:${CHART_PALETTE[i % CHART_PALETTE.length]}"></span>
      <span class="chart-legend-label">${escapeHtml(d.name)}</span>
      <span class="chart-legend-val">${d.value}</span>
    </div>`).join('');

  return `
    <div class="chart-donut-wrap">
      <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${slices}</svg>
      <div class="chart-legend">${legend}</div>
    </div>`;
}

function renderProgressBars(data, { maxItems = 6 } = {}) {
  if (!data.length) return '<p class="chart-empty">No data</p>';
  const items = data.slice(0, maxItems);
  const maxVal = Math.max(...items.map(d => d.value), 1);
  return items.map(d => {
    const pct = Math.round((d.value / maxVal) * 100);
    return `
      <div class="prog-row">
        <div class="prog-label-row">
          <span class="prog-name">${escapeHtml(d.name)}</span>
          <span class="prog-val">${d.value}</span>
        </div>
        <div class="prog-track"><div class="prog-fill" style="width:${pct}%"></div></div>
      </div>`;
  }).join('');
}

// ─── Dashboard: section renderers ────────────────────────────────────────────

function renderStatCards(kpis) {
  if (!kpis.length) return '';
  return `
    <div class="exec-kpi-grid">
      ${kpis.map(k => `
        <div class="exec-kpi-card">
          <div class="exec-kpi-label">${escapeHtml(k.label)}</div>
          <div class="exec-kpi-value">${escapeHtml(k.value)}</div>
          ${k.source ? `<div class="exec-kpi-source">${escapeHtml(k.source)}</div>` : ''}
        </div>`).join('')}
    </div>`;
}

function renderSummaryBar(summary) {
  return `
    <div class="exec-summary-bar">
      ${summary.map(s => `
        <div class="exec-summary-item">
          <div class="exec-summary-label">${escapeHtml(s.label)}</div>
          <div class="exec-summary-value">${escapeHtml(String(s.value))}</div>
        </div>`).join('')}
    </div>`;
}

function renderTicketsSection(tickets) {
  if (!tickets.length) return '';
  const statusDist = buildFrequencyMap(tickets, r => r.status);
  const priorityDist = buildFrequencyMap(tickets, r => r.priority);
  const sorted = [...tickets]
    .sort((a, b) => {
      const ai = PRIORITY_ORDER.indexOf(a.priority.toLowerCase());
      const bi = PRIORITY_ORDER.indexOf(b.priority.toLowerCase());
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })
    .slice(0, 8)
    .map(t => {
      const age = ageInDays(t.createdAt);
      const sColor = statusColor(t.status);
      return `
        <tr>
          <td><div class="tbl-title">${escapeHtml(t.title)}</div>
              <div class="tbl-sub">${escapeHtml(t.id)}</div></td>
          <td>${escapeHtml(t.queue)}</td>
          <td><span class="status-pill" style="background:${sColor}1a;color:${sColor};border-color:${sColor}33">
                ${escapeHtml(titleCase(t.status))}</span></td>
          <td><span class="priority-chip priority-${t.priority.toLowerCase()}">
                ${escapeHtml(titleCase(t.priority))}</span></td>
          <td>${escapeHtml(t.assignee)}</td>
          <td>${age !== null ? `${age}d` : '—'}</td>
        </tr>`;
    }).join('');

  return `
    <div class="exec-section-grid exec-grid-2col">
      <div class="exec-card">
        <div class="exec-card-head"><span>Status Distribution</span></div>
        ${renderDonutChart(statusDist, { size: 150, maxSlices: 6 })}
      </div>
      <div class="exec-card">
        <div class="exec-card-head"><span>Priority Profile</span></div>
        ${renderProgressBars(priorityDist)}
      </div>
    </div>
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>Tickets — by Priority</span>
        <span class="exec-card-sub">${tickets.length} total</span></div>
      <div class="tbl-scroll">
        <table class="exec-table">
          <thead><tr>
            <th>Title</th><th>Queue</th><th>Status</th>
            <th>Priority</th><th>Assignee</th><th>Age</th>
          </tr></thead>
          <tbody>${sorted}</tbody>
        </table>
      </div>
    </div>`;
}

function renderQueuesSection(queues) {
  if (!queues.length) return '';
  return `
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>Queue Backlog</span>
        <span class="exec-card-sub">${queues.length} queues</span></div>
      ${renderBarChart(queues, { height: Math.max(120, queues.length * 32) })}
    </div>`;
}

function renderProjectsSection(projects) {
  if (!projects.length) return '';
  const statusDist = buildFrequencyMap(projects, r => r.status);
  const rows = projects.slice(0, 6).map(p => {
    const sColor = statusColor(p.status);
    const bar = p.completion !== null
      ? `<div class="proj-prog-track"><div class="proj-prog-fill" style="width:${p.completion}%"></div></div>
         <span class="proj-pct">${p.completion}%</span>`
      : '—';
    return `
      <tr>
        <td><div class="tbl-title">${escapeHtml(p.title)}</div>
            <div class="tbl-sub">${escapeHtml(p.id)}</div></td>
        <td><span class="status-pill" style="background:${sColor}1a;color:${sColor};border-color:${sColor}33">
              ${escapeHtml(titleCase(p.status))}</span></td>
        <td><span class="priority-chip priority-${p.priority.toLowerCase()}">
              ${escapeHtml(titleCase(p.priority))}</span></td>
        <td>${escapeHtml(p.lead)}</td>
        <td><div class="proj-prog-wrap">${bar}</div></td>
        <td>${p.dueDate ? escapeHtml(p.dueDate) : '—'}</td>
      </tr>`;
  }).join('');

  return `
    <div class="exec-section-grid exec-grid-2col">
      <div class="exec-card">
        <div class="exec-card-head"><span>Project Status Mix</span></div>
        ${renderDonutChart(statusDist, { size: 150 })}
      </div>
      <div class="exec-card">
        <div class="exec-card-head"><span>Status Breakdown</span></div>
        ${renderProgressBars(statusDist)}
      </div>
    </div>
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>Projects</span>
        <span class="exec-card-sub">${projects.length} total</span></div>
      <div class="tbl-scroll">
        <table class="exec-table">
          <thead><tr>
            <th>Title</th><th>Status</th><th>Priority</th>
            <th>Lead</th><th>Progress</th><th>Due</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderTasksSection(tasks) {
  if (!tasks.length) return '';
  const statusDist = buildFrequencyMap(tasks, r => r.status);
  const assigneeDist = buildFrequencyMap(tasks, r => r.assignee).slice(0, 6);
  const rows = tasks.slice(0, 8).map(t => {
    const sColor = statusColor(t.status);
    return `
      <tr>
        <td>${escapeHtml(t.title)}</td>
        <td><span class="status-pill" style="background:${sColor}1a;color:${sColor};border-color:${sColor}33">
              ${escapeHtml(titleCase(t.status))}</span></td>
        <td><span class="priority-chip priority-${t.priority.toLowerCase()}">
              ${escapeHtml(titleCase(t.priority))}</span></td>
        <td>${escapeHtml(t.assignee)}</td>
        <td>${t.dueDate ? escapeHtml(t.dueDate) : '—'}</td>
      </tr>`;
  }).join('');

  return `
    <div class="exec-section-grid exec-grid-2col">
      <div class="exec-card">
        <div class="exec-card-head"><span>Task Status Mix</span></div>
        ${renderProgressBars(statusDist)}
      </div>
      <div class="exec-card">
        <div class="exec-card-head"><span>Top Assignees by Load</span></div>
        ${renderProgressBars(assigneeDist)}
      </div>
    </div>
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>Tasks</span>
        <span class="exec-card-sub">${tasks.length} total</span></div>
      <div class="tbl-scroll">
        <table class="exec-table">
          <thead><tr>
            <th>Title</th><th>Status</th><th>Priority</th><th>Assignee</th><th>Due</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderEmployeesSection(employees) {
  if (!employees.length) return '';
  const deptDist = buildFrequencyMap(employees, r => r.department);
  const statusDist = buildFrequencyMap(employees, r => r.status);
  const rows = employees.slice(0, 8).map(e => {
    const sColor = statusColor(e.status);
    return `
      <tr>
        <td>${escapeHtml(e.name)}</td>
        <td>${escapeHtml(e.department)}</td>
        <td>${escapeHtml(e.role)}</td>
        <td><span class="status-pill" style="background:${sColor}1a;color:${sColor};border-color:${sColor}33">
              ${escapeHtml(e.status)}</span></td>
      </tr>`;
  }).join('');

  return `
    <div class="exec-section-grid exec-grid-2col">
      <div class="exec-card">
        <div class="exec-card-head"><span>Headcount by Department</span></div>
        ${renderBarChart(deptDist, { height: Math.max(100, deptDist.length * 28) })}
      </div>
      <div class="exec-card">
        <div class="exec-card-head"><span>Workforce Status</span></div>
        ${renderDonutChart(statusDist, { size: 140 })}
      </div>
    </div>
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>Employees</span>
        <span class="exec-card-sub">${employees.length} total</span></div>
      <div class="tbl-scroll">
        <table class="exec-table">
          <thead><tr><th>Name</th><th>Department</th><th>Role</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderGenericListSection(storeKey, rows) {
  if (!rows.length) return '';
  const first = rows[0];
  const headers = Object.keys(first).filter(h => h !== 'id').slice(0, 7);
  const title = titleCase(storeKey);

  const statusKey = headers.find(h => h === 'status');
  const numericKeys = headers.filter(h => typeof first[h] === 'number');
  let chartHtml = '';

  if (statusKey) {
    const dist = buildFrequencyMap(rows, r => r[statusKey]);
    if (dist.length > 1) {
      chartHtml = `
        <div class="exec-section-grid exec-grid-2col" style="margin-bottom:16px">
          <div class="exec-card">
            <div class="exec-card-head"><span>${title} by Status</span></div>
            ${renderDonutChart(dist, { size: 140 })}
          </div>
          ${numericKeys.length ? `
          <div class="exec-card">
            <div class="exec-card-head"><span>${titleCase(numericKeys[0])} Summary</span></div>
            ${renderProgressBars(buildSumMap(rows, r => r[statusKey] || 'Unknown', r => r[numericKeys[0]]))}
          </div>` : '<div></div>'}
        </div>`;
    }
  }

  const tableRows = rows.slice(0, 10).map(row => `
    <tr>${headers.map(h => {
      const val = row[h];
      if (h === 'status') {
        const sColor = statusColor(String(val || ''));
        return `<td><span class="status-pill" style="background:${sColor}1a;color:${sColor};border-color:${sColor}33">
                  ${escapeHtml(titleCase(String(val ?? '')))}
                </span></td>`;
      }
      if (typeof val === 'number' && String(h).includes('amount') || String(h).includes('value') || String(h).includes('revenue')) {
        return `<td class="tbl-num">$${Number(val).toLocaleString()}</td>`;
      }
      return `<td>${escapeHtml(String(val ?? ''))}</td>`;
    }).join('')}</tr>`).join('');

  return `
    ${chartHtml}
    <div class="exec-card exec-card-full">
      <div class="exec-card-head"><span>${title}</span>
        <span class="exec-card-sub">${rows.length} records</span></div>
      <div class="tbl-scroll">
        <table class="exec-table">
          <thead><tr>${headers.map(h => `<th>${escapeHtml(titleCase(h))}</th>`).join('')}</tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    </div>`;
}

// ─── Dashboard: v2 tenant-provisioning manifest renderer ─────────────────────

function pickV2Manifest(payload) {
  if (!payload) return null;
  const candidates = [
    payload,
    payload.dummy_data_json,
    payload.generation_json,
    payload.manifest,
    payload.tenant_manifest,
  ];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object') continue;
    const tenant = candidate.tenant;
    if (!tenant || typeof tenant !== 'object') continue;
    const looksV2 =
      (candidate.tickets && Array.isArray(candidate.tickets.queues)) ||
      (candidate.projects && Array.isArray(candidate.projects.projects)) ||
      (candidate.dashboard && Array.isArray(candidate.dashboard.dashboards)) ||
      (candidate.kpi && Array.isArray(candidate.kpi.kpis)) ||
      (candidate.hr_hub && Array.isArray(candidate.hr_hub.employees));
    if (looksV2) return candidate;
  }
  return null;
}

function renderTpItemList(items) {
  if (!items || !items.length) {
    return `<p class="tp-list-empty">None selected.</p>`;
  }
  return `
    <ul class="tp-list">
      ${items.map(it => `
        <li class="tp-list-item">
          <span class="tp-list-id">#${escapeHtml(String(it.id ?? ''))}</span>
          <span class="tp-list-name">${escapeHtml(String(it.name ?? '—'))}</span>
        </li>`).join('')}
    </ul>`;
}

function renderTpChipRow(items) {
  if (!items || !items.length) {
    return `<p class="tp-list-empty">None selected.</p>`;
  }
  return `
    <div class="tp-chip-row">
      ${items.map(it => `
        <span class="tp-chip">
          <span class="tp-chip-id">#${escapeHtml(String(it.id ?? ''))}</span>
          ${escapeHtml(String(it.name ?? '—'))}
        </span>`).join('')}
    </div>`;
}

function renderTpKpiGrid(kpis) {
  if (!kpis || !kpis.length) {
    return `<p class="tp-list-empty">None selected.</p>`;
  }
  return `
    <div class="tp-kpi-grid">
      ${kpis.map(k => `
        <div class="tp-kpi-tile">
          <span class="tp-list-id">#${escapeHtml(String(k.id ?? ''))}</span>
          <span class="tp-kpi-name">${escapeHtml(String(k.name ?? '—'))}</span>
        </div>`).join('')}
    </div>`;
}

function levelClass(level = '') {
  const l = String(level).toLowerCase();
  if (l.includes('director')) return 'tp-level-director';
  if (l.includes('manager') || l.includes('lead')) return 'tp-level-manager';
  if (l.includes('staff') || l.includes('analyst') || l.includes('rep')) return 'tp-level-staff';
  return 'tp-level-default';
}

function renderTpEmployeesTable(employees) {
  if (!employees || !employees.length) {
    return `<p class="tp-list-empty">No employees selected.</p>`;
  }
  const rows = employees.map(e => `
    <tr>
      <td>
        <div class="tp-emp-name">${escapeHtml(e.position || e.job_title || '—')}</div>
        <div class="tp-emp-meta">ID #${escapeHtml(String(e.id ?? '—'))} · ${escapeHtml(e.job_title || '')}</div>
      </td>
      <td>${escapeHtml(e.team || '—')}</td>
      <td>${escapeHtml(e.department || '—')}</td>
      <td>${escapeHtml(e.job_type || '—')}</td>
      <td>
        <span class="tp-level ${levelClass(e.job_level)}">
          ${escapeHtml(e.job_level || '—')}
        </span>
      </td>
    </tr>`).join('');

  return `
    <div class="tbl-scroll">
      <table class="tp-emp-table">
        <thead>
          <tr>
            <th>Position</th>
            <th>Team</th>
            <th>Department</th>
            <th>Job Type</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function buildEmployeeLevelSummary(employees) {
  const summary = { director: 0, manager: 0, staff: 0, other: 0 };
  employees.forEach((e) => {
    const level = String(e.job_level || '').toLowerCase();
    if (level.includes('director')) summary.director += 1;
    else if (level.includes('manager') || level.includes('lead')) summary.manager += 1;
    else if (level.includes('staff') || level.includes('analyst') || level.includes('rep')) summary.staff += 1;
    else summary.other += 1;
  });
  return summary;
}

function buildTopDepartmentSummary(employees) {
  const counts = new Map();
  employees.forEach((e) => {
    const dep = e.department || 'Unspecified';
    counts.set(dep, (counts.get(dep) || 0) + 1);
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([name, value]) => ({ name, value }));
}

function renderV2Dashboard(manifest, previewType) {
  const tenant = manifest.tenant || {};
  const queues = (manifest.tickets && manifest.tickets.queues) || [];
  const projects = (manifest.projects && manifest.projects.projects) || [];
  const dashboards = (manifest.dashboard && manifest.dashboard.dashboards) || [];
  const kpis = (manifest.kpi && manifest.kpi.kpis) || [];
  const employees = (manifest.hr_hub && manifest.hr_hub.employees) || [];
  const requestTypes = (manifest.hr_hub && manifest.hr_hub.request_types) || [];
  const schemaVersion = manifest.schema_version || '2.0';
  const generatedAt = manifest.generated_at || '';
  const sessionId = manifest.session_id || '';
  const isEarly = previewType === 'early';
  const companyName = tenant.company_name || 'New Tenant';
  const industryLabel = titleCase(tenant.industry || 'workspace');
  const employeeLevel = buildEmployeeLevelSummary(employees);
  const departmentMix = buildTopDepartmentSummary(employees);

  const heroChips = [
    tenant.size_band && { label: 'Headcount', value: tenant.size_band },
    tenant.primary_region && { label: 'Region', value: tenant.primary_region },
    tenant.locale && { label: 'Locale', value: tenant.locale },
    tenant.timezone && { label: 'Timezone', value: tenant.timezone },
  ].filter(Boolean);

  return `
    <div class="tp-dashboard">
      <div class="tp-hero">
        <div class="tp-hero-badges">
          <span class="tp-badge tp-badge-primary">Tenant Manifest</span>
          <span class="tp-badge tp-badge-outline">Schema ${escapeHtml(schemaVersion)}</span>
          <span class="tp-badge tp-badge-outline">${escapeHtml(industryLabel)}</span>
          ${generatedAt ? `<span class="tp-badge tp-badge-outline">${escapeHtml(generatedAt.slice(0, 10))}</span>` : ''}
          ${isEarly ? `<span class="tp-badge tp-badge-warning">Early Preview</span>` : ''}
        </div>
        <h1 class="tp-hero-title">${escapeHtml(companyName)}</h1>
        <p class="tp-hero-sub">
          Provisioning preview — the AI agent picked the right queues, projects, dashboards, KPIs,
          HR request types and employee roster for this org.
        </p>
        <div class="tp-hero-chips">
          ${heroChips.map(c => `
            <span class="tp-hero-chip">
              <span class="chip-label">${escapeHtml(c.label)}</span>
              <strong>${escapeHtml(c.value)}</strong>
            </span>`).join('')}
        </div>
      </div>

      <div class="tp-selection-strip">
        <div class="tp-select-item"><span class="tp-select-key">Queues</span><strong>${queues.length}</strong></div>
        <div class="tp-select-item"><span class="tp-select-key">Projects</span><strong>${projects.length}</strong></div>
        <div class="tp-select-item"><span class="tp-select-key">Dashboards</span><strong>${dashboards.length}</strong></div>
        <div class="tp-select-item"><span class="tp-select-key">KPIs</span><strong>${kpis.length}</strong></div>
        <div class="tp-select-item"><span class="tp-select-key">Employees</span><strong>${employees.length}</strong></div>
        <div class="tp-select-item"><span class="tp-select-key">HR Types</span><strong>${requestTypes.length}</strong></div>
      </div>

      <div class="tp-grid">
        <section class="tp-card tp-card-peach">
          <div class="tp-card-head">
            <h2 class="tp-card-title">Ticket Queues</h2>
            <span class="tp-card-count">${queues.length}</span>
          </div>
          ${renderTpItemList(queues)}
        </section>

        <section class="tp-card tp-card-rose">
          <div class="tp-card-head">
            <h2 class="tp-card-title">Projects</h2>
            <span class="tp-card-count">${projects.length}</span>
          </div>
          ${renderTpItemList(projects)}
        </section>

        <section class="tp-card tp-card-mint">
          <div class="tp-card-head">
            <h2 class="tp-card-title">Dashboards</h2>
            <span class="tp-card-count">${dashboards.length}</span>
          </div>
          ${renderTpItemList(dashboards)}
        </section>
      </div>

      <section class="tp-card tp-card-lavender tp-card-wide">
        <div class="tp-card-head">
          <h2 class="tp-card-title">KPIs</h2>
          <span class="tp-card-count">${kpis.length}</span>
        </div>
        ${renderTpKpiGrid(kpis)}
      </section>

      <section class="tp-card tp-card-sky tp-card-wide">
        <div class="tp-card-head">
          <h2 class="tp-card-title">HR Hub — Employees</h2>
          <span class="tp-card-count">${employees.length}</span>
        </div>
        <div class="tp-employee-mix">
          <span class="tp-level tp-level-director">Director: ${employeeLevel.director}</span>
          <span class="tp-level tp-level-manager">Manager: ${employeeLevel.manager}</span>
          <span class="tp-level tp-level-staff">Staff: ${employeeLevel.staff}</span>
          ${employeeLevel.other ? `<span class="tp-level tp-level-default">Other: ${employeeLevel.other}</span>` : ''}
          ${departmentMix.map(d => `<span class="tp-level tp-level-default">${escapeHtml(d.name)}: ${d.value}</span>`).join('')}
        </div>
        ${renderTpEmployeesTable(employees)}
      </section>

      <section class="tp-card tp-card-yellow tp-card-wide">
        <div class="tp-card-head">
          <h2 class="tp-card-title">HR Request Types</h2>
          <span class="tp-card-count">${requestTypes.length}</span>
        </div>
        ${renderTpChipRow(requestTypes)}
      </section>

      <div class="tp-deploy-row">
        <button id="deployBtn" class="success-btn" ${isEarly ? 'disabled' : ''}>
          ${isEarly ? 'Confirm Bundle to Deploy' : 'Finalize &amp; Deploy Tenant'}
        </button>
      </div>
    </div>`;
}

// ─── Dashboard: root export ───────────────────────────────────────────────────

export function renderDashboard(payload, previewType) {
  if (!payload) {
    return `
      <div class="dashboard-empty dashboard-empty-card">
        <div class="dashboard-empty-icon">✦</div>
        <h3>Your preview space is ready</h3>
        <p>Run Generate Preview from chat to load your dashboard and sample data.</p>
      </div>`;
  }

  const v2Manifest = pickV2Manifest(payload);
  if (v2Manifest) {
    return renderV2Dashboard(v2Manifest, previewType);
  }

  if (!payload.dummy_data_json) {
    return `
      <div class="dashboard-empty dashboard-empty-card">
        <div class="dashboard-empty-icon">✦</div>
        <h3>Your preview space is ready</h3>
        <p>Run Generate Preview from chat to load your dashboard and sample data.</p>
      </div>`;
  }

  const stores = getStores(payload);
  const displayName = payload.display_name || titleCase(payload.bundle_key || 'Operations');
  const bundleName = titleCase(payload.bundle_key || 'dashboard');
  const badgeLabel = previewType === 'early' ? 'Early Preview' : 'Preview Mode';

  const kpis = normalizeKpis(stores.kpis);
  const tickets = normalizeTickets(stores.tickets);
  const projects = normalizeProjects(stores.projects);
  const tasks = normalizeTasks(stores.tasks);
  const employees = normalizeEmployees(stores.employees);
  const queues = buildQueueData(stores.queues, tickets);

  const processedKeys = new Set(['kpis', 'tickets', 'projects', 'tasks', 'employees', 'queues',
    'dashboard_generation_output', 'dashboard_widgets']);

  const extraSections = Object.entries(stores)
    .filter(([k, v]) => !processedKeys.has(k) && !INTERNAL_STORE_KEYS.has(k) && Array.isArray(v) && v.length > 0)
    .map(([k, v]) => renderGenericListSection(k, v))
    .join('');

  const summary = buildSummaryData({ tickets, projects, tasks, employees, queues });

  const disableDeploy = previewType === 'early';

  return `
    <div class="exec-dashboard">
      <div class="exec-header">
        <div class="exec-header-left">
          <div class="exec-badges">
            <span class="exec-badge exec-badge-dark">${escapeHtml(badgeLabel)}</span>
            <span class="exec-badge exec-badge-outline">${escapeHtml(bundleName)}</span>
          </div>
          <h1 class="exec-title">${escapeHtml(displayName)} Dashboard</h1>
        </div>
        ${summary.length ? renderSummaryBar(summary) : ''}
      </div>

      ${renderStatCards(kpis)}
      ${queues.length ? renderQueuesSection(queues) : ''}
      ${tickets.length ? renderTicketsSection(tickets) : ''}
      ${projects.length ? renderProjectsSection(projects) : ''}
      ${tasks.length ? renderTasksSection(tasks) : ''}
      ${employees.length ? renderEmployeesSection(employees) : ''}
      ${extraSections}

      <div class="exec-deploy-row">
        <button id="deployBtn" class="success-btn" ${disableDeploy ? 'disabled' : ''}>
          ${disableDeploy ? 'Confirm Bundle to Deploy' : 'Finalize &amp; Deploy App'}
        </button>
      </div>
    </div>`;
}

function buildSummaryData({ tickets, projects, tasks, employees, queues }) {
  const items = [];
  if (queues.length) {
    const total = queues.reduce((s, q) => s + q.value, 0);
    items.push({ label: 'Queue Volume', value: total || tickets.length });
    items.push({ label: 'Top Queue', value: queues[0]?.name || '—' });
  } else if (tickets.length) {
    const open = tickets.filter(t => !['resolved', 'closed'].includes(t.status.toLowerCase())).length;
    items.push({ label: 'Open Tickets', value: open });
  }
  if (projects.length) {
    const active = projects.filter(p => p.status.toLowerCase() === 'active').length;
    items.push({ label: 'Active Projects', value: active });
  }
  if (employees.length) {
    items.push({ label: 'Employees', value: employees.length });
  }
  if (tasks.length) {
    const open = tasks.filter(t => !['resolved', 'closed', 'completed'].includes(t.status.toLowerCase())).length;
    items.push({ label: 'Open Tasks', value: open });
  }
  return items.slice(0, 4);
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
