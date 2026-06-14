import base64
import datetime
import html
import io
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import gspread
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


GOOGLE_SHEET_ID = os.environ.get(
    "GOOGLE_SHEET_ID",
    "1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw",
)
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parents[1] / "service_account.json"
DEFAULT_VOTE_URL = os.environ.get(
    "DEFAULT_VOTE_URL",
    "https://docs.google.com/forms/d/17VuesL0BOupyw5M5MNCLs1gq_uqZioVKVkGC8oFfn38/viewform",
)
SITE_NAME = os.environ.get("SITE_NAME", "DDG FF")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "legnaro72/dediche-musicali-ff")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
DAILY_WORKFLOW_FILE = os.environ.get("DAILY_WORKFLOW_FILE", "daily-publish.yml")
UPLOAD_DIR = "public/images/upload"
SITE_LOCK_IMAGE_DIR = "public/images/site-lock"
SITE_SETTINGS_PATH = "public/config/site-settings.json"
VISITS_PATH = "data/visits.json"
DEDICATIONS_DIR = "data/dedications"
REACTION_KEYS = ("down", "like", "heart", "sun")
ROOT_DIR = Path(__file__).resolve().parents[1]
DRAFT_DIR = ROOT_DIR / ".streamlit-drafts"
WHATSAPP_NOTIFY_PAOLA_NUMBER = os.environ.get("WHATSAPP_NOTIFY_PAOLA_NUMBER", "393285422549")
WHATSAPP_FF_GROUP_INVITE_URL = os.environ.get(
    "WHATSAPP_FF_GROUP_INVITE_URL",
    "https://chat.whatsapp.com/KbeTRjTEPLv70kMQJWVDrG",
)
WHATSAPP_NOTIFY_MESSAGE = os.environ.get(
    "WHATSAPP_NOTIFY_MESSAGE",
    "Ferrandi la DDG \u00e8 online!! Gloria al Doria e ai Ferrandi !!!\n\n"
    "Clicca sul seguente Link per accedere al Sito !!!\n"
    "https://legnaro72.github.io/dediche-musicali-ff/",
)
DEFAULT_SITE_SETTINGS = {
    "buttons": {
        "googleVote": True,
        "plusVote": True,
    },
    "feedbackApiUrl": "",
    "siteEffect": "none",
    "effectIntensity": "medium",
    "effectBackdrop": True,
    "effectFloatingItems": True,
    "effectBackdropText": True,
    "fakeError": {
        "enabled": False,
        "title": "ERROR 404",
        "message": "Il server non e' al momento raggiungibile.",
        "buttonText": "Verifica stato sistema",
        "imagePath": "",
        "imageMessage": "Sistema momentaneamente offline.",
        "adminMessage": "Per il ripristino del servizio contattare l'amministratore del sito.",
    },
    "updated_at": "",
}
SITE_EFFECT_OPTIONS = {
    "Automatico": "auto",
    "Nessun effetto": "none",
    "Brillio": "sparkles",
    "Neve": "snow",
    "Cuori rossi e blu pulsanti": "hearts_red_blue",
    "Note musicali": "music_notes",
    "Bolle luminose": "glow_bubbles",
    "Petali": "petals",
    "Coriandoli": "confetti",
    "Palloncini": "balloons",
    "Stelle": "stars",
    "Stelle cadenti": "shooting_stars",
    "Luci da concerto": "concert_lights",
    "Flash morbidi": "soft_flashes",
    "Fuochi d'artificio": "fireworks",
    "Pilli effetto diamante": "diamond_pilli",
    "Palloni da calcio dinamici": "soccer_balls",
    "Soli luminosi sorridenti": "smiling_suns",
    "Farfalle luminose glitterate": "glitter_butterflies",
}
EFFECT_INTENSITY_OPTIONS = {
    "Bassa": "low",
    "Media": "medium",
    "Alta": "high",
}
VALID_IMAGE_MODES = ("raw", "auto", "upload", "none")
VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".gif", ".heic", ".heif", ""}
VALID_STATUSES = ("draft", "scheduled", "published", "disabled")
VALID_VIDEO_TYPES = ("", "youtube", "mp4", "external")
UPLOAD_IMAGE_MAX_SIDE = int(os.environ.get("UPLOAD_IMAGE_MAX_SIDE", "1400"))
UPLOAD_IMAGE_WEBP_QUALITY = int(os.environ.get("UPLOAD_IMAGE_WEBP_QUALITY", "78"))
UPLOAD_IMAGE_TARGET_BYTES = int(os.environ.get("UPLOAD_IMAGE_TARGET_BYTES", str(450 * 1024)))
UPLOAD_IMAGE_HARD_MAX_BYTES = int(os.environ.get("UPLOAD_IMAGE_HARD_MAX_BYTES", str(700 * 1024)))
STREAMLIT_ICON_PATH = Path(__file__).resolve().parents[1] / "public" / "favicon" / "favicon.png"


class UploadedImageSnapshot:
    """Copia stabile di un file caricato, utile quando il browser mobile perde il widget."""

    def __init__(self, name: str, file_type: str, data: bytes):
        self.name = name
        self.type = file_type
        self._data = data

    def getvalue(self) -> bytes:
        return self._data

SHEET_COLUMNS = [
    "id",
    "date",
    "status",
    "song_title",
    "artist",
    "dedication_title",
    "dedication_text",
    "audio_url",
    "audio_type",
    "vote_url",
    "image_mode",
    "image_source",
    "short_phrase",
    "tags",
    "seo_title",
    "seo_description",
    "image_alt",
    "video_type",
    "video_url",
    "video_poster",
    "video_title",
    "video_description",
]

QUICK_EMOJIS = ["🎵", "❤️", "✨", "🌙", "🌹", "😊", "🙏", "🎧"]
EXTENDED_EMOJIS = [
    "🎶", "💙", "💛", "💜", "💫", "🌟", "☀️", "🌻",
    "🔥", "😍", "🥹", "🕊️", "🎤", "💭", "🌈", "🍀",
    "⭐", "💌", "🤍", "🫶", "🌊", "🎹", "🎸", "🪩",
]


