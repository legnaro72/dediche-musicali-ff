const REACTION_KEYS = ['down', 'like', 'heart', 'sun'];
const LEGACY_VOTE_FIELD = `voto${'Pil' + 'ly'}`;
const LEGACY_THOUGHT_FIELD = `pensiero${'Pil' + 'ly'}`;
const VISITS_PATH = 'data/visits.json';

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
      'access-control-allow-headers': 'content-type, authorization, x-admin-token',
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

function normalizeUserKey(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 160);
}

function userFromPayload(payload) {
  const fallbackName = [payload.nome, payload.cognome].filter(Boolean).join(' ').trim();
  const nameSource = fallbackName || payload.userName || payload.displayName || '';
  const email = normalizeText(payload.email || payload.mail || '', 160);
  const userKey = normalizeUserKey(payload.userKey || payload.user_key || nameSource || email || payload.userId || payload.user_id);
  if (!userKey) throw new Error('nome e cognome obbligatori per salvare feedback nominale.');
  const userId = normalizeText(payload.userId || payload.user_id || userKey, 160);
  const userName = normalizeText(payload.userName || payload.displayName || fallbackName || 'Utente', 120);
  return { userId, userKey, userName };
}

function normalizeVotes(value) {
  const list = Array.isArray(value) ? value : [];
  const byUser = new Map();
  list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userKey: normalizeUserKey(item?.userKey || item?.user_key || item?.userName || item?.user_name || item?.userId || item?.user_id),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      value: Number(item?.value),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userKey && Number.isInteger(item.value) && item.value >= 1 && item.value <= 10)
    .forEach(item => {
      const existing = byUser.get(item.userKey);
      byUser.set(item.userKey, {
        ...item,
        userId: item.userId || item.userKey,
        createdAt: existing?.createdAt || item.createdAt,
      });
    });
  return [...byUser.values()];
}

function normalizeThoughts(value) {
  const list = Array.isArray(value) ? value : [];
  const byUser = new Map();
  list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userKey: normalizeUserKey(item?.userKey || item?.user_key || item?.userName || item?.user_name || item?.userId || item?.user_id),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      text: String(item?.text || '').trim(),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userKey && item.text)
    .forEach(item => {
      const existing = byUser.get(item.userKey);
      byUser.set(item.userKey, {
        ...item,
        userId: item.userId || item.userKey,
        createdAt: existing?.createdAt || item.createdAt,
      });
    });
  return [...byUser.values()];
}

function normalizeReactionEntries(value) {
  const list = Array.isArray(value) ? value : [];
  const byUser = new Map();
  list
    .map(item => ({
      userId: normalizeText(item?.userId || item?.user_id || '', 160),
      userKey: normalizeUserKey(item?.userKey || item?.user_key || item?.userName || item?.user_name || item?.userId || item?.user_id),
      userName: normalizeText(item?.userName || item?.user_name || 'Utente', 120),
      value: String(item?.value || item?.reaction || '').trim(),
      createdAt: String(item?.createdAt || item?.created_at || '').trim(),
      updatedAt: String(item?.updatedAt || item?.updated_at || '').trim(),
    }))
    .filter(item => item.userKey && REACTION_KEYS.includes(item.value))
    .forEach(item => {
      const existing = byUser.get(item.userKey);
      byUser.set(item.userKey, {
        ...item,
        userId: item.userId || item.userKey,
        createdAt: existing?.createdAt || item.createdAt,
      });
    });
  return [...byUser.values()];
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
  const legacyVote = Number(dedication.voteAverage ?? dedication[LEGACY_VOTE_FIELD]);
  if (!votes.length && Number.isInteger(legacyVote) && legacyVote >= 1 && legacyVote <= 10) {
    votes.push({
      userId: 'legacy-feedback',
      userName: 'Storico',
      value: legacyVote,
      createdAt: String(dedication.updated_at || ''),
      updatedAt: String(dedication.updated_at || ''),
    });
  }
  const legacyThought = String(dedication.thoughtsText ?? dedication[LEGACY_THOUGHT_FIELD] ?? '').trim();
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
  dedication.voteAverage = averageVote(votes);
  dedication.thoughtsText = thoughts.map(item => `[${item.userName}] ${item.text}`).join('\n\n');
  delete dedication[LEGACY_VOTE_FIELD];
  delete dedication[LEGACY_THOUGHT_FIELD];
  dedication.reactions = hasNominalReactions
    ? aggregateReactionEntries(reactionEntries)
    : normalizeReactions(dedication.reactions);
  return dedication;
}

