"""
Servizio condiviso per salvare feedback persistente sulle dediche.

Questo modulo non dipende da Streamlit: puo essere usato da admin UI,
script CLI, micro API o in futuro da un backend Atlas.
"""
from __future__ import annotations

import base64
import json
import os
from copy import deepcopy
from typing import Any

import requests

from scripts.utils import (
    DATA_DIR,
    find_existing_dedication_path,
    get_rome_now,
    load_all_dedications,
    load_json,
    save_json,
)

REACTION_KEYS = ("down", "like", "heart", "sun")
GITHUB_API = "https://api.github.com"
LEGACY_VOTE_FIELD = "voto" + "Pil" + "ly"
LEGACY_THOUGHT_FIELD = "pensiero" + "Pil" + "ly"


def default_reactions() -> dict[str, int]:
    return {key: 0 for key in REACTION_KEYS}


def normalize_reactions(value: Any) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    normalized = default_reactions()
    for key in REACTION_KEYS:
        try:
            normalized[key] = max(0, int(source.get(key, 0) or 0))
        except (TypeError, ValueError):
            normalized[key] = 0
    return normalized


def _clean_text(value: Any, max_length: int = 160) -> str:
    text = str(value or "").strip()
    return text[:max_length]


def _user_from_values(user_id: str = "", user_name: str = "", nome: str = "", cognome: str = "") -> dict[str, str]:
    user_id = _clean_text(user_id)
    if not user_id:
        raise ValueError("userId obbligatorio per salvare feedback nominale.")
    display_name = _clean_text(user_name or " ".join(part for part in (nome, cognome) if part).strip() or "Utente", 120)
    return {"userId": user_id, "userName": display_name}


