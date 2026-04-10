import {
  startSession,
  replySession,
  confirmSession,
  generatePreview,
  generateApp,
} from './api.js';
import {
  renderMessage,
  renderBundleCard,
  renderDashboard,
  renderPipelineStatus,
  renderThinkingIndicator,
} from './components.js';

const state = {
  sessionId: '',
  lastStatus: 'idle', // idle, awaiting_input, pending_confirmation, ready_for_preview, complete
  recommendation: null,
  classification: null,
  previewPayload: null,
  isProcessing: false,
  statusInterval: null,
};

const STATUS_MESSAGES = [
  "Analyzing your request...",
  "Extracting requirements...",
  "Classifying bundle candidates...",
  "Thinking about your thoughts...",
  "Checking for compatibility...",
  "hmmm, i love my job...",
  "Almost there...",
  "Mapping architecture...",
  "Personalizing modules...",
];

const els = {
  chatLog: document.getElementById('chatLog'),
  messageInput: document.getElementById('messageInput'),
  sendBtn: document.getElementById('sendBtn'),
  previewPanel: document.getElementById('previewPanel'),
  pipelineContainer: document.getElementById('pipelineContainer'),
};

// Initialize
bindEvents();
appendSystemMessage("Hello! I'm AI Architect. Tell me what kind of app or workspace you want to build.");

function bindEvents() {
  els.sendBtn.addEventListener('click', handleSendMessage);
  els.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Global delegation for dynamic buttons
  document.addEventListener('click', async (e) => {
    if (e.target.id === 'confirmBundleBtn') {
      await handleConfirmBundle(true);
    } else if (e.target.id === 'generatePreviewBtn') {
      await handleGeneratePreview();
    } else if (e.target.id === 'deployBtn') {
      await handleDeployApp();
    } else if (e.target.classList.contains('suggestion-chip')) {
      const msg = e.target.getAttribute('data-msg');
      els.messageInput.value = msg;
      handleSendMessage();
    }
  });
}

function startThinking() {
  let index = 0;
  // Initial thinking indicator
  els.chatLog.insertAdjacentHTML('beforeend', renderThinkingIndicator(STATUS_MESSAGES[0]));
  scrollToBottom();

  state.statusInterval = setInterval(() => {
    index = (index + 1) % STATUS_MESSAGES.length;
    const indicator = document.getElementById('thinkingIndicator');
    if (indicator) {
      const textEl = indicator.querySelector('.thinking-text');
      if (textEl) textEl.textContent = STATUS_MESSAGES[index];
    }
  }, 2500);
}

function stopThinking() {
  if (state.statusInterval) {
    clearInterval(state.statusInterval);
    state.statusInterval = null;
  }
  const indicator = document.getElementById('thinkingIndicator');
  if (indicator) indicator.remove();
}

async function handleSendMessage() {
  const message = els.messageInput.value.trim();
  if (!message || state.isProcessing) return;

  els.messageInput.value = '';
  appendUserMessage(message);
  setProcessing(true);
  startThinking();

  try {
    let response;
    if (!state.sessionId) {
      // Step 1: Start Conversation
      response = await startSession({ message });
    } else {
      // Step 2: Chat Loop
      response = await replySession(state.sessionId, { message });
    }
    
    stopThinking();
    applyTurnResponse(response);
  } catch (error) {
    stopThinking();
    appendErrorMessage(error.message);
  } finally {
    setProcessing(false);
  }
}

async function handleConfirmBundle(confirmed) {
  if (!state.sessionId || state.isProcessing) return;
  setProcessing(true);
  startThinking();

  try {
    // Step 3: Bundle Confirmation
    const response = await confirmSession(state.sessionId, confirmed);
    stopThinking();
    applyTurnResponse(response);
    
    if (confirmed) {
      appendSystemMessage("Great! Bundle confirmed. I'm ready to generate your preview data.");
      addActionButton('Generate Preview', 'generatePreviewBtn');
    }
  } catch (error) {
    stopThinking();
    appendErrorMessage(error.message);
  } finally {
    setProcessing(false);
  }
}

