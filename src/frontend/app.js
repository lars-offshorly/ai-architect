import {
  confirmSession,
  fetchMetadata,
  generateEarlyPreview,
  replySession,
  startSession,
} from '/static/api.js';
import {
  appendMessage,
  renderClassification,
  renderExtraction,
  renderFooter,
  renderMetadata,
  renderPipeline,
} from '/static/components.js';

const state = {
  sessionId: '',
  turnCount: 0,
  lastStatus: '',
  previewType: null,
  warning: null,
  debug: null,
  classification: null,
  recommendation: null,
  metadata: null,
  metadataError: '',
};

const els = {
  chatLog: document.getElementById('chatLog'),
  messageInput: document.getElementById('messageInput'),
  bundleInput: document.getElementById('bundleInput'),
  intentInput: document.getElementById('intentInput'),
  startBtn: document.getElementById('startBtn'),
  replyBtn: document.getElementById('replyBtn'),
  confirmBtn: document.getElementById('confirmBtn'),
  earlyPreviewBtn: document.getElementById('earlyPreviewBtn'),
  tabs: document.getElementById('tabs'),
  pipelinePanel: document.getElementById('tab-pipeline'),
  extractionPanel: document.getElementById('tab-extraction'),
  classificationPanel: document.getElementById('tab-classification'),
  metadataPanel: document.getElementById('tab-metadata'),
  footer: document.getElementById('footer'),
};

bindEvents();
refreshPanels();
appendMessage(els.chatLog, 'system', 'Ready. Start a session to inspect pipeline state.');

function bindEvents() {
  els.startBtn.addEventListener('click', handleStartSession);
  els.replyBtn.addEventListener('click', handleReply);
  els.confirmBtn.addEventListener('click', handleConfirm);
  els.earlyPreviewBtn.addEventListener('click', handleEarlyPreview);
  els.tabs.addEventListener('click', handleTabSwitch);
}

async function handleStartSession() {
  const message = els.messageInput.value.trim();
  if (!message) return;

  try {
    const body = {
      message,
      preselected_bundle_key: normalizeOptional(els.bundleInput.value),
      preselected_intent: normalizeOptional(els.intentInput.value),
    };
    const response = await startSession(body);
    applyTurnResponse(response);
    appendMessage(els.chatLog, 'user', message);
    appendMessage(els.chatLog, 'assistant', response.message || response.question || response.status);
  } catch (error) {
    appendMessage(els.chatLog, 'error', error.message);
  }
}

async function handleReply() {
  if (!state.sessionId) {
    appendMessage(els.chatLog, 'error', 'Start a session first.');
    return;
  }
  const message = els.messageInput.value.trim();
  if (!message) return;

  try {
    const response = await replySession(state.sessionId, {
      message,
      force_preview: false,
    });
    applyTurnResponse(response);
    appendMessage(els.chatLog, 'user', message);
    appendMessage(els.chatLog, 'assistant', response.message || response.question || response.status);
  } catch (error) {
    appendMessage(els.chatLog, 'error', error.message);
  }
}

async function handleConfirm() {
  if (!state.sessionId) {
    appendMessage(els.chatLog, 'error', 'Start a session first.');
    return;
  }
  try {
    const response = await confirmSession(state.sessionId, true);
    applyTurnResponse(response);
    appendMessage(els.chatLog, 'system', 'Bundle confirmed.');
  } catch (error) {
    appendMessage(els.chatLog, 'error', error.message);
  }
}

async function handleEarlyPreview() {
  if (!state.sessionId) {
    appendMessage(els.chatLog, 'error', 'Start a session first.');
    return;
  }
  try {
    const payload = await generateEarlyPreview(state.sessionId);
    appendMessage(els.chatLog, 'system', `Early preview generated for bundle=${payload.bundle_key}`);
    if (payload.warning) {
      appendMessage(els.chatLog, 'warning', payload.warning);
    }
  } catch (error) {
    appendMessage(els.chatLog, 'error', error.message);
  }
}

function handleTabSwitch(event) {
  const button = event.target.closest('button[data-tab]');
  if (!button) return;
  const tab = button.dataset.tab;

  document.querySelectorAll('.tab').forEach((el) => el.classList.remove('is-active'));
  document.querySelectorAll('.tab-panel').forEach((el) => el.classList.remove('is-active'));

  button.classList.add('is-active');
  document.getElementById(`tab-${tab}`).classList.add('is-active');
}

async function applyTurnResponse(response) {
  state.sessionId = response.session_id || state.sessionId;
  state.turnCount += 1;
  state.lastStatus = response.status || state.lastStatus;
  state.previewType = response.preview_type || null;
  state.warning = response.warning || null;
  state.debug = response.debug || null;
  state.classification = response.classification || null;
  state.recommendation = response.recommendation || null;

  await hydrateMetadata();
  refreshPanels();
}

async function hydrateMetadata() {
  const bundleKey = state.recommendation?.primary_bundle_key || state.classification?.top_bundle_key;
  if (!bundleKey) {
    state.metadata = null;
    state.metadataError = '';
    return;
  }

  try {
    state.metadata = await fetchMetadata(bundleKey);
    state.metadataError = '';
  } catch (error) {
    state.metadata = null;
    state.metadataError = error.message;
  }
}

function refreshPanels() {
  renderPipeline(els.pipelinePanel, state);
  renderExtraction(els.extractionPanel, state.debug);
  renderClassification(els.classificationPanel, state.classification);
  renderMetadata(els.metadataPanel, state.metadata, state.metadataError);
  renderFooter(els.footer, state);
}

function normalizeOptional(value) {
  const trimmed = value.trim();
  return trimmed.length ? trimmed : null;
}