def normalize_votes(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            vote = int(item.get("value"))
        except (TypeError, ValueError):
            continue
        user_id = _clean_text(item.get("userId") or item.get("user_id"))
        if not user_id or vote < 1 or vote > 10:
            continue
        normalized.append({
            "userId": user_id,
            "userName": _clean_text(item.get("userName") or item.get("user_name") or "Utente", 120),
            "value": vote,
            "createdAt": _clean_text(item.get("createdAt") or item.get("created_at"), 80),
            "updatedAt": _clean_text(item.get("updatedAt") or item.get("updated_at"), 80),
        })
    return normalized


def normalize_thoughts(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        user_id = _clean_text(item.get("userId") or item.get("user_id"))
        text = str(item.get("text") or "").strip()
        if not user_id or not text:
            continue
        normalized.append({
            "userId": user_id,
            "userName": _clean_text(item.get("userName") or item.get("user_name") or "Utente", 120),
            "text": text,
            "createdAt": _clean_text(item.get("createdAt") or item.get("created_at"), 80),
            "updatedAt": _clean_text(item.get("updatedAt") or item.get("updated_at"), 80),
        })
    return normalized


def normalize_reaction_entries(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        user_id = _clean_text(item.get("userId") or item.get("user_id"))
        reaction = _clean_text(item.get("value") or item.get("reaction"), 40)
        if not user_id or reaction not in REACTION_KEYS:
            continue
        normalized.append({
            "userId": user_id,
            "userName": _clean_text(item.get("userName") or item.get("user_name") or "Utente", 120),
            "value": reaction,
            "createdAt": _clean_text(item.get("createdAt") or item.get("created_at"), 80),
            "updatedAt": _clean_text(item.get("updatedAt") or item.get("updated_at"), 80),
        })
    return normalized


def _average_vote(votes: list[dict[str, Any]]) -> float | None:
    if not votes:
        return None
    return round(sum(int(item["value"]) for item in votes) / len(votes), 1)


def _reaction_counts(entries: list[dict[str, str]]) -> dict[str, int]:
    counts = default_reactions()
    for item in entries:
        if item["value"] in counts:
            counts[item["value"]] += 1
    return counts


def sync_feedback_aggregates(dedication: dict) -> dict:
    has_nominal_reactions = isinstance(dedication.get("reactionEntries"), list)
    votes = normalize_votes(dedication.get("votes"))
    thoughts = normalize_thoughts(dedication.get("thoughts"))
    reaction_entries = normalize_reaction_entries(dedication.get("reactionEntries"))
    try:
        legacy_vote = int(dedication.get("voteAverage", dedication.get(LEGACY_VOTE_FIELD)))
    except (TypeError, ValueError):
        legacy_vote = 0
    if not votes and 1 <= legacy_vote <= 10:
        votes.append({
            "userId": "legacy-feedback",
            "userName": "Storico",
            "value": legacy_vote,
            "createdAt": _clean_text(dedication.get("updated_at"), 80),
            "updatedAt": _clean_text(dedication.get("updated_at"), 80),
        })
    legacy_thought = str(dedication.get("thoughtsText", dedication.get(LEGACY_THOUGHT_FIELD)) or "").strip()
    if not thoughts and legacy_thought:
        thoughts.append({
            "userId": "legacy-feedback",
            "userName": "Storico",
            "text": legacy_thought,
            "createdAt": _clean_text(dedication.get("updated_at"), 80),
            "updatedAt": _clean_text(dedication.get("updated_at"), 80),
        })
    dedication["votes"] = votes
    dedication["thoughts"] = thoughts
    dedication["reactionEntries"] = reaction_entries
    dedication["voteAverage"] = _average_vote(votes)
    dedication["thoughtsText"] = "\n\n".join(f"[{item['userName']}] {item['text']}" for item in thoughts)
    dedication.pop(LEGACY_VOTE_FIELD, None)
    dedication.pop(LEGACY_THOUGHT_FIELD, None)
    dedication["reactions"] = _reaction_counts(reaction_entries) if has_nominal_reactions else normalize_reactions(dedication.get("reactions"))
    return dedication


def ensure_feedback_fields(dedication: dict) -> dict:
    """Aggiunge i campi feedback standard senza perdere valori esistenti."""
    updated = deepcopy(dedication)
    updated.setdefault("voteAverage", updated.get(LEGACY_VOTE_FIELD))
    updated.setdefault("thoughtsText", updated.get(LEGACY_THOUGHT_FIELD, ""))
    updated["reactions"] = normalize_reactions(updated.get("reactions"))
    updated["votes"] = normalize_votes(updated.get("votes"))
    updated["thoughts"] = normalize_thoughts(updated.get("thoughts"))
    if isinstance(updated.get("reactionEntries"), list):
        updated["reactionEntries"] = normalize_reaction_entries(updated.get("reactionEntries"))
    return sync_feedback_aggregates(updated)


def merge_existing_feedback(target: dict, existing: dict | None) -> dict:
    """Preserva il feedback locale quando una sync rigenera la dedica."""
    updated = ensure_feedback_fields(target)
    if not existing:
        return updated

    existing = ensure_feedback_fields(existing)
    for key in ("voteAverage", "thoughtsText", "reactions", "votes", "thoughts", "reactionEntries"):
        if key == "reactionEntries" and not existing.get(key):
            continue
        if key in existing:
            updated[key] = existing[key]
    if not updated.get("reactionEntries"):
        updated.pop("reactionEntries", None)
    return sync_feedback_aggregates(updated)


def _load_existing_dedication(dedication_id: str) -> tuple[dict, Any]:
    dedication_id = (dedication_id or "").strip()
    if not dedication_id:
        raise ValueError("dedication_id obbligatorio.")

    path = find_existing_dedication_path(dedication_id)
    if not path:
        raise FileNotFoundError(f"Dedica non trovata: {dedication_id}")

    dedication = load_json(path)
    if not isinstance(dedication, dict):
        raise ValueError(f"JSON dedica non valido: {path}")
    return ensure_feedback_fields(dedication), path


def _github_token() -> str:
    return (
        os.environ.get("DDGFF_GITHUB_TOKEN")
        or os.environ.get("GITHUB_PAT")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()


def use_github_backend() -> bool:
    return os.environ.get("DDGFF_FEEDBACK_BACKEND", "").strip().lower() == "github"


def _github_repo() -> str:
    repo = os.environ.get("DDGFF_GITHUB_REPO") or os.environ.get("GITHUB_REPO") or ""
    repo = repo.strip()
    if not repo:
        raise ValueError("DDGFF_GITHUB_REPO mancante, esempio: legnaro72/dediche-musicali-ff.")
    return repo


def _github_branch() -> str:
    return (os.environ.get("DDGFF_GITHUB_BRANCH") or os.environ.get("GITHUB_BRANCH") or "main").strip()


def _github_headers() -> dict[str, str]:
    token = _github_token()
    if not token:
        raise ValueError("Token GitHub mancante. Configura DDGFF_GITHUB_TOKEN come secret del backend.")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _github_request(method: str, path: str, **kwargs):
    response = requests.request(
        method,
        f"{GITHUB_API}/repos/{_github_repo()}/{path.lstrip('/')}",
        headers=_github_headers(),
        timeout=25,
        **kwargs,
    )
    if response.status_code >= 400:
        raise ValueError(f"GitHub API error {response.status_code}: {response.text}")
    return response


def _dedication_file_name(dedication: dict) -> str:
    current_path = find_existing_dedication_path(str(dedication.get("id", "")), str(dedication.get("date", "")))
    if current_path:
        return current_path.name
    return f"{dedication.get('id')}.json"


def _github_load_path(repo_path: str) -> tuple[dict, str]:
    response = _github_request("GET", f"contents/{repo_path}", params={"ref": _github_branch()})
    payload = response.json()
    content = base64.b64decode(payload["content"]).decode("utf-8-sig")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"JSON GitHub non valido: {repo_path}")
    return ensure_feedback_fields(data), payload["sha"]


def _github_load_dedication(dedication_id: str) -> tuple[dict, str, str]:
    dedication_id = (dedication_id or "").strip()
    if not dedication_id:
        raise ValueError("dedication_id obbligatorio.")

    direct_path = f"data/dedications/{dedication_id}.json"
    try:
        dedication, sha = _github_load_path(direct_path)
        return dedication, direct_path, sha
    except Exception:
        pass

    response = _github_request("GET", "contents/data/dedications", params={"ref": _github_branch()})
    for item in response.json():
        if not str(item.get("name", "")).endswith(".json"):
            continue
        dedication, sha = _github_load_path(item["path"])
        if dedication.get("id") == dedication_id:
            return dedication, item["path"], sha

    raise FileNotFoundError(f"Dedica non trovata su GitHub: {dedication_id}")


def _github_save_dedication(dedication: dict, repo_path: str, sha: str, message: str) -> dict:
    encoded = base64.b64encode(
        json.dumps(dedication, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
        "branch": _github_branch(),
    }
    _github_request("PUT", f"contents/{repo_path}", json=payload)
    return dedication


def _load_feedback_target(dedication_id: str) -> tuple[dict, Any, str | None]:
    if use_github_backend():
        dedication, repo_path, sha = _github_load_dedication(dedication_id)
        return dedication, repo_path, sha
    dedication, path = _load_existing_dedication(dedication_id)
    return dedication, path, None


def _save_feedback_target(dedication: dict, target: Any, sha: str | None, message: str) -> dict:
    if use_github_backend():
        if not sha:
            raise ValueError("SHA GitHub mancante per il salvataggio.")
        return _github_save_dedication(dedication, str(target), sha, message)
    if not save_json(dedication, target):
        raise OSError(f"Impossibile salvare {target}")
    return dedication


def feedback_payload(dedication: dict) -> dict:
    dedication = ensure_feedback_fields(dedication)
    return {
        "id": dedication.get("id", ""),
        "date": dedication.get("date", ""),
        "title": dedication.get("song_title", ""),
        "artist": dedication.get("artist", ""),
        "voteAverage": dedication.get("voteAverage"),
        "thoughtsText": dedication.get("thoughtsText", ""),
        "reactions": normalize_reactions(dedication.get("reactions")),
        "votes": normalize_votes(dedication.get("votes")),
        "thoughts": normalize_thoughts(dedication.get("thoughts")),
        "reactionEntries": normalize_reaction_entries(dedication.get("reactionEntries")),
        "updated_at": dedication.get("updated_at", ""),
    }


def load_feedback(dedication_id: str) -> dict:
    dedication, _target, _sha = _load_feedback_target(dedication_id)
    return feedback_payload(dedication)


def load_all_feedback() -> dict[str, dict]:
    if use_github_backend():
        response = _github_request("GET", "contents/data/dedications", params={"ref": _github_branch()})
        feedback = {}
        for item in response.json():
            if not str(item.get("name", "")).endswith(".json"):
                continue
            dedication, _sha = _github_load_path(item["path"])
            payload = feedback_payload(dedication)
            if payload["id"]:
                feedback[payload["id"]] = payload
        return feedback

    feedback = {}
    for dedication in load_all_dedications():
        if not isinstance(dedication, dict):
            continue
        payload = feedback_payload(dedication)
        if payload["id"]:
            feedback[payload["id"]] = payload
    return feedback


def update_vote(
    dedication_id: str,
    vote_value: int,
    thought_text: str = "",
    user_id: str = "",
    user_name: str = "",
    nome: str = "",
    cognome: str = "",
) -> dict:
    """Aggiorna voto e pensiero nominali sul JSON della dedica."""
    try:
        vote = int(vote_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Il voto deve essere un numero intero da 1 a 10.") from exc
    if vote < 1 or vote > 10:
        raise ValueError("Il voto deve essere compreso tra 1 e 10.")

    dedication, target, sha = _load_feedback_target(dedication_id)
    user = _user_from_values(user_id, user_name, nome, cognome)
    now = get_rome_now().isoformat()
    votes = normalize_votes(dedication.get("votes"))
    current_vote = next((item for item in votes if item["userId"] == user["userId"]), None)
    if current_vote:
        current_vote.update({**user, "value": vote, "updatedAt": now})
    else:
        votes.append({**user, "value": vote, "createdAt": now, "updatedAt": now})

    thought_text = str(thought_text or "").strip()
    thoughts = normalize_thoughts(dedication.get("thoughts"))
    current_thought = next((item for item in thoughts if item["userId"] == user["userId"]), None)
    if thought_text:
        if current_thought:
            current_thought.update({**user, "text": thought_text, "updatedAt": now})
        else:
            thoughts.append({**user, "text": thought_text, "createdAt": now, "updatedAt": now})
    elif current_thought:
        thoughts = [item for item in thoughts if item["userId"] != user["userId"]]

    dedication["votes"] = votes
    dedication["thoughts"] = thoughts
    dedication["updated_at"] = now
    sync_feedback_aggregates(dedication)

    return _save_feedback_target(
        dedication,
        target,
        sha,
        f"Salva voto FF {dedication_id}",
    )


def update_reaction(
    dedication_id: str,
    reaction: str | None,
    previous_reaction: str | None = None,
    user_id: str = "",
    user_name: str = "",
    nome: str = "",
    cognome: str = "",
) -> dict:
    """Aggiorna la reaction nominale per una dedica."""
    reaction = str(reaction or "").strip()
    previous_reaction = str(previous_reaction or "").strip()
    if reaction and reaction not in REACTION_KEYS:
        raise ValueError(f"reaction non valida. Usa una tra: {', '.join(REACTION_KEYS)}")
    if previous_reaction and previous_reaction not in REACTION_KEYS:
        raise ValueError(f"previous_reaction non valida. Usa una tra: {', '.join(REACTION_KEYS)}")
    if not reaction and not previous_reaction:
        raise ValueError("reaction o previous_reaction obbligatoria.")

    dedication, target, sha = _load_feedback_target(dedication_id)
    user = _user_from_values(user_id, user_name, nome, cognome)
    now = get_rome_now().isoformat()
    reaction_entries = normalize_reaction_entries(dedication.get("reactionEntries"))
    current = next((item for item in reaction_entries if item["userId"] == user["userId"]), None)
    if reaction:
        if current:
            current.update({**user, "value": reaction, "updatedAt": now})
        else:
            reaction_entries.append({**user, "value": reaction, "createdAt": now, "updatedAt": now})
    else:
        reaction_entries = [item for item in reaction_entries if item["userId"] != user["userId"]]
    dedication["reactionEntries"] = reaction_entries
    dedication["updated_at"] = now
    sync_feedback_aggregates(dedication)

    return _save_feedback_target(
        dedication,
        target,
        sha,
        f"Salva reazione FF {dedication_id}",
    )
