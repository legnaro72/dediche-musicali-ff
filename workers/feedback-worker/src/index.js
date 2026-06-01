const REACTION_KEYS = ['down', 'like', 'heart', 'sun'];

function allowedCorsOrigin(request, env = {}) {
  const requestOrigin = request?.headers?.get('origin') || '';
  const configured = String(env.ALLOWED_ORIGINS || env.ALLOWED_ORIGIN || '*')
    .split(',')
    .map(origin => origin.trim())
    .filter(Boolean);
  if (configured.includes('*')) return '*';
  if (requestOrigin && configured.includes(requestOrigin)) return requestOrigin;
  return configured[0] || '*';
}

function jsonResponse(payload, status = 200, env = {}, request = null) {
  const origin = allowedCorsOrigin(request, env);
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': origin,
      'access-control-allow-methods': 'GET, POST, OPTIONS',
      'access-control-allow-headers': 'content-type',
      'cache-control': 'no-store',
      vary: 'Origin',
    },
  });
}

function normalizeReactions(value) {
  const source = value && typeof value === 'object' ? value : {};
  return REACTION_KEYS.reduce((acc, key) => {
    const count = Number(source[key] || 0);
    acc[key] = Number.isFinite(count) ? Math.max(0, Math.trunc(count)) : 0;
    return acc;
  }, {});
}

function normalizeText(value, maxLength = 120) {
  const text = String(value || '').trim();
  return text.length <= maxLength ? text : text.slice(0, maxLength);
}

function userFromPayload(payload) {
  const userId = normalizeText(payload.userId || payload.user_id || '', 160);
  if (!userId) throw new Error('userId obbligatorio per salvare feedback nominale.');
  const fallbackName = [payload.nome, payload.cognome].filter(Boolean).join(' ').trim();
  const userName = normalizeText(payload.userName || payload.displayName || fallbackName || 'Utente', 120);
  return { userId, userName };
}

function normalizeVotes(value) {
  const list = Array.isArray(value) ? value : [];
  return list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      value: Number(item?.value),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userId && Number.isInteger(item.value) && item.value >= 1 && item.value <= 10);
}

function normalizeThoughts(value) {
  const list = Array.isArray(value) ? value : [];
  return list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      text: String(item?.text || '').trim(),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userId && item.text);
}

function normalizeReactionEntries(value) {
  const list = Array.isArray(value) ? value : [];
  return list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      value: String(item?.value || item?.reaction || '').trim(),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userId && REACTION_KEYS.includes(item.value));
}

function averageVote(votes) {
  if (!votes.length) return null;
  const total = votes.reduce((sum, item) => sum + Number(item.value || 0), 0);
  return Math.round((total / votes.length) * 10) / 10;
}

function aggregateReactionEntries(entries) {
  const counts = normalizeReactions({});
  entries.forEach(item => {
    if (REACTION_KEYS.includes(item.value)) counts[item.value] += 1;
  });
  return counts;
}

function syncDerivedFeedbackFields(dedication) {
  const hasNominalReactions = Array.isArray(dedication.reactionEntries);
  const votes = normalizeVotes(dedication.votes);
  const thoughts = normalizeThoughts(dedication.thoughts);
  const reactionEntries = normalizeReactionEntries(dedication.reactionEntries);
  const legacyVote = Number(dedication.votoPilly);
  if (!votes.length && Number.isInteger(legacyVote) && legacyVote >= 1 && legacyVote <= 10) {
    votes.push({
      userId: 'legacy-feedback',
      userName: 'Storico',
      value: legacyVote,
      createdAt: String(dedication.updated_at || ''),
      updatedAt: String(dedication.updated_at || ''),
    });
  }
  const legacyThought = String(dedication.pensieroPilly || '').trim();
  if (!thoughts.length && legacyThought) {
    thoughts.push({
      userId: 'legacy-feedback',
      userName: 'Storico',
      text: legacyThought,
      createdAt: String(dedication.updated_at || ''),
      updatedAt: String(dedication.updated_at || ''),
    });
  }
  dedication.votes = votes;
  dedication.thoughts = thoughts;
  dedication.reactionEntries = reactionEntries;
  dedication.votoPilly = averageVote(votes);
  dedication.pensieroPilly = thoughts.map(item => `[${item.userName}] ${item.text}`).join('\n\n');
  dedication.reactions = hasNominalReactions
    ? aggregateReactionEntries(reactionEntries)
    : normalizeReactions(dedication.reactions);
  return dedication;
}

