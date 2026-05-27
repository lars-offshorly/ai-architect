export async function startSession(payload) {
  return requestJson('/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function replySession(sessionId, payload) {
  return requestJson(`/sessions/${sessionId}/reply`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function confirmSession(sessionId, confirmed = true) {
  return requestJson(`/sessions/${sessionId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ confirmed }),
  });
}

export async function generatePreview(sessionId) {
  return requestJson(`/sessions/${sessionId}/preview`, {
    method: 'POST',
  });
}

export async function generateEarlyPreview(sessionId) {
  return requestJson(`/sessions/${sessionId}/preview/early`, {
    method: 'POST',
  });
}

export async function editPreview(sessionId, currentPreview, instruction) {
  return requestJson(`/sessions/${sessionId}/preview/edit`, {
    method: 'POST',
    body: JSON.stringify({
      current_preview: currentPreview,
      instruction,
    }),
  });
}

export async function generateApp(sessionId, v2Manifest) {
  return requestJson(`/sessions/${sessionId}/app`, {
    method: 'POST',
    body: JSON.stringify({
      manifest: v2Manifest,
    }),
  });
}

export async function fetchMetadata(bundleKey) {
  return requestJson(`/bundles/${bundleKey}/metadata`, {
    method: 'GET',
  });
}

async function requestJson(path, options) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText;
    throw new Error(detail || `Request failed (${response.status})`);
  }

  return body;
}
