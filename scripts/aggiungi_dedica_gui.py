import re
import datetime
import base64
import os
import shutil
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
import gspread
import requests
from google.oauth2.service_account import Credentials

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


GOOGLE_SHEET_ID = "1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw"
SERVICE_ACCOUNT_FILE = "service_account.json"

DEFAULT_VOTE_URL = "https://docs.google.com/forms/d/17VuesL0BOupyw5M5MNCLs1gq_uqZioVKVkGC8oFfn38/viewform"
SITE_NAME = "DDG FF"
GITHUB_REPO = "legnaro72/dediche-musicali-ff"
GITHUB_BRANCH = "main"
UPLOAD_DIR = "public/images/upload"
VALID_IMAGE_MODES = ("auto", "upload", "raw", "none")
VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ROOT_DIR = Path(__file__).resolve().parents[1]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("à", "a").replace("è", "e").replace("é", "e")
    text = text.replace("ì", "i").replace("ò", "o").replace("ù", "u")
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


def default_dedication_text(song_title: str, artist: str) -> str:
    return (
        f"Ci sono canzoni che arrivano senza fare rumore, "
        f"ma restano dentro piu di tante parole.\n"
        f"Oggi ti dedico \"{song_title}\" di {artist}, "
        f"perche certe emozioni meritano di essere ascoltate fino in fondo."
    )


def default_short_phrase() -> str:
    return "Alcune emozioni restano anche dopo l'ultima nota."


def build_row(
    date_value,
    song_title,
    artist,
    spotify_url,
    image_mode,
    image_source,
    custom_dedication_text="",
    custom_short_phrase="",
):
    song_slug = slugify(song_title)
    artist_slug = slugify(artist)

    dedication_id = f"{date_value}-{song_slug}-{artist_slug}"

    dedication_text = (
        f"Ci sono canzoni che arrivano senza fare rumore, "
        f"ma restano dentro più di tante parole.\n"
        f"Oggi ti dedico “{song_title}” di {artist}, "
        f"perché certe emozioni meritano di essere ascoltate fino in fondo. 🎵"
    )

    short_phrase = "Alcune emozioni restano anche dopo l’ultima nota."

    if custom_dedication_text:
        dedication_text = custom_dedication_text
    if custom_short_phrase:
        short_phrase = custom_short_phrase

    tags = "musica,emozioni,dedica"

    seo_title = f"{song_title} – {artist} | {SITE_NAME}"
    seo_description = f"Dedica musicale del giorno con “{song_title}” di {artist}."
    image_alt = f"Dedica musicale {song_title} di {artist}"

    return [
        dedication_id,
        date_value,
        "scheduled",
        song_title,
        artist,
        "La dedica del giorno",
        dedication_text,
        spotify_url,
        "spotify",
        DEFAULT_VOTE_URL,
        image_mode,
        image_source,
        short_phrase,
        tags,
        seo_title,
        seo_description,
        image_alt,
    ]


def get_github_token() -> str:
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_PAT")
        or ""
    ).strip()
    if not token:
        raise ValueError(
            "Per caricare immagini su GitHub imposta una variabile "
            "GITHUB_TOKEN, GH_TOKEN oppure GITHUB_PAT con permesso Contents: write."
        )
    return token