function ensureFeedbackFields(dedication) {
  const updated = {
    ...dedication,
    voteAverage: dedication.voteAverage ?? dedication[LEGACY_VOTE_FIELD] ?? null,
    thoughtsText: dedication.thoughtsText ?? dedication[LEGACY_THOUGHT_FIELD] ?? '',
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
    voteAverage: normalized.voteAverage,
    thoughtsText: normalized.thoughtsText || '',
    reactions: normalizeReactions(normalized.reactions),
    votes: normalized.votes || [],
    thoughts: normalized.thoughts || [],
    reactionEntries: normalized.reactionEntries || [],
    updated_at: normalized.updated_at || '',
  };
}

function normalizePage(value) {
  const page = normalizeText(value || '/', 240) || '/';
  if (/^https?:\/\//i.test(page)) {
    try {
      return new URL(page).pathname || '/';
    } catch {
      return '/';
    }
  }
  return page.startsWith('/') ? page : `/${page}`;
}

function normalizeVisit(item) {
  const visitId = normalizeText(item?.visitId || item?.visit_id || '', 220);
  const userKey = normalizeUserKey(item?.userKey || item?.user_key || item?.userName || item?.user_name);
  const userName = normalizeText(item?.userName || item?.user_name || 'Utente', 120);
  const visitedAt = normalizeText(item?.visitedAt || item?.visited_at || item?.createdAt || item?.created_at || '', 80);
  const visitDate = normalizeText(item?.visitDate || item?.visit_date || String(visitedAt).slice(0, 10), 20);
  if (!visitId || !userKey || !userName || !visitedAt || !visitDate) return null;
  return {
    visitId,
    userKey,
    userName,
    visitedAt,
    visitDate,
    page: normalizePage(item?.page || '/'),
    source: normalizeText(item?.source || 'site', 40),
    userAgent: normalizeText(item?.userAgent || item?.user_agent || '', 240),
    createdAt: normalizeText(item?.createdAt || item?.created_at || visitedAt, 80),
  };
}

function normalizeVisitsPayload(value) {
  const visits = Array.isArray(value?.visits) ? value.visits : [];
  return { visits: visits.map(normalizeVisit).filter(Boolean) };
}

function requiredEnv(env, key) {
  const value = env[key];
  if (!value) throw new Error(`Secret/variabile mancante: ${key}`);
  return value;
}

function assertVisitsReadAllowed(env, request) {
  const expected = String(env.VISITS_READ_TOKEN || '').trim();
  if (!expected) return;
  const authorization = request.headers.get('authorization') || '';
  const bearer = authorization.replace(/^Bearer\s+/i, '').trim();
  const headerToken = request.headers.get('x-admin-token') || '';
  if (bearer === expected || headerToken === expected) return;
  throw new Error('Non autorizzato a leggere le visite.');
}