def inject_streamlit_pwa_tags() -> None:
    favicon_href = ""
    if STREAMLIT_ICON_PATH.exists():
        favicon_href = (
            "data:image/png;base64,"
            + base64.b64encode(STREAMLIT_ICON_PATH.read_bytes()).decode("ascii")
        )
    favicon_href_js = json.dumps(favicon_href or "/app/static/pwa/icons/icon-192.png?v=ddgff-admin-v2")
    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const faviconHref = {favicon_href_js};
          const tags = [
            ['link', {{ rel: 'manifest', href: '/app/static/pwa/manifest.json?v=ddgff-admin-v2' }}],
            ['link', {{ rel: 'icon', type: 'image/png', href: faviconHref }}],
            ['link', {{ rel: 'shortcut icon', type: 'image/png', href: faviconHref }}],
            ['link', {{ rel: 'apple-touch-icon', href: '/app/static/pwa/icons/apple-touch-icon.png?v=ddgff-admin-v2' }}],
            ['link', {{ rel: 'apple-touch-startup-image', href: '/app/static/pwa/icons/apple-splash-2048.png?v=ddgff-admin-v2' }}],
            ['meta', {{ name: 'theme-color', content: '#08070f' }}],
            ['meta', {{ name: 'apple-mobile-web-app-capable', content: 'yes' }}],
            ['meta', {{ name: 'apple-mobile-web-app-title', content: 'DDG FF Admin' }}],
            ['meta', {{ name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' }}],
            ['meta', {{ name: 'mobile-web-app-capable', content: 'yes' }}]
          ];

          for (const [tagName, attrs] of tags) {{
            const selector = attrs.rel
              ? `${{tagName}}[rel="${{attrs.rel}}"]`
              : `${{tagName}}[name="${{attrs.name}}"]`;
            let el = doc.querySelector(selector);
            if (!el) {{
              el = doc.createElement(tagName);
              doc.head.appendChild(el);
            }}
            for (const [key, value] of Object.entries(attrs)) {{
              el.setAttribute(key, value);
            }}
          }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a",
        "è": "e", "é": "e", "ê": "e", "ë": "e",
        "ì": "i", "í": "i", "î": "i", "ï": "i",
        "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o",
        "ù": "u", "ú": "u", "û": "u", "ü": "u",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_date(date_text: str) -> str:
    date_text = date_text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Formato data non valido. Usa YYYY-MM-DD oppure DD/MM/YYYY.")


def tomorrow_rome_date() -> datetime.date:
    if ZoneInfo is not None:
        now = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    else:
        now = datetime.datetime.now()
    return now.date() + datetime.timedelta(days=1)


def parse_date_value(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    value = str(value or "").strip()
    if value:
        try:
            return datetime.datetime.strptime(normalize_date(value), "%Y-%m-%d").date()
        except ValueError:
            pass
    return tomorrow_rome_date()


def sync_date_picker(prefix: str) -> None:
    selected = st.session_state.get(f"{prefix}_date_picker")
    st.session_state[f"{prefix}_date"] = parse_date_value(selected).isoformat()


def is_spotify_track_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return spotify_track_url(url) is not None


def spotify_track_url(url: str) -> str | None:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc not in ("open.spotify.com", "play.spotify.com"):
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    track_index = None
    for idx, part in enumerate(parts):
        if part == "track":
            track_index = idx
            break
    if track_index is None or track_index + 1 >= len(parts):
        return None

    track_id = parts[track_index + 1]
    if not re.fullmatch(r"[A-Za-z0-9]{10,}", track_id):
        return None

    return urlunparse(("https", "open.spotify.com", f"/track/{track_id}", "", "", ""))


def split_spotify_title(raw_title: str, raw_artist: str) -> tuple[str, str]:
    title = (raw_title or "").strip()
    artist = (raw_artist or "").strip()
    title = re.sub(r"\s*\|\s*Spotify\s*$", "", title, flags=re.IGNORECASE).strip()

    match = re.match(r"(.+?)\s+-\s+song and lyrics by\s+(.+)$", title, flags=re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        artist = artist or match.group(2).strip()
    elif artist and title.lower().endswith(f" - {artist}".lower()):
        title = title[:-(len(artist) + 3)].strip()

    return title, artist


def fetch_spotify_oembed(url: str) -> tuple[str, str]:
    response = requests.get(
        "https://open.spotify.com/oembed",
        params={"url": url},
        timeout=12,
        headers={"User-Agent": "DDGFFAdmin/1.0"},
    )
    if response.status_code >= 400:
        raise ValueError("Spotify oEmbed non ha restituito metadati.")
    payload = response.json()
    return split_spotify_title(payload.get("title", ""), payload.get("author_name", ""))


def fetch_spotify_open_graph(url: str) -> tuple[str, str]:
    response = requests.get(
        url,
        timeout=12,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        },
    )
    if response.status_code >= 400:
        raise ValueError("Pagina Spotify non recuperabile.")
    page_html = response.text

    title_match = re.search(
        r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        page_html,
        flags=re.IGNORECASE,
    )
    description_match = re.search(
        r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
        page_html,
        flags=re.IGNORECASE,
    )

    title = html.unescape(title_match.group(1).strip()) if title_match else ""
    description = html.unescape(description_match.group(1).strip()) if description_match else ""
    artist = ""

    description_parts = [part.strip() for part in description.split("·") if part.strip()]
    if len(description_parts) >= 3 and description_parts[-2].lower() in {"brano", "song"}:
        artist = description_parts[0]
    else:
        patterns = [
            r"Listen to .+? on Spotify\.\s*Song\s*·\s*(.+?)\s*·\s*\d{4}",
            r"Song\s*·\s*(.+?)\s*·\s*\d{4}",
            r"Brano\s*·\s*(.+?)\s*·\s*\d{4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, flags=re.IGNORECASE)
            if match:
                artist = match.group(1).strip()
                break

    return split_spotify_title(title, artist)


def fetch_spotify_track_metadata(url: str) -> dict:
    normalized_url = spotify_track_url(url)
    if not normalized_url:
        raise ValueError("URL Spotify non valido o non riconosciuto.")

    errors = []
    for fetcher in (fetch_spotify_oembed, fetch_spotify_open_graph):
        try:
            title, artist = fetcher(normalized_url)
        except Exception as exc:
            errors.append(str(exc))
            continue
        if title and artist:
            return {"song_title": title, "artist": artist}

    raise ValueError("Metadati Spotify incompleti. " + " ".join(errors))


def autofill_spotify_metadata(prefix: str) -> None:
    url = str(st.session_state.get(f"{prefix}_audio_url", "") or "").strip()
    status_key = f"{prefix}_spotify_status"
    last_key = f"{prefix}_spotify_last_url"

    if not url:
        st.session_state[status_key] = ""
        return
    if st.session_state.get(last_key) == url:
        return

    try:
        metadata = fetch_spotify_track_metadata(url)
    except Exception as exc:
        st.session_state[status_key] = (
            "Non e' stato possibile recuperare automaticamente i dati da Spotify. "
            "Inserisci manualmente artista e titolo della canzone. "
            f"Dettaglio: {exc}"
        )
        st.session_state[last_key] = url
        return

    st.session_state[f"{prefix}_song_title"] = metadata["song_title"]
    st.session_state[f"{prefix}_artist"] = metadata["artist"]
    st.session_state[status_key] = (
        f"Dati recuperati da Spotify: {metadata['song_title']} - {metadata['artist']}."
    )
    st.session_state[last_key] = url


def default_dedication_text(song_title: str, artist: str) -> str:
    return (
        "Ci sono canzoni che arrivano senza fare rumore, "
        "ma restano dentro piu' di tante parole.\n"
        f"Oggi ti dedico \"{song_title}\" di {artist}, "
        "perche' certe emozioni meritano di essere ascoltate fino in fondo. 🎵"
    )


def default_short_phrase() -> str:
    return "Alcune emozioni restano anche dopo l'ultima nota."


def get_secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(name, default) or "").strip()


def whatsapp_group_notify_url() -> str:
    return f"https://api.whatsapp.com/send?text={quote(WHATSAPP_NOTIFY_MESSAGE)}"


def whatsapp_paola_notify_url() -> str:
    number = re.sub(r"\D+", "", WHATSAPP_NOTIFY_PAOLA_NUMBER)
    return f"https://wa.me/{number}?text={quote(WHATSAPP_NOTIFY_MESSAGE)}"


def render_whatsapp_notification_button() -> None:
    st.link_button(
        "Invia notifica WhatsApp al gruppo FF",
        whatsapp_group_notify_url(),
        use_container_width=True,
        help=f"Testo pronto per WhatsApp. Seleziona il gruppo FF ({WHATSAPP_FF_GROUP_INVITE_URL}).",
    )
    st.link_button(
        "Invia notifica WhatsApp a Paola Ferrando",
        whatsapp_paola_notify_url(),
        use_container_width=True,
    )


def get_github_token() -> str:
    token = (
        get_secret_or_env("GITHUB_PAT")
        or get_secret_or_env("GH_TOKEN")
        or get_secret_or_env("GITHUB_TOKEN")
        or ""
    ).strip()
    if not token:
        raise ValueError(
            "Imposta GITHUB_TOKEN, GH_TOKEN oppure GITHUB_PAT. "
            "Per Pubblica subito servono permessi Contents: write e Actions: write."
        )
    return token


def github_headers() -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {get_github_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def read_github_json(repo_path: str, default: dict) -> tuple[dict, str | None]:
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    response = requests.get(
        api_url,
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=20,
    )

    if response.status_code == 404:
        return json.loads(json.dumps(default)), None
    if response.status_code != 200:
        raise ValueError(f"Lettura configurazione GitHub fallita: {response.text}")

    payload = response.json()
    raw_content = base64.b64decode(payload.get("content", "")).decode("utf-8")
    data = json.loads(raw_content)
    return data, payload.get("sha")


def write_github_json(repo_path: str, data: dict, sha: str | None, message: str) -> None:
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    payload = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(api_url, headers=github_headers(), json=payload, timeout=30)
    if response.status_code not in (200, 201):
        raise ValueError(f"Salvataggio configurazione GitHub fallito: {response.text}")


def upload_site_lock_image(uploaded_file) -> str:
    original_name = uploaded_file.name or "site-lock-image"
    ext = Path(original_name).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Formato immagine non supportato. Usa PNG, JPG, JPEG oppure WEBP.")

    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("File immagine vuoto. Riprova selezionando l'immagine.")

    safe_name = slugify(Path(original_name).stem) or "site-lock-image"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    repo_path = f"{SITE_LOCK_IMAGE_DIR}/{stamp}-{safe_name}{ext}"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    payload = {
        "message": "Aggiorna immagine fake error sito",
        "content": base64.b64encode(data).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    response = requests.put(api_url, headers=github_headers(), json=payload, timeout=40)
    if response.status_code not in (200, 201):
        raise ValueError(f"Upload immagine fake error fallito: {response.text}")
    return github_raw_url(repo_path)


def github_raw_url(repo_path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{repo_path.lstrip('/')}"


def normalize_site_lock_image_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    repo_path = value.lstrip("/")
    if not repo_path.startswith("public/"):
        repo_path = f"public/{repo_path}"
    return github_raw_url(repo_path)


def normalize_site_settings(settings: dict) -> dict:
    buttons = settings.get("buttons") if isinstance(settings, dict) else {}
    if not isinstance(buttons, dict):
        buttons = {}
    fake_error = settings.get("fakeError") if isinstance(settings, dict) else {}
    if not isinstance(fake_error, dict):
        fake_error = {}
    default_fake = DEFAULT_SITE_SETTINGS["fakeError"]
    site_effect = str(settings.get("siteEffect", DEFAULT_SITE_SETTINGS["siteEffect"]) if isinstance(settings, dict) else "").strip()
    if site_effect not in SITE_EFFECT_OPTIONS.values():
        site_effect = DEFAULT_SITE_SETTINGS["siteEffect"]
    effect_intensity = str(settings.get("effectIntensity", DEFAULT_SITE_SETTINGS["effectIntensity"]) if isinstance(settings, dict) else "").strip()
    if effect_intensity not in EFFECT_INTENSITY_OPTIONS.values():
        effect_intensity = DEFAULT_SITE_SETTINGS["effectIntensity"]
    raw_effect_backdrop = settings.get("effectBackdrop", DEFAULT_SITE_SETTINGS["effectBackdrop"]) if isinstance(settings, dict) else DEFAULT_SITE_SETTINGS["effectBackdrop"]
    effect_backdrop = raw_effect_backdrop is True or raw_effect_backdrop == 1 or str(raw_effect_backdrop).strip().lower() in {"true", "1", "on", "yes"}
    raw_effect_items = settings.get("effectFloatingItems", DEFAULT_SITE_SETTINGS["effectFloatingItems"]) if isinstance(settings, dict) else DEFAULT_SITE_SETTINGS["effectFloatingItems"]
    effect_floating_items = raw_effect_items is True or raw_effect_items == 1 or str(raw_effect_items).strip().lower() in {"true", "1", "on", "yes"}
    raw_effect_backdrop_text = settings.get("effectBackdropText", DEFAULT_SITE_SETTINGS["effectBackdropText"]) if isinstance(settings, dict) else DEFAULT_SITE_SETTINGS["effectBackdropText"]
    effect_backdrop_text = raw_effect_backdrop_text is True or raw_effect_backdrop_text == 1 or str(raw_effect_backdrop_text).strip().lower() in {"true", "1", "on", "yes"}
    return {
        "buttons": {
            "googleVote": buttons.get("googleVote", True) is not False,
            "plusVote": buttons.get("plusVote", True) is not False,
        },
        "feedbackApiUrl": str(settings.get("feedbackApiUrl", "") if isinstance(settings, dict) else "").strip(),
        "siteEffect": site_effect,
        "effectIntensity": effect_intensity,
        "effectBackdrop": effect_backdrop,
        "effectFloatingItems": effect_floating_items,
        "effectBackdropText": effect_backdrop_text,
        "fakeError": {
            "enabled": fake_error.get("enabled", False) is True,
            "title": str(fake_error.get("title") or default_fake["title"]),
            "message": str(fake_error.get("message") or default_fake["message"]),
            "buttonText": str(fake_error.get("buttonText") or default_fake["buttonText"]),
            "imagePath": normalize_site_lock_image_path(str(fake_error.get("imagePath") or "")),
            "imageMessage": str(fake_error.get("imageMessage") or default_fake["imageMessage"]),
            "adminMessage": str(fake_error.get("adminMessage") or default_fake["adminMessage"]),
        },
        "updated_at": str(settings.get("updated_at", "") if isinstance(settings, dict) else ""),
    }


def save_site_settings(updated: dict, message: str) -> None:
    _, latest_sha = read_github_json(SITE_SETTINGS_PATH, DEFAULT_SITE_SETTINGS)
    write_github_json(SITE_SETTINGS_PATH, updated, latest_sha, message)


def force_restore_site_settings() -> None:
    latest_settings, latest_sha = read_github_json(SITE_SETTINGS_PATH, DEFAULT_SITE_SETTINGS)
    latest_settings = normalize_site_settings(latest_settings)
    latest_settings["fakeError"]["enabled"] = False
    latest_settings["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_github_json(
        SITE_SETTINGS_PATH,
        latest_settings,
        latest_sha,
        "Ripristina sito da Fake Error Mode",
    )


def force_site_lock_enabled(enabled: bool) -> None:
    latest_settings, latest_sha = read_github_json(SITE_SETTINGS_PATH, DEFAULT_SITE_SETTINGS)
    latest_settings = normalize_site_settings(latest_settings)
    latest_settings["fakeError"]["enabled"] = bool(enabled)
    latest_settings["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_github_json(
        SITE_SETTINGS_PATH,
        latest_settings,
        latest_sha,
        "Attiva Fake Error Mode" if enabled else "Disattiva Fake Error Mode",
    )


def get_google_credentials(scopes: list[str]) -> Credentials:
    try:
        service_account_info = st.secrets.get("gcp_service_account", None)
    except Exception:
        service_account_info = None

    if service_account_info:
        return Credentials.from_service_account_info(
            dict(service_account_info),
            scopes=scopes,
        )

    service_account_json = get_secret_or_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        return Credentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=scopes,
        )

    if SERVICE_ACCOUNT_FILE.exists():
        return Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=scopes,
        )

    raise ValueError(
        "Credenziali Google mancanti. Su Streamlit Cloud configura la tabella "
        "[gcp_service_account] nei secrets."
    )


def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = get_google_credentials(scopes)
    sheet_id = get_secret_or_env("GOOGLE_SHEET_ID", GOOGLE_SHEET_ID)
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID mancante nei secrets o nell'ambiente.")
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id).sheet1
    ensure_sheet_headers(sheet)
    return sheet


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def ensure_sheet_headers(sheet) -> None:
    headers = [str(value or "").strip() for value in sheet.row_values(1)]
    if not headers:
        sheet.update("A1", [SHEET_COLUMNS], value_input_option="USER_ENTERED")
        return

    missing = [col for col in SHEET_COLUMNS if col not in headers]
    if not missing:
        return

    updated_headers = headers + missing
    end_col = column_letter(len(updated_headers))
    sheet.update(f"A1:{end_col}1", [updated_headers], value_input_option="USER_ENTERED")


def load_sheet_records() -> list[dict]:
    sheet = get_sheet()
    rows = sheet.get_all_records()
    records = []
    for idx, row in enumerate(rows, start=2):
        record = {col: str(row.get(col, "") or "") for col in SHEET_COLUMNS}
        record["_row_number"] = idx
        records.append(record)
    return records


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def draft_path(prefix: str) -> Path:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]+", "-", prefix).strip("-") or "draft"
    return DRAFT_DIR / f"{safe_prefix}.json"


def has_form_data(prefix: str) -> bool:
    return any(st.session_state.get(f"{prefix}_{col}") for col in SHEET_COLUMNS)


def restore_form_draft(prefix: str) -> bool:
    if has_form_data(prefix):
        return False

    path = draft_path(prefix)
    if not path.exists():
        return False

    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False

    values = draft.get("values") if isinstance(draft, dict) else {}
    if not isinstance(values, dict):
        return False

    for col in SHEET_COLUMNS:
        if col in values:
            st.session_state[f"{prefix}_{col}"] = values.get(col, "")

    date_value = values.get("date")
    if date_value:
        st.session_state[f"{prefix}_date_picker_value"] = parse_date_value(date_value)

    image = draft.get("image")
    if isinstance(image, dict) and image.get("data_b64"):
        try:
            st.session_state[f"{prefix}_uploaded_image_snapshot"] = UploadedImageSnapshot(
                image.get("name") or f"{prefix}-immagine.jpg",
                image.get("type") or "application/octet-stream",
                base64.b64decode(image["data_b64"]),
            )
        except Exception:
            pass

    st.session_state[f"{prefix}_draft_restored"] = True
    return True


def save_form_draft(prefix: str, uploaded_snapshot=None) -> None:
    values = collect_form_state(prefix)
    has_values = any(str(value or "").strip() for value in values.values())
    if not has_values and uploaded_snapshot is None:
        return

    draft = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "values": values,
    }
    if uploaded_snapshot is not None:
        data = uploaded_snapshot.getvalue()
        if data:
            draft["image"] = {
                "name": uploaded_snapshot.name,
                "type": getattr(uploaded_snapshot, "type", "") or "application/octet-stream",
                "data_b64": base64.b64encode(data).decode("ascii"),
            }

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    draft_path(prefix).write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")


def clear_form_draft(prefix: str) -> None:
    path = draft_path(prefix)
    if path.exists():
        path.unlink()


def remember_uploaded_image(prefix: str, uploaded_file):
    snapshot_key = f"{prefix}_uploaded_image_snapshot"
    if uploaded_file is None:
        return st.session_state.get(snapshot_key)

    data = uploaded_file.getvalue()
    if not data:
        st.warning("Il browser ha inviato un file vuoto. Riprova selezionando la foto dalla galleria.")
        return st.session_state.get(snapshot_key)

    snapshot = UploadedImageSnapshot(
        uploaded_file.name or f"{prefix}-immagine.jpg",
        getattr(uploaded_file, "type", "") or "application/octet-stream",
        data,
    )
    st.session_state[snapshot_key] = snapshot
    return snapshot


def optimize_uploaded_image(uploaded_file) -> tuple[bytes, dict]:
    from PIL import Image, ImageFile, ImageOps

    ImageFile.LOAD_TRUNCATED_IMAGES = True

    original_bytes = uploaded_file.getvalue()
    original_name = uploaded_file.name or "immagine"
    original_ext = Path(original_name).suffix.lower()

    if original_ext in {".heic", ".heif"}:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception as exc:
            raise ValueError(
                "Questa sembra una foto HEIC/Live Photo da telefono, ma manca il "
                "supporto HEIC. Installa/aggiorna le dipendenze con pillow-heif "
                "oppure esporta la foto come JPEG normale."
            ) from exc

    try:
        img = Image.open(io.BytesIO(original_bytes))
        original_format = img.format or original_ext.replace(".", "").upper() or "UNKNOWN"
        frame_count = getattr(img, "n_frames", 1) or 1
        is_animated = bool(getattr(img, "is_animated", False) or frame_count > 1)
        if is_animated:
            img.seek(frame_count - 1)
            img.load()
            img = img.copy()
        else:
            img.load()
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        file_type = getattr(uploaded_file, "type", "") or "tipo non dichiarato"
        raise ValueError(
            "Immagine non leggibile. Se e' una Live Photo/foto in movimento, "
            "prova a esportarla come JPEG statico oppure disattiva Live Photo "
            "prima dello scatto. "
            f"Dettagli: file={original_name}, tipo={file_type}, "
            f"peso={format_bytes(len(original_bytes))}, errore={exc}"
        ) from exc

    original_size = img.size
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        alpha = img.convert("RGBA").getchannel("A")
        background.paste(img.convert("RGBA"), mask=alpha)
        img = background
    else:
        img = img.convert("RGB")

    def encode_webp(source_img, max_side: int, quality: int) -> tuple[bytes, tuple[int, int], int, int]:
        resized = source_img.copy()
        resized.thumbnail((max_side, max_side), Image.LANCZOS)
        output = io.BytesIO()
        resized.save(output, format="WEBP", quality=quality, method=6)
        return output.getvalue(), resized.size, max_side, quality

    optimized_bytes, optimized_size, used_side, used_quality = encode_webp(
        img,
        UPLOAD_IMAGE_MAX_SIDE,
        UPLOAD_IMAGE_WEBP_QUALITY,
    )

    for side, quality in ((1280, 76), (1200, 74), (1080, 72), (960, 70), (840, 66), (720, 62)):
        if len(optimized_bytes) <= UPLOAD_IMAGE_TARGET_BYTES:
            break
        optimized_bytes, optimized_size, used_side, used_quality = encode_webp(img, side, quality)

    if len(optimized_bytes) > UPLOAD_IMAGE_HARD_MAX_BYTES:
        raise ValueError(
            "La foto in movimento resta troppo pesante anche dopo la conversione "
            f"({format_bytes(len(optimized_bytes))}). Esportala come foto JPEG "
            "statica dalla galleria e ricaricala."
        )

    return optimized_bytes, {
        "original_bytes": len(original_bytes),
        "optimized_bytes": len(optimized_bytes),
        "original_size": original_size,
        "optimized_size": optimized_size,
        "original_format": original_format,
        "used_max_side": used_side,
        "used_quality": used_quality,
        "frame_count": frame_count,
        "is_animated": is_animated,
    }


def upload_image_to_github(uploaded_file, asset_id: str) -> str:
    original_name = uploaded_file.name or ""
    ext = Path(original_name).suffix.lower()
    if ext not in VALID_IMAGE_EXTS:
        st.warning(
            f"Estensione '{ext or 'nessuna'}' non riconosciuta: provo comunque a leggere "
            "il file come immagine."
        )

    optimized_bytes, image_info = optimize_uploaded_image(uploaded_file)
    upload_name = f"{asset_id}.webp"
    repo_path = f"{UPLOAD_DIR}/{upload_name}"
    token = get_github_token()
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    sha = None
    existing = requests.get(
        api_url,
        headers=headers,
        params={"ref": GITHUB_BRANCH},
        timeout=20,
    )
    if existing.status_code == 200:
        sha = existing.json().get("sha")
    elif existing.status_code != 404:
        raise ValueError(f"Verifica file GitHub fallita: {existing.text}")

    content_b64 = base64.b64encode(optimized_bytes).decode("ascii")
    payload = {
        "message": f"Upload immagine dedica {asset_id}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(api_url, headers=headers, json=payload, timeout=60)
    if response.status_code not in (200, 201):
        raise ValueError(f"Upload GitHub fallito: {response.text}")

    st.caption(
        "Immagine ottimizzata: "
        f"{format_bytes(image_info['original_bytes'])} -> "
        f"{format_bytes(image_info['optimized_bytes'])}, "
        f"{image_info['original_size'][0]}x{image_info['original_size'][1]} -> "
        f"{image_info['optimized_size'][0]}x{image_info['optimized_size'][1]} "
        f"(max {image_info['used_max_side']}px, qualita' {image_info['used_quality']}, "
        f"frame usati: 1/{image_info['frame_count']})."
    )
    return repo_path


def dispatch_deploy_pages() -> None:
    """Avvia manualmente il workflow deploy.yml (Build + Deploy su GitHub Pages)."""
    token = get_github_token()
    deploy_workflow = os.environ.get("DEPLOY_WORKFLOW_FILE", "deploy.yml")
    api_url = (
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/"
        f"{deploy_workflow}/dispatches"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": GITHUB_BRANCH}
    response = requests.post(api_url, headers=headers, json=payload, timeout=20)
    if response.status_code != 204:
        if response.status_code == 403:
            raise ValueError(
                "Avvio deploy GitHub Pages negato: il token GitHub non ha "
                "permesso Actions: write. Aggiorna il PAT con Actions: Read and write."
            )
        raise ValueError(f"Avvio deploy GitHub Pages fallito: {response.text}")


def dispatch_daily_publish(date_value: str, dedication_id: str = '', force_republish: bool = True) -> None:
    token = get_github_token()
    api_url = (
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/"
        f"{DAILY_WORKFLOW_FILE}/dispatches"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "ref": GITHUB_BRANCH,
        "inputs": {
            "date": date_value,
            "dedication_id": dedication_id,
            "force_republish": "true" if force_republish else "false",
            "dry_run": "false",
        },
    }
    response = requests.post(api_url, headers=headers, json=payload, timeout=20)
    if response.status_code != 204:
        if response.status_code == 403:
            raise ValueError(
                "Avvio workflow GitHub Actions negato: il token GitHub non ha "
                "permesso Actions: write sul repository. Crea/aggiorna un PAT "
                "fine-grained con Repository access sul repo dediche-musicali e "
                "permessi Contents: Read and write + Actions: Read and write, "
                "poi salvalo nei secrets Streamlit come GITHUB_PAT."
            )
        raise ValueError(f"Avvio workflow GitHub Actions fallito: {response.text}")


def make_default_id(date_value: str, song_title: str, artist: str) -> str:
    return f"{date_value}-{slugify(song_title)}-{slugify(artist)}"


def default_form_values() -> dict:
    return {
        "id": "",
        "date": tomorrow_rome_date().isoformat(),
        "status": "scheduled",
        "song_title": "",
        "artist": "",
        "dedication_title": "La dedica del giorno",
        "dedication_text": "",
        "audio_url": "",
        "audio_type": "spotify",
        "vote_url": DEFAULT_VOTE_URL,
        "image_mode": "raw",
        "image_source": "",
        "short_phrase": "",
        "tags": "musica,emozioni,dedica",
        "seo_title": "",
        "seo_description": "",
        "image_alt": "",
        "video_type": "",
        "video_url": "",
        "video_poster": "",
        "video_title": "",
        "video_description": "",
    }


def build_row_from_values(values: dict) -> list[str]:
    return [str(values.get(col, "") or "").strip() for col in SHEET_COLUMNS]


def prepare_values(values: dict) -> dict:
    cleaned = {col: str(values.get(col, "") or "").strip() for col in SHEET_COLUMNS}
    cleaned["date"] = normalize_date(cleaned["date"])

    if not cleaned["song_title"]:
        raise ValueError("Inserisci il titolo della canzone.")
    if not cleaned["artist"]:
        raise ValueError("Inserisci l'artista.")
    if not cleaned["audio_url"].startswith("https://open.spotify.com/"):
        raise ValueError("Inserisci un URL Spotify valido.")
    # dedication_text e short_phrase sono facoltativi: si possono lasciare vuoti e compilare dopo
    if cleaned["status"] not in VALID_STATUSES:
        raise ValueError(f"Status non valido. Usa uno tra: {', '.join(VALID_STATUSES)}")
    if cleaned["image_mode"] not in VALID_IMAGE_MODES:
        raise ValueError(f"image_mode non valido. Usa uno tra: {', '.join(VALID_IMAGE_MODES)}")

    cleaned["video_type"] = cleaned["video_type"].lower()
    if cleaned["video_type"] not in VALID_VIDEO_TYPES:
        raise ValueError("video_type non valido. Usa youtube, mp4 oppure external.")
    if cleaned["video_type"] and not cleaned["video_url"]:
        raise ValueError(f"video_url obbligatorio per video_type={cleaned['video_type']}.")
    if cleaned["video_url"] and not cleaned["video_type"]:
        raise ValueError("Compila video_type se inserisci video_url.")
    if cleaned["video_url"] and not cleaned["video_url"].startswith("https://"):
        raise ValueError("video_url deve essere un URL https valido.")
    if cleaned["video_type"] == "youtube" and not re.search(
        r"(youtube\.com/(watch\?v=|embed/|shorts/)|youtu\.be/)[A-Za-z0-9_-]{11}",
        cleaned["video_url"],
    ):
        raise ValueError("Per video_type=youtube inserisci un URL YouTube valido.")
    if cleaned["video_type"] == "mp4" and not cleaned["video_url"].split("?", 1)[0].lower().endswith(".mp4"):
        raise ValueError("Per video_type=mp4 video_url deve puntare a un file .mp4.")

    if not cleaned["id"]:
        cleaned["id"] = make_default_id(cleaned["date"], cleaned["song_title"], cleaned["artist"])
    if not cleaned["dedication_title"]:
        cleaned["dedication_title"] = "La dedica del giorno"
    if not cleaned["audio_type"]:
        cleaned["audio_type"] = "spotify"
    if not cleaned["vote_url"]:
        cleaned["vote_url"] = DEFAULT_VOTE_URL
    if not cleaned["tags"]:
        cleaned["tags"] = "musica,emozioni,dedica"
    if not cleaned["seo_title"]:
        cleaned["seo_title"] = f"{cleaned['song_title']} - {cleaned['artist']} | {SITE_NAME}"
    if not cleaned["seo_description"]:
        cleaned["seo_description"] = (
            f"Dedica musicale del giorno con \"{cleaned['song_title']}\" "
            f"di {cleaned['artist']}."
        )
    if not cleaned["image_alt"]:
        cleaned["image_alt"] = f"Dedica musicale {cleaned['song_title']} di {cleaned['artist']}"

    return cleaned


def append_to_google_sheet(row: list[str]) -> None:
    sheet = get_sheet()
    sheet.append_row(row, value_input_option="USER_ENTERED")


def update_google_sheet_row(row_number: int, row: list[str]) -> None:
    sheet = get_sheet()
    end_col = column_letter(len(SHEET_COLUMNS))
    sheet.update(f"A{row_number}:{end_col}{row_number}", [row], value_input_option="USER_ENTERED")


def find_sheet_rows_by_id(dedication_id: str) -> list[int]:
    if not dedication_id:
        return []

    sheet = get_sheet()
    rows = sheet.get_all_records()
    matches = []
    for idx, row in enumerate(rows, start=2):
        if str(row.get("id", "") or "").strip() == dedication_id:
            matches.append(idx)
    return matches


def upsert_google_sheet_row(row: list[str], dedication_id: str) -> tuple[str, int | None, int]:
    matching_rows = find_sheet_rows_by_id(dedication_id)
    if matching_rows:
        update_google_sheet_row(matching_rows[0], row)
        return "updated", matching_rows[0], len(matching_rows)

    append_to_google_sheet(row)
    return "inserted", None, 0


def add_to_active_text(value: str, prefix: str) -> None:
    target = st.session_state.get(f"{prefix}_active_text_target", "dedication_text")
    key = f"{prefix}_short_phrase" if target == "short_phrase" else f"{prefix}_dedication_text"
    current = st.session_state.get(key, "")
    st.session_state[key] = f"{current}{value}"


def add_custom_to_active_text(prefix: str) -> None:
    value = st.session_state.get(f"{prefix}_custom_emoji", "").strip()
    if value:
        add_to_active_text(value, prefix)


def clear_texts(prefix: str) -> None:
    st.session_state[f"{prefix}_dedication_text"] = ""
    st.session_state[f"{prefix}_short_phrase"] = ""


def generate_dedication_text(prefix: str) -> None:
    """Genera solo il testo della dedica (dedication_text), senza toccare short_phrase."""
    song = st.session_state.get(f"{prefix}_song_title", "").strip()
    artist = st.session_state.get(f"{prefix}_artist", "").strip()
    if not song or not artist:
        st.session_state[f"{prefix}_gen_text_warning"] = True
        return
    st.session_state[f"{prefix}_gen_text_warning"] = False
    st.session_state[f"{prefix}_dedication_text"] = default_dedication_text(song, artist)


def generate_short_phrase(prefix: str) -> None:
    """Genera solo la frase breve (short_phrase), senza toccare dedication_text."""
    st.session_state[f"{prefix}_short_phrase"] = default_short_phrase()


def generate_preview(prefix: str) -> None:
    """Genera entrambi i campi testo in un colpo solo."""
    song = st.session_state.get(f"{prefix}_song_title", "").strip()
    artist = st.session_state.get(f"{prefix}_artist", "").strip()
    if not song or not artist:
        st.session_state[f"{prefix}_gen_text_warning"] = True
        return
    st.session_state[f"{prefix}_gen_text_warning"] = False
    st.session_state[f"{prefix}_dedication_text"] = default_dedication_text(song, artist)
    st.session_state[f"{prefix}_short_phrase"] = default_short_phrase()


def set_form_state(prefix: str, values: dict) -> None:
    defaults = default_form_values()
    defaults.update({col: values.get(col, "") for col in SHEET_COLUMNS})
    for col in SHEET_COLUMNS:
        st.session_state[f"{prefix}_{col}"] = defaults[col]
    st.session_state[f"{prefix}_date_picker_value"] = parse_date_value(defaults["date"])
    st.session_state.pop(f"{prefix}_date_picker", None)
    st.session_state[f"{prefix}_spotify_status"] = ""
    st.session_state[f"{prefix}_spotify_last_url"] = str(defaults.get("audio_url", "") or "").strip()


def init_form_state(prefix: str, values: dict | None = None) -> None:
    defaults = default_form_values()
    if values:
        defaults.update({col: values.get(col, "") for col in SHEET_COLUMNS})
    for col, value in defaults.items():
        st.session_state.setdefault(f"{prefix}_{col}", value)
    st.session_state.setdefault(f"{prefix}_date_picker_value", parse_date_value(defaults["date"]))
    st.session_state.setdefault(f"{prefix}_spotify_status", "")
    st.session_state.setdefault(f"{prefix}_spotify_last_url", "")
    st.session_state.setdefault(f"{prefix}_active_text_target", "dedication_text")


def collect_form_state(prefix: str) -> dict:
    return {col: st.session_state.get(f"{prefix}_{col}", "") for col in SHEET_COLUMNS}


def render_emoji_picker(prefix: str) -> None:
    st.caption("Clicca prima nel testo o nella frase breve, poi inserisci l'emoji.")
    st.radio(
        "Campo attivo",
        options=("dedication_text", "short_phrase"),
        horizontal=True,
        key=f"{prefix}_active_text_target",
    )

    st.markdown("**Emoji rapide**")
    cols = st.columns(len(QUICK_EMOJIS))
    for col, emoji in zip(cols, QUICK_EMOJIS):
        col.button(
            emoji,
            key=f"{prefix}_quick_{emoji}",
            on_click=add_to_active_text,
            args=(emoji, prefix),
        )

    with st.expander("Emoji estese"):
        for row_start in range(0, len(EXTENDED_EMOJIS), 8):
            row = EXTENDED_EMOJIS[row_start:row_start + 8]
            cols = st.columns(len(row))
            for col, emoji in zip(cols, row):
                col.button(
                    emoji,
                    key=f"{prefix}_extended_{row_start}_{emoji}",
                    on_click=add_to_active_text,
                    args=(emoji, prefix),
                )

    st.text_input("Emoji o testo speciale libero", key=f"{prefix}_custom_emoji")
    st.button(
        "Inserisci nel campo attivo",
        use_container_width=True,
        on_click=add_custom_to_active_text,
        args=(prefix,),
        key=f"{prefix}_insert_custom_emoji",
    )


def render_dedication_form(prefix: str, existing_image_source: str = ""):
    st.subheader("Dati principali")
    st.text_input("ID", key=f"{prefix}_id", help="Lascia vuoto per generarne uno automaticamente.")
    date_key = f"{prefix}_date_picker"
    date_kwargs = {
        "label": "Data",
        "format": "DD/MM/YYYY",
        "key": date_key,
        "on_change": sync_date_picker,
        "args": (prefix,),
    }
    if date_key not in st.session_state:
        date_kwargs["value"] = parse_date_value(st.session_state.get(f"{prefix}_date_picker_value") or st.session_state.get(f"{prefix}_date"))
    selected_date = st.date_input(**date_kwargs)
    st.session_state[f"{prefix}_date"] = parse_date_value(selected_date).isoformat()
    st.selectbox(
        "status",
        VALID_STATUSES,
        index=VALID_STATUSES.index(st.session_state.get(f"{prefix}_status", "scheduled"))
        if st.session_state.get(f"{prefix}_status", "scheduled") in VALID_STATUSES else 1,
        key=f"{prefix}_status",
    )
    st.text_input(
        "URL Spotify",
        key=f"{prefix}_audio_url",
        on_change=autofill_spotify_metadata,
        args=(prefix,),
        placeholder="https://open.spotify.com/track/...",
    )
    spotify_status = st.session_state.get(f"{prefix}_spotify_status", "")
    if spotify_status:
        if spotify_status.startswith("Dati recuperati"):
            st.success(spotify_status)
        else:
            st.warning(spotify_status)
    if st.button("Recupera dati da Spotify", use_container_width=True, key=f"{prefix}_fetch_spotify"):
        st.session_state[f"{prefix}_spotify_last_url"] = ""
        autofill_spotify_metadata(prefix)
    st.text_input("Titolo canzone", key=f"{prefix}_song_title")
    st.text_input("Artista", key=f"{prefix}_artist")
    st.text_input("Titolo dedica", key=f"{prefix}_dedication_title")

    st.subheader("Immagine")
    image_mode = st.selectbox(
        "image_mode",
        VALID_IMAGE_MODES,
        index=VALID_IMAGE_MODES.index(st.session_state.get(f"{prefix}_image_mode", "raw"))
        if st.session_state.get(f"{prefix}_image_mode", "raw") in VALID_IMAGE_MODES else 0,
        key=f"{prefix}_image_mode",
    )
    uploaded_file = st.file_uploader(
        "Nuova immagine per raw/upload",
        disabled=image_mode not in ("raw", "upload"),
        key=f"{prefix}_uploaded_file",
        help="Puoi caricare JPG/JPEG, PNG, WEBP, GIF o HEIC. Se il nome file e' strano provo comunque a leggerlo.",
    )
    uploaded_snapshot = remember_uploaded_image(prefix, uploaded_file)
    st.text_input("image_source", key=f"{prefix}_image_source")
    if existing_image_source and not uploaded_snapshot:
        st.caption(f"Immagine attuale: {existing_image_source}")
    if uploaded_snapshot:
        uploaded_bytes = uploaded_snapshot.getvalue()
        uploaded_size = len(uploaded_bytes)
        uploaded_type = getattr(uploaded_snapshot, "type", "") or "tipo non dichiarato"
        date_text = st.session_state.get(f"{prefix}_date", "")
        song = st.session_state.get(f"{prefix}_song_title", "")
        artist = st.session_state.get(f"{prefix}_artist", "")
        preview_id = st.session_state.get(f"{prefix}_id", "").strip()
        if not preview_id and date_text and song and artist:
            preview_id = make_default_id(normalize_date(date_text), song, artist)
        with st.expander("Anteprima immagine caricata", expanded=True):
            try:
                st.image(uploaded_bytes, use_container_width=True)
            except Exception as exc:
                st.warning(
                    "Anteprima non disponibile, ma provo comunque a convertirla al salvataggio. "
                    f"Dettaglio: {exc}"
                )
            st.caption(
                "Pronta per il salvataggio: "
                f"{preview_id or 'ID-DELLA-DEDICA'}.webp "
                f"({format_bytes(uploaded_size)}, {uploaded_type}). "
                "Se su mobile il selettore si chiude, questa copia resta in memoria fino al salvataggio."
            )

    st.subheader("Testi")
    st.caption("Facoltativi: puoi salvare anche senza compilarli e aggiungerli in seguito.")

    # --- dedication_text ---
    st.text_area(
        "Testo della dedica (dedication_text)",
        key=f"{prefix}_dedication_text",
        height=180,
        placeholder="Scrivi il testo manualmente oppure clicca \"Genera testo dedica\"...",
    )
    if st.session_state.get(f"{prefix}_gen_text_warning"):
        st.warning("Inserisci prima titolo canzone e artista per generare il testo.")
    st.button(
        "✍️ Genera testo dedica",
        use_container_width=True,
        on_click=generate_dedication_text,
        args=(prefix,),
        key=f"{prefix}_gen_dedication_text",
        help="Genera un testo di dedica standard basato su titolo e artista.",
    )

    # --- short_phrase ---
    st.text_input(
        "Frase breve (short_phrase)",
        key=f"{prefix}_short_phrase",
        placeholder="Una breve frase evocativa, oppure clicca \"Genera frase\"...",
    )
    st.button(
        "💬 Genera frase breve",
        use_container_width=True,
        on_click=generate_short_phrase,
        args=(prefix,),
        key=f"{prefix}_gen_short_phrase",
        help="Inserisce la frase breve predefinita.",
    )

    st.text_input("tags", key=f"{prefix}_tags")

    with st.expander("SEO e opzioni avanzate"):
        st.text_input("audio_type", key=f"{prefix}_audio_type")
        st.text_input("vote_url", key=f"{prefix}_vote_url")
        st.text_input("seo_title", key=f"{prefix}_seo_title")
        st.text_area("seo_description", key=f"{prefix}_seo_description", height=80)
        st.text_input("image_alt", key=f"{prefix}_image_alt")

    with st.expander("Video opzionale"):
        st.selectbox(
            "video_type",
            VALID_VIDEO_TYPES,
            index=VALID_VIDEO_TYPES.index(st.session_state.get(f"{prefix}_video_type", ""))
            if st.session_state.get(f"{prefix}_video_type", "") in VALID_VIDEO_TYPES else 0,
            key=f"{prefix}_video_type",
            help="Lascia vuoto se questa dedica non ha un video.",
        )
        st.text_input("video_url", key=f"{prefix}_video_url")
        st.text_input(
            "video_poster",
            key=f"{prefix}_video_poster",
            help="Immagine anteprima. Se vuota il sito usa il placeholder standard.",
        )
        st.text_input("video_title", key=f"{prefix}_video_title")
        st.text_area("video_description", key=f"{prefix}_video_description", height=80)

    st.divider()
    col_preview, col_clear = st.columns(2)
    col_preview.button(
        "✍️ Genera entrambi i testi",
        use_container_width=True,
        on_click=generate_preview,
        args=(prefix,),
        key=f"{prefix}_generate_preview",
        help="Genera sia il testo della dedica sia la frase breve in un colpo solo.",
    )
    col_clear.button(
        "🗑️ Pulisci testi",
        use_container_width=True,
        on_click=clear_texts,
        args=(prefix,),
        key=f"{prefix}_clear_texts",
    )

    render_emoji_picker(prefix)
    return uploaded_snapshot


def save_dedication(prefix: str, uploaded_file, mode: str, row_number: int | None = None) -> dict:
    values = prepare_values(collect_form_state(prefix))
    if uploaded_file is not None:
        with st.spinner("Caricamento immagine su GitHub..."):
            values["image_source"] = upload_image_to_github(uploaded_file, values["id"])

    if values["image_mode"] in ("raw", "upload") and not values["image_source"]:
        raise ValueError(f"Seleziona un'immagine o compila image_source per image_mode={values['image_mode']}.")

    row = build_row_from_values(values)
    if mode == "edit":
        matching_rows = find_sheet_rows_by_id(values["id"])
        if row_number is None:
            if not matching_rows:
                raise ValueError("Riga Google Sheet non trovata per la modifica.")
            row_number = matching_rows[0]
        with st.spinner("Aggiornamento riga nel Google Sheet..."):
            update_google_sheet_row(row_number, row)
        values["_save_action"] = "updated"
        values["_save_row_number"] = row_number
        values["_duplicate_count"] = len(set(matching_rows + [row_number]))
    else:
        with st.spinner("Salvataggio nel Google Sheet..."):
            action, saved_row_number, duplicate_count = upsert_google_sheet_row(row, values["id"])
        values["_save_action"] = action
        values["_save_row_number"] = saved_row_number
        values["_duplicate_count"] = duplicate_count

    return values


def save_and_optionally_publish(prefix: str, uploaded_file, mode: str, publish_now: bool,
                                row_number: int | None = None) -> None:
    values = save_dedication(prefix, uploaded_file, mode, row_number=row_number)
    clear_form_draft(prefix)
    action = "aggiornata" if values.get("_save_action") == "updated" else "programmata"
    st.success(f"Dedica {action} per il {values['date']}.")
    if values.get("_duplicate_count", 0) > 1:
        st.warning(
            "Attenzione: nel Google Sheet esistono gia' piu' righe con questo ID. "
            "Ho aggiornato la prima riga trovata; conviene eliminare manualmente le copie."
        )

    if publish_now:
        with st.spinner("Avvio workflow GitHub Actions..."):
            dispatch_daily_publish(values["date"], dedication_id=values["id"], force_republish=True)
        st.success(
            "Workflow daily-publish avviato. Il sito verra' aggiornato appena GitHub Actions termina."
        )
    render_whatsapp_notification_button()


def render_new_dedication() -> None:
    restore_form_draft("new")
    init_form_state("new")
    st.title("Nuova dedica musicale")
    st.caption("Crea una nuova riga nel Google Sheet e, se vuoi, pubblicala subito.")
    if st.session_state.pop("new_draft_restored", False):
        st.info("Ho ripristinato la bozza locale dell'ultima dedica non salvata.")

    uploaded_file = render_dedication_form("new")
    save_form_draft("new", uploaded_file)

    col_save, col_publish = st.columns(2)
    save_clicked = col_save.button(
        "Salva nel Google Sheet",
        use_container_width=True,
        key="new_save_sheet",
    )
    publish_clicked = col_publish.button(
        "Pubblica subito",
        type="primary",
        use_container_width=True,
        key="new_publish_now",
    )

    if save_clicked or publish_clicked:
        try:
            save_and_optionally_publish(
                "new",
                uploaded_file,
                mode="new",
                publish_now=publish_clicked,
            )
        except Exception as exc:
            st.error(str(exc))


def format_record_label(record: dict) -> str:
    return (
        f"{record.get('date', '')} - {record.get('song_title', '')} "
        f"({record.get('artist', '')}) [{record.get('status', '')}]"
    )


def render_historical() -> None:
    st.title("Historical")
    st.caption("Legge le dediche dal Google Sheet e aggiorna la riga selezionata.")

    if st.button("Ricarica Google Sheet", key="hist_reload_sheet"):
        st.cache_data.clear()

    try:
        records = load_sheet_records()
    except Exception as exc:
        st.error(str(exc))
        return

    if not records:
        st.info("Nessuna dedica trovata nel Google Sheet.")
        return

    records = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
    options = {format_record_label(record): record for record in records}
    selected_label = st.selectbox("Seleziona dedica", list(options.keys()))
    selected = options[selected_label]

    selected_key = f"{selected.get('_row_number')}-{selected.get('id')}"
    if st.session_state.get("historical_loaded_key") != selected_key:
        set_form_state("hist", selected)
        st.session_state["historical_loaded_key"] = selected_key

    uploaded_file = render_dedication_form("hist", existing_image_source=selected.get("image_source", ""))

    col_save, col_publish = st.columns(2)
    save_clicked = col_save.button(
        "Salva modifiche",
        use_container_width=True,
        key="hist_save_changes",
    )
    publish_clicked = col_publish.button(
        "Pubblica subito",
        type="primary",
        use_container_width=True,
        key="hist_publish_now",
    )

    if save_clicked or publish_clicked:
        try:
            save_and_optionally_publish(
                "hist",
                uploaded_file,
                mode="edit",
                publish_now=publish_clicked,
                row_number=int(selected["_row_number"]),
            )
            st.session_state["historical_loaded_key"] = ""
        except Exception as exc:
            st.error(str(exc))


def configured_feedback_api_url() -> str:
    configured = (
        get_secret_or_env("DDGFF_FEEDBACK_API_URL")
        or get_secret_or_env("PUBLIC_DDGFF_FEEDBACK_API_URL")
        or get_secret_or_env("FEEDBACK_API_URL")
    )
    if configured:
        return configured.rstrip("/")
    try:
        settings, _ = read_github_json(SITE_SETTINGS_PATH, DEFAULT_SITE_SETTINGS)
        return str(settings.get("feedbackApiUrl", "") or "").strip().rstrip("/")
    except Exception:
        return ""


def visits_read_headers() -> dict:
    token = get_secret_or_env("VISITS_READ_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


@st.cache_data(ttl=60)
def load_site_visits() -> list[dict]:
    api_url = configured_feedback_api_url()
    if api_url:
        response = requests.get(
            f"{api_url}/visits",
            headers=visits_read_headers(),
            timeout=20,
        )
        if response.status_code != 200:
            raise ValueError(f"Lettura visite dal Worker fallita: {response.text}")
        payload = response.json()
        return payload.get("visits", []) if isinstance(payload, dict) else []

    local_path = Path(__file__).resolve().parents[1] / VISITS_PATH
    if local_path.exists():
        payload = json.loads(local_path.read_text(encoding="utf-8"))
        return payload.get("visits", []) if isinstance(payload, dict) else []

    payload, _ = read_github_json(VISITS_PATH, {"visits": []})
    return payload.get("visits", []) if isinstance(payload, dict) else []


def visits_dataframe(visits: list[dict]) -> pd.DataFrame:
    rows = []
    for visit in visits:
        if not isinstance(visit, dict):
            continue
        user_key = str(visit.get("userKey") or visit.get("user_key") or "").strip()
        user_name = str(visit.get("userName") or visit.get("user_name") or "Utente").strip()
        visited_at = str(visit.get("visitedAt") or visit.get("visited_at") or "").strip()
        visit_date = str(visit.get("visitDate") or visit.get("visit_date") or visited_at[:10]).strip()
        if not user_key or not user_name or not visited_at or not visit_date:
            continue
        rows.append(
            {
                "visitId": str(visit.get("visitId") or visit.get("visit_id") or "").strip(),
                "userKey": user_key,
                "utente": user_name,
                "visitedAt": visited_at,
                "data": visit_date,
                "pagina": str(visit.get("page") or "/").strip() or "/",
                "source": str(visit.get("source") or "site").strip(),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["visitId", "userKey", "utente", "visitedAt", "data", "ora", "pagina", "source"])
    df["datetime"] = pd.to_datetime(df["visitedAt"], errors="coerce", utc=True)
    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["ora"] = df["datetime"].dt.tz_convert("Europe/Rome").dt.strftime("%H:%M:%S")
    df["data"] = df["data_dt"].astype(str)
    return df.sort_values("datetime", ascending=False)


def load_visits_json_for_edit() -> tuple[dict, str | None]:
    payload, sha = read_github_json(VISITS_PATH, {"visits": []})
    if not isinstance(payload, dict):
        payload = {"visits": []}
    if not isinstance(payload.get("visits"), list):
        payload["visits"] = []
    return payload, sha


def save_visits_json(visits: list[dict], sha: str | None, message: str) -> None:
    write_github_json(VISITS_PATH, {"visits": visits}, sha, message)
    load_site_visits.clear()


def list_github_json_files(repo_dir: str) -> list[dict]:
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_dir.strip('/')}"
    response = requests.get(
        api_url,
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"Lettura directory GitHub fallita: {response.text}")
    items = response.json()
    return [
        item for item in items
        if item.get("type") == "file" and str(item.get("name", "")).endswith(".json")
    ]


@st.cache_data(ttl=60)
def load_garbage_dedications() -> list[dict]:
    dedications = []
    for item in list_github_json_files(DEDICATIONS_DIR):
        data, sha = read_github_json(item["path"], {})
        if isinstance(data, dict):
            dedications.append({"path": item["path"], "sha": sha, "data": data})
    return dedications


def dedication_label(dedication: dict) -> str:
    return (
        f"{dedication.get('date', '')} - {dedication.get('song_title', '')} "
        f"({dedication.get('artist', '')})"
    ).strip()


def feedback_garbage_dataframe(dedications: list[dict]) -> pd.DataFrame:
    rows = []
    for item in dedications:
        data = item["data"]
        path = item["path"]
        dedication_id = str(data.get("id") or Path(path).stem)
        label = dedication_label(data)
        for field_name, type_label in (
            ("votes", "voto"),
            ("thoughts", "pensiero"),
            ("reactionEntries", "reaction"),
        ):
            entries = data.get(field_name)
            if not isinstance(entries, list):
                continue
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                user_key = str(entry.get("userKey") or entry.get("user_key") or entry.get("userName") or "").strip()
                user_name = str(entry.get("userName") or entry.get("user_name") or "Utente").strip()
                if type_label == "pensiero":
                    value = str(entry.get("text") or "").strip()
                else:
                    value = str(entry.get("value") or entry.get("reaction") or "").strip()
                rows.append({
                    "entryId": f"{path}|{field_name}|{index}",
                    "path": path,
                    "dedicationId": dedication_id,
                    "dedica": label,
                    "tipo": type_label,
                    "field": field_name,
                    "index": index,
                    "utente": user_name,
                    "userKey": user_key,
                    "valore": value,
                    "createdAt": str(entry.get("createdAt") or entry.get("created_at") or ""),
                    "updatedAt": str(entry.get("updatedAt") or entry.get("updated_at") or ""),
                })
    if not rows:
        return pd.DataFrame(columns=["entryId", "path", "dedicationId", "dedica", "tipo", "field", "index", "utente", "userKey", "valore"])
    return pd.DataFrame(rows)


def sync_dedication_feedback_fields(dedication: dict) -> dict:
    votes = [item for item in dedication.get("votes", []) if isinstance(item, dict)]
    thoughts = [item for item in dedication.get("thoughts", []) if isinstance(item, dict)]
    reactions = [item for item in dedication.get("reactionEntries", []) if isinstance(item, dict)]

    numeric_votes = []
    for item in votes:
        try:
            value = int(item.get("value"))
        except (TypeError, ValueError):
            continue
        if 1 <= value <= 10:
            numeric_votes.append(value)

    dedication["votes"] = votes
    dedication["thoughts"] = thoughts
    dedication["reactionEntries"] = reactions
    dedication["voteAverage"] = round(sum(numeric_votes) / len(numeric_votes), 1) if numeric_votes else None
    dedication["thoughtsText"] = "\n\n".join(
        f"[{item.get('userName') or item.get('user_name') or 'Utente'}] {str(item.get('text') or '').strip()}"
        for item in thoughts
        if str(item.get("text") or "").strip()
    )
    counts = {key: 0 for key in REACTION_KEYS}
    for item in reactions:
        value = str(item.get("value") or item.get("reaction") or "").strip()
        if value in counts:
            counts[value] += 1
    dedication["reactions"] = counts
    dedication["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return dedication


def delete_feedback_entries(selected_ids: set[str], dedications: list[dict]) -> int:
    by_path = {item["path"]: item for item in dedications}
    selected_by_path: dict[str, dict[str, set[int]]] = {}
    for entry_id in selected_ids:
        parts = str(entry_id).split("|")
        if len(parts) != 3:
            continue
        path, field_name, index_text = parts
        try:
            index = int(index_text)
        except ValueError:
            continue
        selected_by_path.setdefault(path, {}).setdefault(field_name, set()).add(index)

    deleted = 0
    for path, fields in selected_by_path.items():
        source = by_path.get(path)
        if not source:
            continue
        dedication = json.loads(json.dumps(source["data"]))
        for field_name, indexes in fields.items():
            entries = dedication.get(field_name)
            if not isinstance(entries, list):
                continue
            before = len(entries)
            dedication[field_name] = [
                entry for idx, entry in enumerate(entries)
                if idx not in indexes
            ]
            deleted += before - len(dedication[field_name])
        sync_dedication_feedback_fields(dedication)
        write_github_json(path, dedication, source["sha"], f"Ripulisci feedback {dedication.get('id') or Path(path).stem}")

    load_garbage_dedications.clear()
    return deleted


def render_visit_statistics() -> None:
    st.title("Accessi sito")
    st.caption("Statistiche amministrative delle visite registrate dal sito. Non sono mostrate nelle pagine pubbliche.")

    col_reload, col_source = st.columns([1, 2])
    if col_reload.button("Ricarica visite", use_container_width=True):
        load_site_visits.clear()
    api_url = configured_feedback_api_url()
    col_source.caption(f"Sorgente: {api_url}/visits" if api_url else VISITS_PATH)

    try:
        df = visits_dataframe(load_site_visits())
    except Exception as exc:
        st.error(str(exc))
        return

    if df.empty:
        st.info("Nessuna visita registrata.")
        return

    users = sorted(df["utente"].dropna().unique().tolist())
    selected_user = st.selectbox("Utente", ["Tutti gli utenti", *users], key="visits_user_filter")
    all_days = st.checkbox("Tutti i giorni", value=True, key="visits_all_days")

    filtered = df.copy()
    if selected_user != "Tutti gli utenti":
        filtered = filtered[filtered["utente"] == selected_user]

    if not all_days:
        mode = st.radio(
            "Filtro data",
            ["Singolo giorno", "Intervallo temporale"],
            horizontal=True,
            key="visits_date_mode",
        )
        min_day = df["data_dt"].min()
        max_day = df["data_dt"].max()
        if mode == "Singolo giorno":
            selected_day = st.date_input("Giorno", value=max_day, min_value=min_day, max_value=max_day, key="visits_single_day")
            filtered = filtered[filtered["data_dt"] == selected_day]
        else:
            selected_range = st.date_input(
                "Intervallo",
                value=(min_day, max_day),
                min_value=min_day,
                max_value=max_day,
                key="visits_date_range",
            )
            if isinstance(selected_range, tuple) and len(selected_range) == 2:
                start_day, end_day = selected_range
            else:
                start_day = end_day = selected_range
            if start_day > end_day:
                start_day, end_day = end_day, start_day
            filtered = filtered[(filtered["data_dt"] >= start_day) & (filtered["data_dt"] <= end_day)]

    total_visits = int(len(filtered))
    unique_users = int(filtered["userKey"].nunique()) if total_visits else 0
    metric_total, metric_users = st.columns(2)
    metric_total.metric("Visite totali", total_visits)
    metric_users.metric("Utenti unici", unique_users)

    if filtered.empty:
        st.warning("Nessuna visita nel filtro selezionato.")
        return

    st.subheader("Visite per giorno")
    by_day = filtered.groupby("data", as_index=False).size().rename(columns={"size": "visite"})
    st.bar_chart(by_day.set_index("data"))
    st.dataframe(by_day.sort_values("data", ascending=False), use_container_width=True, hide_index=True)

    st.subheader("Visite per utente")
    by_user = filtered.groupby("utente", as_index=False).size().rename(columns={"size": "visite"})
    st.dataframe(by_user.sort_values(["visite", "utente"], ascending=[False, True]), use_container_width=True, hide_index=True)

    st.subheader("Dettaglio visite")
    detail = filtered[["data", "ora", "utente", "pagina"]].sort_values(["data", "ora"], ascending=[False, False])
    st.dataframe(detail, use_container_width=True, hide_index=True)


def render_garbage() -> None:
    st.title("Garbage")
    st.caption("Pulizia manuale delle visite sito salvate in data/visits.json.")

    if st.button("Ricarica dati Garbage", use_container_width=True, key="garbage_reload"):
        load_site_visits.clear()

    try:
        payload, sha = load_visits_json_for_edit()
        visits = payload.get("visits", [])
        df = visits_dataframe(visits)
    except Exception as exc:
        st.error(str(exc))
        return

    if df.empty:
        st.info("Nessuna visita da cancellare.")
        return

    mode = st.radio(
        "Cosa vuoi cancellare?",
        ["Singole visite", "Visite per utente", "Visite per data"],
        horizontal=True,
        key="garbage_visit_delete_mode",
    )

    selected_ids: set[str] = set()
    if mode == "Singole visite":
        options = {}
        for row in df.itertuples(index=False):
            label = f"{row.data} {row.ora} | {row.utente} | {row.pagina} | {row.visitId}"
            options[label] = row.visitId
        selected_labels = st.multiselect(
            "Seleziona visite da cancellare",
            list(options.keys()),
            key="garbage_single_visit_ids",
        )
        selected_ids = {options[label] for label in selected_labels}
    elif mode == "Visite per utente":
        users = sorted(df["utente"].dropna().unique().tolist())
        selected_user = st.selectbox("Utente", users, key="garbage_user")
        selected_ids = set(df.loc[df["utente"] == selected_user, "visitId"].tolist())
    else:
        days = sorted(df["data"].dropna().unique().tolist(), reverse=True)
        selected_day = st.selectbox("Data", days, key="garbage_day")
        selected_ids = set(df.loc[df["data"] == selected_day, "visitId"].tolist())

    preview = df[df["visitId"].isin(selected_ids)].copy()
    st.metric("Visite selezionate per cancellazione", int(len(preview)))
    if not preview.empty:
        st.dataframe(
            preview[["data", "ora", "utente", "pagina", "visitId"]],
            use_container_width=True,
            hide_index=True,
        )

    confirm = st.checkbox(
        "Confermo la cancellazione delle visite selezionate",
        key="garbage_confirm_delete_visits",
        disabled=preview.empty,
    )
    if st.button(
        "Cancella visite selezionate",
        type="primary",
        use_container_width=True,
        disabled=preview.empty or not confirm,
        key="garbage_delete_visits",
    ):
        try:
            remaining = [
                visit for visit in visits
                if str(visit.get("visitId") or visit.get("visit_id") or "").strip() not in selected_ids
            ]
            save_visits_json(
                remaining,
                sha,
                f"Rimuovi {len(visits) - len(remaining)} visite sito",
            )
            st.success(f"Cancellate {len(visits) - len(remaining)} visite.")
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Feedback dediche")
    st.caption("Cancella voti, pensieri e reaction dai JSON delle dediche.")

    try:
        dedications = load_garbage_dedications()
        feedback_df = feedback_garbage_dataframe(dedications)
    except Exception as exc:
        st.error(str(exc))
        return

    if feedback_df.empty:
        st.info("Nessun voto, pensiero o reaction da cancellare.")
        return

    feedback_mode = st.radio(
        "Cosa vuoi cancellare dai feedback?",
        ["Singoli elementi", "Per dedica", "Per utente", "Per tipo"],
        horizontal=True,
        key="garbage_feedback_delete_mode",
    )

    selected_feedback_ids: set[str] = set()
    if feedback_mode == "Singoli elementi":
        options = {}
        display_df = feedback_df.sort_values(["dedica", "tipo", "utente"])
        for row in display_df.itertuples(index=False):
            label = f"{row.dedica} | {row.tipo} | {row.utente} | {row.valore}"
            options[label] = row.entryId
        selected_labels = st.multiselect(
            "Seleziona elementi da cancellare",
            list(options.keys()),
            key="garbage_feedback_single_ids",
        )
        selected_feedback_ids = {options[label] for label in selected_labels}
    elif feedback_mode == "Per dedica":
        dediche = sorted(feedback_df["dedica"].dropna().unique().tolist())
        selected_dedica = st.selectbox("Dedica", dediche, key="garbage_feedback_dedica")
        type_filter = st.multiselect(
            "Tipi da cancellare",
            ["voto", "pensiero", "reaction"],
            default=["voto", "pensiero", "reaction"],
            key="garbage_feedback_dedica_types",
        )
        selected = feedback_df[(feedback_df["dedica"] == selected_dedica) & (feedback_df["tipo"].isin(type_filter))]
        selected_feedback_ids = set(selected["entryId"].tolist())
    elif feedback_mode == "Per utente":
        users = sorted(feedback_df["utente"].dropna().unique().tolist())
        selected_user = st.selectbox("Utente feedback", users, key="garbage_feedback_user")
        type_filter = st.multiselect(
            "Tipi da cancellare",
            ["voto", "pensiero", "reaction"],
            default=["voto", "pensiero", "reaction"],
            key="garbage_feedback_user_types",
        )
        selected = feedback_df[(feedback_df["utente"] == selected_user) & (feedback_df["tipo"].isin(type_filter))]
        selected_feedback_ids = set(selected["entryId"].tolist())
    else:
        selected_type = st.selectbox(
            "Tipo feedback",
            ["voto", "pensiero", "reaction"],
            key="garbage_feedback_type",
        )
        selected = feedback_df[feedback_df["tipo"] == selected_type]
        selected_feedback_ids = set(selected["entryId"].tolist())

    feedback_preview = feedback_df[feedback_df["entryId"].isin(selected_feedback_ids)].copy()
    st.metric("Elementi feedback selezionati", int(len(feedback_preview)))
    if not feedback_preview.empty:
        st.dataframe(
            feedback_preview[["dedica", "tipo", "utente", "valore", "createdAt", "updatedAt"]],
            use_container_width=True,
            hide_index=True,
        )

    confirm_feedback = st.checkbox(
        "Confermo la cancellazione dei feedback selezionati",
        key="garbage_confirm_delete_feedback",
        disabled=feedback_preview.empty,
    )
    if st.button(
        "Cancella feedback selezionati",
        type="primary",
        use_container_width=True,
        disabled=feedback_preview.empty or not confirm_feedback,
        key="garbage_delete_feedback",
    ):
        try:
            deleted = delete_feedback_entries(selected_feedback_ids, dedications)
            st.success(f"Cancellati {deleted} elementi feedback.")
        except Exception as exc:
            st.error(str(exc))


def render_site_configuration() -> None:
    st.title("Configurazione sito")
    st.caption(
        "Gestisce la visibilita' dei pulsanti e la modalita' Fake Error / Site Locked. "
        "Il sito legge questa configurazione da GitHub e si aggiorna entro pochi secondi."
    )

    try:
        settings, sha = read_github_json(SITE_SETTINGS_PATH, DEFAULT_SITE_SETTINGS)
        settings = normalize_site_settings(settings)
    except Exception as exc:
        st.error(str(exc))
        return

    buttons = settings["buttons"]
    fake_error = settings["fakeError"]
    config_version = settings.get("updated_at") or "default"
    config_dirty = bool(st.session_state.get("config_site_dirty", False))
    config_first_load = "config_loaded_version" not in st.session_state
    if config_first_load or (st.session_state.get("config_loaded_version") != config_version and not config_dirty):
        st.session_state["config_site_effect"] = settings.get("siteEffect", DEFAULT_SITE_SETTINGS["siteEffect"])
        st.session_state["config_effect_intensity"] = settings.get("effectIntensity", DEFAULT_SITE_SETTINGS["effectIntensity"])
        st.session_state["config_effect_backdrop"] = settings.get("effectBackdrop", DEFAULT_SITE_SETTINGS["effectBackdrop"])
        st.session_state["config_effect_floating_items"] = settings.get("effectFloatingItems", DEFAULT_SITE_SETTINGS["effectFloatingItems"])
        st.session_state["config_effect_backdrop_text"] = settings.get("effectBackdropText", DEFAULT_SITE_SETTINGS["effectBackdropText"])
        st.session_state["config_google_vote_visible"] = buttons["googleVote"]
        st.session_state["config_plus_vote_visible"] = buttons["plusVote"]
        st.session_state["config_feedback_api_url"] = settings.get("feedbackApiUrl", "")
        st.session_state["config_fake_error_enabled"] = fake_error["enabled"]
        st.session_state["config_fake_error_title"] = fake_error["title"]
        st.session_state["config_fake_error_message"] = fake_error["message"]
        st.session_state["config_fake_error_button"] = fake_error["buttonText"]
        st.session_state["config_fake_error_image_message"] = fake_error["imageMessage"]
        st.session_state["config_fake_error_admin_message"] = fake_error["adminMessage"]
        st.session_state["config_loaded_version"] = config_version

    def mark_site_config_dirty() -> None:
        st.session_state["config_site_dirty"] = True

    def persist_fake_error_toggle() -> None:
        try:
            force_site_lock_enabled(bool(st.session_state.get("config_fake_error_enabled", False)))
            st.session_state["config_site_dirty"] = False
            st.session_state["config_toggle_status"] = (
                "Fake Error Mode attivata nel JSON remoto."
                if st.session_state.get("config_fake_error_enabled")
                else "Fake Error Mode disattivata nel JSON remoto."
            )
        except Exception as exc:
            st.session_state["config_toggle_status"] = str(exc)

    st.subheader("Effetti Speciali")
    effect_label_by_value = {value: label for label, value in SITE_EFFECT_OPTIONS.items()}
    intensity_label_by_value = {value: label for label, value in EFFECT_INTENSITY_OPTIONS.items()}
    site_effect = st.selectbox(
        "Effetto speciale del sito",
        options=list(SITE_EFFECT_OPTIONS.values()),
        format_func=lambda value: effect_label_by_value.get(value, value),
        key="config_site_effect",
        on_change=mark_site_config_dirty,
    )
    effect_intensity = st.selectbox(
        "Intensita' effetto",
        options=list(EFFECT_INTENSITY_OPTIONS.values()),
        format_func=lambda value: intensity_label_by_value.get(value, value),
        key="config_effect_intensity",
        on_change=mark_site_config_dirty,
    )
    effect_backdrop = st.toggle(
        "Sfondo brillante / scintillio",
        key="config_effect_backdrop",
        on_change=mark_site_config_dirty,
        help="Controlla il fondale luminoso dell'effetto.",
    )
    effect_floating_items = st.toggle(
        "Scritte / icone fluttuanti",
        key="config_effect_floating_items",
        on_change=mark_site_config_dirty,
        help="Per Pilli controlla le scritte Pilli che fluttuano nello schermo; per cuori e altri effetti custom controlla le icone grandi fluttuanti.",
    )
    effect_backdrop_text = st.toggle(
        "Oggetti fissi nello sfondo",
        key="config_effect_backdrop_text",
        on_change=mark_site_config_dirty,
        help="Spegne gli oggetti ripetuti e lampeggianti del fondale, per esempio Pilli, cuori, palloni o soli fissi in alto a sinistra, senza spegnere scintillio o oggetti fluttuanti.",
    )
    if site_effect == "auto":
        st.info("Automatico e' pronto per regole future: in questa versione equivale a Nessun effetto.")
    save_effects_clicked = st.button(
        "Salva configurazione sito",
        type="primary",
        use_container_width=True,
        key="config_save_effects",
    )

    st.divider()
    st.subheader("Pulsanti")
    google_vote_visible = st.checkbox(
        "Mostra pulsante Votami (Google Form)",
        key="config_google_vote_visible",
    )
    plus_vote_visible = st.checkbox(
        "Mostra pulsante Votami Plus",
        key="config_plus_vote_visible",
    )

    st.divider()
    st.subheader("API feedback")
    feedback_api_url = st.text_input(
        "URL API feedback per Votami Plus e reaction",
        placeholder="https://ddgff-feedback.<account>.workers.dev",
        key="config_feedback_api_url",
    )
    if not feedback_api_url.strip():
        st.warning(
            "API feedback non configurata: Votami Plus e reaction non possono salvare in modo persistente."
        )

    st.divider()
    st.subheader("Fake Error / Site Locked Mode")
    fake_error_enabled = st.toggle(
        "Abilita Fake Error Mode",
        key="config_fake_error_enabled",
        on_change=persist_fake_error_toggle,
    )
    if st.session_state.get("config_toggle_status"):
        st.info(st.session_state["config_toggle_status"])
    fake_error_title = st.text_input(
        "Titolo errore principale",
        key="config_fake_error_title",
    )
    fake_error_message = st.text_area(
        "Messaggio personalizzato iniziale",
        height=120,
        key="config_fake_error_message",
    )
    fake_error_button = st.text_input(
        "Testo pulsante/interazione",
        key="config_fake_error_button",
    )

    current_image_path = fake_error["imagePath"]
    if current_image_path:
        st.caption("Immagine attualmente configurata")
        st.image(
            current_image_path,
            use_container_width=True,
        )

    lock_image = st.file_uploader(
        "Sostituisci immagine seconda schermata",
        type=["png", "jpg", "jpeg", "webp"],
        key="config_fake_error_image",
    )
    fake_error_image_message = st.text_area(
        "Messaggio associato all'immagine",
        height=140,
        key="config_fake_error_image_message",
    )
    fake_error_admin_message = st.text_area(
        "Messaggio amministrativo finale",
        height=120,
        key="config_fake_error_admin_message",
    )

    st.caption(
        "File configurazione: "
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{SITE_SETTINGS_PATH}"
    )

    col_enable_site, col_save_config, col_restore_site = st.columns(3)
    enable_site_clicked = col_enable_site.button(
        "Attiva Fake Error",
        use_container_width=True,
    )
    save_config_clicked = col_save_config.button(
        "Salva configurazione sito",
        type="primary",
        use_container_width=True,
    )
    restore_site_clicked = col_restore_site.button(
        "Ripristina sito",
        use_container_width=True,
    )

    if enable_site_clicked or save_effects_clicked or save_config_clicked or restore_site_clicked:
        if enable_site_clicked:
            try:
                force_site_lock_enabled(True)
                st.success(
                    "Fake Error Mode attivata nel JSON remoto. "
                    "Aggiorna il sito o attendi il prossimo controllo automatico."
                )
                st.session_state["config_site_dirty"] = False
                render_whatsapp_notification_button()
                return
            except Exception as exc:
                st.error(str(exc))
                return

        if restore_site_clicked:
            try:
                force_restore_site_settings()
                st.success(
                    "Sito ripristinato: Fake Error Mode disattivata nel JSON remoto. "
                    "Aggiorna il sito o attendi il prossimo controllo automatico."
                )
                st.session_state["config_site_dirty"] = False
                render_whatsapp_notification_button()
                return
            except Exception as exc:
                st.error(str(exc))
                return

        image_path = current_image_path
        updated = {
            "buttons": {
                "googleVote": bool(google_vote_visible),
                "plusVote": bool(plus_vote_visible),
            },
            "feedbackApiUrl": feedback_api_url.strip(),
            "siteEffect": site_effect,
            "effectIntensity": effect_intensity,
            "effectBackdrop": bool(effect_backdrop),
            "effectFloatingItems": bool(effect_floating_items),
            "effectBackdropText": bool(effect_backdrop_text),
            "fakeError": {
                "enabled": False if restore_site_clicked else bool(fake_error_enabled),
                "title": fake_error_title.strip() or DEFAULT_SITE_SETTINGS["fakeError"]["title"],
                "message": fake_error_message.strip() or DEFAULT_SITE_SETTINGS["fakeError"]["message"],
                "buttonText": fake_error_button.strip() or DEFAULT_SITE_SETTINGS["fakeError"]["buttonText"],
                "imagePath": image_path,
                "imageMessage": fake_error_image_message.strip() or DEFAULT_SITE_SETTINGS["fakeError"]["imageMessage"],
                "adminMessage": fake_error_admin_message.strip() or DEFAULT_SITE_SETTINGS["fakeError"]["adminMessage"],
            },
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            if lock_image is not None:
                image_path = upload_site_lock_image(lock_image)
                updated["fakeError"]["imagePath"] = image_path
            save_site_settings(updated, "Aggiorna configurazione sito")
            st.session_state["config_loaded_version"] = updated["updated_at"]
            st.session_state["config_site_dirty"] = False
            st.success(
                "Configurazione salvata. Le pagine gia' aperte la rileggono automaticamente "
                "entro circa 15 secondi."
            )
            render_whatsapp_notification_button()
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("🚀 Deploy GitHub Pages")
    st.caption(
        "Avvia manualmente il workflow **deploy.yml** su GitHub Actions: "
        "esegue il build Astro e pubblica il sito su GitHub Pages. "
        "Utile dopo modifiche manuali ai file JSON o alla configurazione."
    )
    deploy_pages_clicked = st.button(
        "🚀 Deploy GitHub Pages ora",
        type="primary",
        use_container_width=True,
        key="config_deploy_pages",
    )
    if deploy_pages_clicked:
        with st.spinner("Avvio deploy GitHub Pages..."):
            try:
                dispatch_deploy_pages()
                st.success(
                    "✅ Workflow deploy.yml avviato. "
                    "Il sito verrà aggiornato appena GitHub Actions termina il build "
                    f"(solitamente 2-3 minuti). "
                    f"Monitora lo stato su: https://github.com/{GITHUB_REPO}/actions"
                )
                render_whatsapp_notification_button()
            except Exception as exc:
                st.error(str(exc))


def main() -> None:
    page_icon = STREAMLIT_ICON_PATH.read_bytes() if STREAMLIT_ICON_PATH.exists() else "🎵"
    st.set_page_config(page_title="DDG FF Admin", page_icon=page_icon, layout="centered")
    inject_streamlit_pwa_tags()
    tab_new, tab_historical, tab_config, tab_visits, tab_garbage = st.tabs([
        "Nuova dedica",
        "Historical",
        "Configurazione sito",
        "Accessi sito",
        "Garbage",
    ])
    with tab_new:
        render_new_dedication()
    with tab_historical:
        render_historical()
    with tab_config:
        render_site_configuration()
    with tab_visits:
        render_visit_statistics()
    with tab_garbage:
        render_garbage()


if __name__ == "__main__":
    main()