def upload_image_to_github(local_path: str, asset_id: str) -> str:
    src = Path(local_path)
    if not src.exists():
        raise ValueError("Il file immagine selezionato non esiste.")

    ext = src.suffix.lower()
    if ext not in VALID_IMAGE_EXTS:
        raise ValueError(
            "Formato immagine non supportato. Usa JPG, JPEG, PNG oppure WEBP."
        )

    upload_name = f"{asset_id}{ext}"
    repo_path = f"{UPLOAD_DIR}/{upload_name}"
    local_upload_dir = ROOT_DIR / UPLOAD_DIR
    local_upload_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, local_upload_dir / upload_name)

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

    content_b64 = base64.b64encode(src.read_bytes()).decode("ascii")
    payload = {
        "message": f"Upload immagine dedica {asset_id}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(api_url, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 201):
        raise ValueError(f"Upload GitHub fallito: {response.text}")

    return repo_path


def append_to_google_sheet(row):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
    sheet.append_row(row, value_input_option="USER_ENTERED")


def submit():
    try:
        date_value = normalize_date(date_entry.get())
        song_title = song_entry.get().strip()
        artist = artist_entry.get().strip()
        spotify_url = spotify_entry.get().strip()
        image_mode = image_mode_var.get().strip()
        selected_image = image_path_var.get().strip()
        dedication_text = dedication_text_box.get("1.0", "end").strip()
        short_phrase = short_phrase_entry.get().strip()

        if not song_title:
            raise ValueError("Inserisci il titolo della canzone.")

        if not artist:
            raise ValueError("Inserisci l'artista.")

        if not spotify_url.startswith("https://open.spotify.com/"):
            raise ValueError("Inserisci un URL Spotify valido.")

        if image_mode not in VALID_IMAGE_MODES:
            raise ValueError("Seleziona un image_mode valido.")

        if not dedication_text:
            raise ValueError("Inserisci o conferma il testo della dedica.")

        if not short_phrase:
            raise ValueError("Inserisci o conferma la frase breve.")

        image_source = ""
        dedication_id = f"{date_value}-{slugify(song_title)}-{slugify(artist)}"
        if image_mode in ("upload", "raw"):
            if not selected_image:
                raise ValueError(f"Seleziona un'immagine per image_mode={image_mode}.")
            image_source = upload_image_to_github(selected_image, dedication_id)

        row = build_row(
            date_value,
            song_title,
            artist,
            spotify_url,
            image_mode,
            image_source,
            dedication_text,
            short_phrase,
        )
        append_to_google_sheet(row)

        extra = f"\nImmagine caricata: {image_source}" if image_source else ""
        messagebox.showinfo(
            "Dedica aggiunta",
            f"Dedica programmata correttamente per il {date_value}!{extra}",
        )

        date_entry.delete(0, "end")
        song_entry.delete(0, "end")
        artist_entry.delete(0, "end")
        spotify_entry.delete(0, "end")
        image_mode_var.set("raw")
        image_path_var.set("")
        dedication_text_box.delete("1.0", "end")
        short_phrase_entry.delete(0, "end")
        update_image_picker_state("raw")

    except Exception as e:
        messagebox.showerror("Errore", str(e))


def choose_image():
    path = filedialog.askopenfilename(
        title="Seleziona immagine dedica",
        filetypes=[
            ("Immagini supportate", "*.jpg *.jpeg *.png *.webp"),
            ("Tutti i file", "*.*"),
        ],
    )
    if path:
        image_path_var.set(path)


def update_image_picker_state(mode: str):
    needs_image = mode in ("upload", "raw")
    state = "normal" if needs_image else "disabled"
    image_button.configure(state=state)
    if not needs_image:
        image_path_var.set("")


def refresh_text_preview():
    song_title = song_entry.get().strip()
    artist = artist_entry.get().strip()
    if not song_title or not artist:
        messagebox.showwarning(
            "Dati mancanti",
            "Inserisci prima titolo canzone e artista.",
        )
        return

    dedication_text_box.delete("1.0", "end")
    dedication_text_box.insert("1.0", default_dedication_text(song_title, artist))
    short_phrase_entry.delete(0, "end")
    short_phrase_entry.insert(0, default_short_phrase())


def refresh_text_preview_if_empty(_event=None):
    has_dedication = dedication_text_box.get("1.0", "end").strip()
    has_phrase = short_phrase_entry.get().strip()
    if has_dedication or has_phrase:
        return
    if song_entry.get().strip() and artist_entry.get().strip():
        refresh_text_preview()


def set_text_target(target: str):
    active_text_target.set(target)


def insert_emoji(emoji: str):
    target = active_text_target.get()
    if target == "short_phrase":
        short_phrase_entry.insert("insert", emoji)
        short_phrase_entry.focus_set()
    else:
        dedication_text_box.insert("insert", emoji)
        dedication_text_box.focus_set()


def insert_custom_emoji():
    value = custom_emoji_entry.get().strip()
    if value:
        insert_emoji(value)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
QUICK_EMOJIS = ["🎵", "❤️", "✨", "🌙", "🌹", "😊", "🙏", "🎧"]
EXTENDED_EMOJIS = [
    "🎶", "💙", "💛", "💜", "💫", "🌟", "☀️", "🌻",
    "🔥", "😍", "🥹", "🕊️", "🎤", "💭", "🌈", "🍀",
    "⭐", "💌", "🤍", "🫶", "🌊", "🎹", "🎸", "🪩",
]

app = ctk.CTk()
app.title("DDG FF - Aggiungi dedica")
app.geometry("720x820")
app.minsize(720, 760)

frame = ctk.CTkScrollableFrame(app, corner_radius=24)
frame.pack(padx=32, pady=32, fill="both", expand=True)
active_text_target = ctk.StringVar(value="dedication_text")

title = ctk.CTkLabel(
    frame,
    text="♪ Nuova dedica musicale",
    font=ctk.CTkFont(size=28, weight="bold"),
)
title.pack(pady=(28, 8))

subtitle = ctk.CTkLabel(
    frame,
    text="Compila i dati e programma automaticamente la dedica",
    font=ctk.CTkFont(size=14),
    text_color="#b8b8b8",
)
subtitle.pack(pady=(0, 24))

date_entry = ctk.CTkEntry(
    frame,
    width=480,
    height=44,
    placeholder_text="Data — esempio 2026-05-13 oppure 13/05/2026",
)
date_entry.pack(pady=8)

song_entry = ctk.CTkEntry(
    frame,
    width=480,
    height=44,
    placeholder_text="Titolo canzone",
)
song_entry.pack(pady=8)
song_entry.bind("<FocusOut>", refresh_text_preview_if_empty)

artist_entry = ctk.CTkEntry(
    frame,
    width=480,
    height=44,
    placeholder_text="Artista",
)
artist_entry.pack(pady=8)
artist_entry.bind("<FocusOut>", refresh_text_preview_if_empty)

spotify_entry = ctk.CTkEntry(
    frame,
    width=480,
    height=44,
    placeholder_text="URL Spotify",
)
spotify_entry.pack(pady=8)

image_mode_var = ctk.StringVar(value="raw")
image_mode_menu = ctk.CTkOptionMenu(
    frame,
    width=480,
    height=44,
    values=list(VALID_IMAGE_MODES),
    variable=image_mode_var,
    command=update_image_picker_state,
)
image_mode_menu.pack(pady=8)

image_hint = ctk.CTkLabel(
    frame,
    text="Con image_mode raw o upload devi scegliere un'immagine. Il caricamento su GitHub avviene col bottone finale.",
    font=ctk.CTkFont(size=12),
    text_color="#9ca3af",
    wraplength=560,
)
image_hint.pack(pady=(0, 4))

image_row = ctk.CTkFrame(frame, fg_color="transparent")
image_row.pack(pady=8)

image_path_var = ctk.StringVar(value="")
image_button = ctk.CTkButton(
    image_row,
    text="Scegli immagine",
    width=150,
    height=40,
    command=choose_image,
)
image_button.pack(side="left", padx=(0, 10))

image_label = ctk.CTkLabel(
    image_row,
    textvariable=image_path_var,
    width=320,
    height=40,
    anchor="w",
    text_color="#b8b8b8",
)
image_label.pack(side="left")

preview_button = ctk.CTkButton(
    frame,
    text="Genera anteprima testo",
    width=220,
    height=38,
    command=refresh_text_preview,
)
preview_button.pack(pady=(10, 6))

dedication_text_label = ctk.CTkLabel(
    frame,
    text="Dedication text",
    font=ctk.CTkFont(size=13, weight="bold"),
    text_color="#b8b8b8",
)
dedication_text_label.pack(anchor="w", padx=70, pady=(4, 2))

dedication_text_box = ctk.CTkTextbox(
    frame,
    width=560,
    height=120,
    wrap="word",
)
dedication_text_box.pack(pady=(0, 8))
dedication_text_box.bind("<FocusIn>", lambda _event: set_text_target("dedication_text"))

short_phrase_entry = ctk.CTkEntry(
    frame,
    width=560,
    height=44,
    placeholder_text="Short phrase",
)
short_phrase_entry.pack(pady=8)
short_phrase_entry.bind("<FocusIn>", lambda _event: set_text_target("short_phrase"))

emoji_label = ctk.CTkLabel(
    frame,
    text="Emoji rapide",
    font=ctk.CTkFont(size=13, weight="bold"),
    text_color="#b8b8b8",
)
emoji_label.pack(anchor="w", padx=70, pady=(8, 2))

emoji_row = ctk.CTkFrame(frame, fg_color="transparent")
emoji_row.pack(pady=(0, 8))

for emoji in QUICK_EMOJIS:
    emoji_button = ctk.CTkButton(
        emoji_row,
        text=emoji,
        width=42,
        height=36,
        command=lambda value=emoji: insert_emoji(value),
    )
    emoji_button.pack(side="left", padx=4)

emoji_extended_label = ctk.CTkLabel(
    frame,
    text="Emoji estese",
    font=ctk.CTkFont(size=13, weight="bold"),
    text_color="#b8b8b8",
)
emoji_extended_label.pack(anchor="w", padx=70, pady=(2, 2))

emoji_grid = ctk.CTkFrame(frame, fg_color="transparent")
emoji_grid.pack(pady=(0, 8))

for index, emoji in enumerate(EXTENDED_EMOJIS):
    emoji_button = ctk.CTkButton(
        emoji_grid,
        text=emoji,
        width=40,
        height=34,
        command=lambda value=emoji: insert_emoji(value),
    )
    emoji_button.grid(row=index // 8, column=index % 8, padx=3, pady=3)

custom_emoji_row = ctk.CTkFrame(frame, fg_color="transparent")
custom_emoji_row.pack(pady=(0, 8))

custom_emoji_entry = ctk.CTkEntry(
    custom_emoji_row,
    width=360,
    height=38,
    placeholder_text="Emoji o testo speciale libero",
)
custom_emoji_entry.pack(side="left", padx=(0, 10))

custom_emoji_button = ctk.CTkButton(
    custom_emoji_row,
    text="Inserisci",
    width=120,
    height=38,
    command=insert_custom_emoji,
)
custom_emoji_button.pack(side="left")

button = ctk.CTkButton(
    frame,
    text="Carica immagine e inserisci nel Google Sheet",
    width=420,
    height=52,
    corner_radius=18,
    font=ctk.CTkFont(size=16, weight="bold"),
    command=submit,
)
button.pack(pady=(22, 10))

footer = ctk.CTkLabel(
    frame,
    text="La dedica verrà aggiunta al Google Sheet con status = scheduled",
    font=ctk.CTkFont(size=12),
    text_color="#888888",
)
footer.pack(pady=(8, 0))

update_image_picker_state("raw")

app.mainloop()