function githubHeaders(env) {
  return {
    accept: 'application/vnd.github+json',
    authorization: `Bearer ${requiredEnv(env, 'GITHUB_TOKEN')}`,
    'x-github-api-version': '2022-11-28',
    'user-agent': 'ddgff-feedback-worker',
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

async function loadJsonPath(env, repoPath, defaultValue) {
  try {
    const response = await githubRequest(
      env,
      `contents/${repoPath}?ref=${encodeURIComponent(githubBranch(env))}`,
      { method: 'GET', cf: { cacheTtl: 0 }, headers: {} },
    );
    const payload = await response.json();
    return {
      data: JSON.parse(decodeBase64Utf8(payload.content)),
      path: payload.path,
      sha: payload.sha,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    if (message.includes('GitHub API 404')) {
      return { data: defaultValue, path: repoPath, sha: null };
    }
    throw error;
  }
}

async function saveJsonPath(env, loaded, message) {
  const content = encodeBase64Utf8(JSON.stringify(loaded.data, null, 2));
  const body = {
    message,
    content,
    branch: githubBranch(env),
  };
  if (loaded.sha) body.sha = loaded.sha;
  const response = await githubRequest(env, `contents/${loaded.path}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  await response.json();
  return loaded.data;
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
        score: String(feedback.currentVote ?? feedback.voteAverage ?? ''),
        thought: truncateInput(feedback.currentThought || feedback.thoughtsText || '', 6000),
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
  const vote = Number(payload.voteValue ?? payload.vote ?? payload[LEGACY_VOTE_FIELD]);
  if (!Number.isInteger(vote) || vote < 1 || vote > 10) {
    throw new Error('Il voto deve essere un numero intero da 1 a 10.');
  }

  const loaded = await loadDedicationById(env, dedicationId);
  const now = nowIsoRomeApprox();
  const votes = normalizeVotes(loaded.dedication.votes);
  const existingVote = votes.find(item => item.userKey === user.userKey);
  if (existingVote) {
    existingVote.userName = user.userName;
    existingVote.value = vote;
    existingVote.updatedAt = now;
  } else {
    votes.push({ ...user, value: vote, createdAt: now, updatedAt: now });
  }

  const thoughtText = String(payload.thoughtText ?? payload.thought ?? payload[LEGACY_THOUGHT_FIELD] ?? '').trim();
  let thoughts = normalizeThoughts(loaded.dedication.thoughts);
  const existingThought = thoughts.find(item => item.userKey === user.userKey);
  if (thoughtText) {
    if (existingThought) {
      existingThought.userName = user.userName;
      existingThought.text = thoughtText;
      existingThought.updatedAt = now;
    } else {
      thoughts.push({ ...user, text: thoughtText, createdAt: now, updatedAt: now });
    }
  } else if (existingThought) {
    thoughts = thoughts.filter(item => item.userKey !== user.userKey);
  }

  loaded.dedication.votes = votes;
  loaded.dedication.thoughts = thoughts;
  loaded.dedication.updated_at = now;
  syncDerivedFeedbackFields(loaded.dedication);
  await saveDedication(env, loaded, `Salva voto FF ${dedicationId}`);
  const feedback = feedbackPayload(loaded.dedication);
  feedback.currentVote = vote;
  feedback.currentThought = thoughtText;
  feedback.currentUserName = user.userName;
  try {
    await dispatchVoteEmail(env, feedback);
    feedback.vote_email_dispatched = true;
  } catch (error) {
    console.warn('Email voto FF non inviata:', error);
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
  const existing = reactionEntries.find(item => item.userKey === user.userKey);
  if (reaction) {
    if (existing) {
      existing.userName = user.userName;
      existing.value = reaction;
      existing.updatedAt = now;
    } else {
      reactionEntries.push({ ...user, value: reaction, createdAt: now, updatedAt: now });
    }
  } else {
    reactionEntries = reactionEntries.filter(item => item.userKey !== user.userKey);
  }
  loaded.dedication.reactionEntries = reactionEntries;
  loaded.dedication.updated_at = now;
  syncDerivedFeedbackFields(loaded.dedication);
  await saveDedication(env, loaded, `Salva reazione FF ${dedicationId}`);
  return feedbackPayload(loaded.dedication);
}

async function getVisits(env) {
  const loaded = await loadJsonPath(env, VISITS_PATH, { visits: [] });
  return normalizeVisitsPayload(loaded.data);
}

async function trackVisit(env, request, payload) {
  const user = userFromPayload(payload);
  const now = new Date();
  const visitedAt = now.toISOString();
  const visitDate = romeDateTimeParts(now).date;
  const loaded = await loadJsonPath(env, VISITS_PATH, { visits: [] });
  const current = normalizeVisitsPayload(loaded.data);
  const visit = {
    visitId: crypto.randomUUID ? crypto.randomUUID() : `${visitedAt}-${user.userKey}-${Math.random().toString(36).slice(2)}`,
    userKey: user.userKey,
    userName: user.userName,
    visitedAt,
    visitDate,
    page: normalizePage(payload.page || payload.path || '/'),
    source: 'site',
    userAgent: normalizeText(request.headers.get('user-agent') || payload.userAgent || '', 240),
    createdAt: visitedAt,
  };
  current.visits.push(visit);
  loaded.data = current;
  await saveJsonPath(env, loaded, `Registra visita sito ${visitDate}`);
  return visit;
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
          endpoints: ['/feedback/all', '/feedback?id=<dedication_id>', '/save_vote', '/save_reaction', '/track_visit', '/visits'],
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

      if (request.method === 'GET' && url.pathname === '/visits') {
        assertVisitsReadAllowed(env, request);
        return jsonResponse({ ok: true, visits: (await getVisits(env)).visits }, 200, env, request);
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

      if (request.method === 'POST' && url.pathname === '/track_visit') {
        const payload = await request.json();
        const visit = await trackVisit(env, request, payload);
        return jsonResponse({ ok: true, visit }, 200, env, request);
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