async function handleGeneratePreview() {
  if (!state.sessionId || state.isProcessing) return;
  setProcessing(true);
  startThinking();

  try {
    // Step 4: Preview Generation
    const payload = await generatePreview(state.sessionId);
    stopThinking();
    state.previewPayload = payload;
    state.lastStatus = 'preview_ready';
    
    refreshUI();
    appendSystemMessage("Preview generated! Check out the dashboard on the right.");
  } catch (error) {
    stopThinking();
    appendErrorMessage(error.message);
  } finally {
    setProcessing(false);
  }
}

async function handleDeployApp() {
  if (!state.sessionId || !state.previewPayload || state.isProcessing) return;
  setProcessing(true);
  startThinking();

  try {
    // Step 5: Final Delivery
    const finalPayload = await generateApp(state.sessionId, state.previewPayload.dummy_data_json);
    stopThinking();
    state.lastStatus = 'complete';
    
    appendSystemMessage("Success! Your workspace is ready. Manifest generated.");
    console.log("Final App Payload:", finalPayload);
    
    // Disable deploy button in dashboard
    refreshUI();
  } catch (error) {
    stopThinking();
    appendErrorMessage(error.message);
  } finally {
    setProcessing(false);
  }
}

function applyTurnResponse(response) {
  state.sessionId = response.session_id || state.sessionId;
  state.lastStatus = response.status;
  state.recommendation = response.recommendation;
  state.classification = response.classification;

  if (response.message || response.question) {
    appendAssistantMessage(response.message || response.question);
  }

  if (state.lastStatus === 'pending_confirmation') {
    appendCustomHTML(renderBundleCard(state.recommendation));
  } else if (state.lastStatus === 'ready_for_preview') {
    addActionButton('Generate Preview', 'generatePreviewBtn');
  }

  refreshUI();
}

function refreshUI() {
  els.pipelineContainer.innerHTML = renderPipelineStatus(state);
  els.previewPanel.innerHTML = renderDashboard(state.previewPayload);
  
  if (state.lastStatus === 'complete') {
    const deployBtn = document.getElementById('deployBtn');
    if (deployBtn) {
      deployBtn.disabled = true;
      deployBtn.textContent = 'App Deployed';
    }
  }
}

function setProcessing(processing) {
  state.isProcessing = processing;
  els.sendBtn.disabled = processing;
  els.messageInput.disabled = processing;
  if (processing) {
    els.sendBtn.textContent = '...';
  } else {
    els.sendBtn.textContent = 'Send';
  }
}

// Helper methods for chat display
function appendUserMessage(content) {
  els.chatLog.insertAdjacentHTML('beforeend', renderMessage('user', content));
  scrollToBottom();
}

function appendAssistantMessage(content) {
  els.chatLog.insertAdjacentHTML('beforeend', renderMessage('assistant', content));
  scrollToBottom();
}

function appendSystemMessage(content) {
  els.chatLog.insertAdjacentHTML('beforeend', renderMessage('system', content));
  scrollToBottom();
}

function appendErrorMessage(content) {
  els.chatLog.insertAdjacentHTML('beforeend', `
    <div class="msg-bubble msg-error">
      <div class="msg-role">Error</div>
      <div class="msg-content">${content}</div>
    </div>
  `);
  scrollToBottom();
}

function appendCustomHTML(html) {
  els.chatLog.insertAdjacentHTML('beforeend', html);
  scrollToBottom();
}

function addActionButton(label, id) {
  appendCustomHTML(`
    <div class="msg-bubble msg-assistant action-bubble">
      <button id="${id}" class="primary-btn">${label}</button>
    </div>
  `);
}

function scrollToBottom() {
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}