function ensureFeedbackFields(dedication) {
  const updated = {
    ...dedication,
    votoPilly: dedication.votoPilly ?? null,
    pensieroPilly: dedication.pensieroPilly ?? '',
    reactions: normalizeReactions(dedication.reactions),
    votes: normalizeVotes(dedication.votes),
    thoughts: normalizeThoughts(dedication.thoughts),
  };
  if (Array.isArray(dedication.reactionEntries)) {
    updated.reactionEntries = normalizeReactionEntries(dedication.reactionEntries);
  }
  return syncDerivedFeedbackFields(updated);
}

function feedbackPayload(dedication) {
  const normalized = ensureFeedbackFields(dedication);
  return {
    id: normalized.id || '',
    date: normalized.date || '',
    title: normalized.song_title || '',
    artist: normalized.artist || '',
    votoPilly: normalized.votoPilly,
    pensieroPilly: normalized.pensieroPilly || '',
    reactions: normalizeReactions(normalized.reactions),
    votes: normalized.votes || [],
    thoughts: normalized.thoughts || [],
    reactionEntries: normalized.reactionEntries || [],
    updated_at: normalized.updated_at || '',
  };
}

function requiredEnv(env, key) {
  const value = env[key];
  if (!value) throw new Error(`Secret/variabile mancante: ${key}`);
  return value;
}

function githubHeaders(env) {
  return {
    accept: 'application/vnd.github+json',
    authorization: `Bearer ${requiredEnv(env, 'GITHUB_TOKEN')}`,
    'x-github-api-version': '2022-11-28',
    'user-agent': 'ddgpilli-feedback-worker',
  };
}

function githubRepo(env) {
  return requiredEnv(env, 'GITHUB_REPO');
}

function githubBranch(env) {
  return env.GITHUB_BRANCH || 'main';
}

async function githubRequest(env, path, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${githubRepo(env)}/${path.replace(/^\/+/, '')}`, {
    ...options,
    headers: {
      ...githubHeaders(env),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`GitHub API ${response.status}: ${text}`);
  }
  return response;
}

function decodeBase64Utf8(value) {
  const binary = atob(value.replace(/\s/g, ''));
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
  return new TextDecoder('utf-8').decode(bytes).replace(/^\uFEFF/, '');
}

function encodeBase64Utf8(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  bytes.forEach(byte => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

async function loadDedicationPath(env, repoPath) {
  const response = await githubRequest(
    env,
    `contents/${repoPath}`,
    { method: 'GET', cf: { cacheTtl: 0 }, headers: {} },
  );
  const payload = await response.json();
  const dedication = JSON.parse(decodeBase64Utf8(payload.content));
  return {
    dedication: ensureFeedbackFields(dedication),
    path: payload.path,
    sha: payload.sha,
  };
}

async function listDedicationFiles(env) {
  const response = await githubRequest(
    env,
    `contents/data/dedications?ref=${encodeURIComponent(githubBranch(env))}`,
    { method: 'GET', cf: { cacheTtl: 0 } },
  );
  const items = await response.json();
  return items.filter(item => item.type === 'file' && item.name.endsWith('.json'));
}

async function loadDedicationById(env, dedicationId) {
  if (!dedicationId) throw new Error('dedication_id obbligatorio.');

  const directPath = `data/dedications/${dedicationId}.json`;
  try {
    return await loadDedicationPath(env, `${directPath}?ref=${encodeURIComponent(githubBranch(env))}`);
  } catch {
    // Compatibilita' con file legacy chiamati per data ma con id interno completo.
  }

  const files = await listDedicationFiles(env);
  for (const file of files) {
    const loaded = await loadDedicationPath(env, `${file.path}?ref=${encodeURIComponent(githubBranch(env))}`);
    if (loaded.dedication.id === dedicationId) return loaded;
  }

  throw new Error(`Dedica non trovata: ${dedicationId}`);
}

async function saveDedication(env, loaded, message) {
  const content = encodeBase64Utf8(JSON.stringify(loaded.dedication, null, 2));
  const response = await githubRequest(env, `contents/${loaded.path}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      message,
      content,
      sha: loaded.sha,
      branch: githubBranch(env),
    }),
  });
  await response.json();
  return loaded.dedication;
}

function nowIsoRomeApprox() {
  return new Date().toISOString();
}

function romeDateTimeParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date).reduce((acc, part) => {
    acc[part.type] = part.value;
    return acc;
  }, {});
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour}:${parts.minute}:${parts.second}`,
  };
}

function truncateInput(value, maxLength) {
  const text = String(value || '').trim();
  return text.length <= maxLength ? text : `${text.slice(0, maxLength - 1)}…`;
}

async function dispatchVoteEmail(env, feedback) {
  const workflow = env.VOTE_EMAIL_WORKFLOW_FILE || 'vote-email-notification.yml';
  const when = romeDateTimeParts(new Date());
  const response = await githubRequest(env, `actions/workflows/${workflow}/dispatches`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      ref: githubBranch(env),
      inputs: {
        date: when.date,
        time: when.time,
        score: String(feedback.currentVote ?? feedback.votoPilly ?? ''),
        thought: truncateInput(feedback.currentThought || feedback.pensieroPilly || '', 6000),
        title: truncateInput(feedback.title || '', 200),
        artist: truncateInput(feedback.artist || '', 200),
      },
    }),
  });
  if (response.status !== 204) await response.text();
}

async function getFeedback(env, dedicationId) {
  const loaded = await loadDedicationById(env, dedicationId);
  return feedbackPayload(loaded.dedication);
}

async function getAllFeedback(env) {
  const files = await listDedicationFiles(env);
  const feedback = {};
  for (const file of files) {
    const loaded = await loadDedicationPath(env, `${file.path}?ref=${encodeURIComponent(githubBranch(env))}`);
    const payload = feedbackPayload(loaded.dedication);
    if (payload.id) feedback[payload.id] = payload;
  }
  return feedback;
}

async function saveVote(env, payload) {
  const dedicationId = String(payload.id || payload.dedicationId || '').trim();
  const user = userFromPayload(payload);
  const vote = Number(payload.votoPilly);
  if (!Number.isInteger(vote) || vote < 1 || vote > 10) {
    throw new Error('votoPilly deve essere un numero intero da 1 a 10.');
  }

  const loaded = await loadDedicationById(env, dedicationId);
  const now = nowIsoRomeApprox();
  const votes = normalizeVotes(loaded.dedication.votes);
  const existingVote = votes.find(item => item.userId === user.userId);
  if (existingVote) {
    existingVote.userName = user.userName;
    existingVote.value = vote;
    existingVote.updatedAt = now;
  } else {
    votes.push({ ...user, value: vote, createdAt: now, updatedAt: now });
  }

  const thoughtText = String(payload.pensieroPilly || payload.thought || '').trim();
  let thoughts = normalizeThoughts(loaded.dedication.thoughts);
  const existingThought = thoughts.find(item => item.userId === user.userId);
  if (thoughtText) {
    if (existingThought) {
      existingThought.userName = user.userName;
      existingThought.text = thoughtText;
      existingThought.updatedAt = now;
    } else {
      thoughts.push({ ...user, text: thoughtText, createdAt: now, updatedAt: now });
    }
  } else if (existingThought) {
    thoughts = thoughts.filter(item => item.userId !== user.userId);
  }

  loaded.dedication.votes = votes;
  loaded.dedication.thoughts = thoughts;
  loaded.dedication.updated_at = now;
  syncDerivedFeedbackFields(loaded.dedication);
  await saveDedication(env, loaded, `Salva voto Pilly ${dedicationId}`);
  const feedback = feedbackPayload(loaded.dedication);
  feedback.currentVote = vote;
  feedback.currentThought = thoughtText;
  feedback.currentUserName = user.userName;
  try {
    await dispatchVoteEmail(env, feedback);
    feedback.vote_email_dispatched = true;
  } catch (error) {
    console.warn('Email voto Pilly non inviata:', error);
    feedback.vote_email_dispatched = false;
  }
  return feedback;
}

async function saveReaction(env, payload) {
  const dedicationId = String(payload.id || payload.dedicationId || '').trim();
  const user = userFromPayload(payload);
  const reaction = payload.reaction === null || payload.reaction === undefined
    ? ''
    : String(payload.reaction).trim();
  const previousReaction = String(payload.previousReaction || '').trim();
  if (reaction && !REACTION_KEYS.includes(reaction)) {
    throw new Error(`reaction non valida. Usa una tra: ${REACTION_KEYS.join(', ')}`);
  }
  if (previousReaction && !REACTION_KEYS.includes(previousReaction)) {
    throw new Error(`previousReaction non valida. Usa una tra: ${REACTION_KEYS.join(', ')}`);
  }
  if (!reaction && !previousReaction) {
    throw new Error('reaction o previousReaction obbligatoria.');
  }

  const loaded = await loadDedicationById(env, dedicationId);
  const now = nowIsoRomeApprox();
  let reactionEntries = normalizeReactionEntries(loaded.dedication.reactionEntries);
  const existing = reactionEntries.find(item => item.userId === user.userId);
  if (reaction) {
    if (existing) {
      existing.userName = user.userName;
      existing.value = reaction;
      existing.updatedAt = now;
    } else {
      reactionEntries.push({ ...user, value: reaction, createdAt: now, updatedAt: now });
    }
  } else {
    reactionEntries = reactionEntries.filter(item => item.userId !== user.userId);
  }
  loaded.dedication.reactionEntries = reactionEntries;
  loaded.dedication.updated_at = now;
  syncDerivedFeedbackFields(loaded.dedication);
  await saveDedication(env, loaded, `Salva reazione Pilly ${dedicationId}`);
  return feedbackPayload(loaded.dedication);
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return jsonResponse({ ok: true }, 200, env, request);

    const url = new URL(request.url);
    try {
      if (request.method === 'GET' && url.pathname === '/') {
        return jsonResponse({
          ok: true,
          service: 'DDG FF feedback worker',
          endpoints: ['/feedback/all', '/feedback?id=<dedication_id>', '/save_vote', '/save_reaction'],
        }, 200, env, request);
      }

      if (request.method === 'GET' && url.pathname === '/feedback') {
        return jsonResponse({
          ok: true,
          feedback: await getFeedback(env, url.searchParams.get('id') || url.searchParams.get('dedicationId')),
        }, 200, env, request);
      }

      if (request.method === 'GET' && url.pathname === '/feedback/all') {
        return jsonResponse({ ok: true, feedback: await getAllFeedback(env) }, 200, env, request);
      }

      if (request.method === 'POST' && url.pathname === '/save_vote') {
        const payload = await request.json();
        const feedback = await saveVote(env, payload);
        return jsonResponse({ ok: true, ...feedback }, 200, env, request);
      }

      if (request.method === 'POST' && url.pathname === '/save_reaction') {
        const payload = await request.json();
        const feedback = await saveReaction(env, payload);
        return jsonResponse({ ok: true, ...feedback }, 200, env, request);
      }

      return jsonResponse({ ok: false, error: 'Endpoint non trovato.' }, 404, env, request);
    } catch (error) {
      return jsonResponse({
        ok: false,
        error: error instanceof Error ? error.message : 'Errore feedback worker.',
      }, 400, env, request);
    }
  },
};
