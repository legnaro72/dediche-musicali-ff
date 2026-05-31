# ♪ DDG FF

> Sito di dediche musicali giornaliere — clone indipendente di DDGPilliSite.

**Stack:** Astro · GitHub Pages · GitHub Actions · Python · Google Sheet

---

## Repo

- **Sito live:** https://legnaro72.github.io/dediche-musicali-ff/
- **Repository:** https://github.com/legnaro72/dediche-musicali-ff
- **Google Sheet FF:** `1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw`

---

## Indice
1. [Descrizione](#-descrizione)
2. [Architettura](#-architettura)
3. [Setup locale](#-setup-locale)
4. [Configurazione Google Sheet](#-configurazione-google-sheet)
5. [Configurazione GitHub Secrets](#-configurazione-github-secrets)
6. [Configurazione GitHub Pages](#-configurazione-github-pages)
7. [Deploy](#-deploy)
8. [Pubblicazione automatica](#-pubblicazione-automatica)
9. [Pubblicazione manuale](#-pubblicazione-manuale)
10. [Struttura repository](#-struttura-repository)
11. [Campi Google Sheet](#-campi-google-sheet)
12. [Nuova funzionalità: identificazione utente](#-identificazione-utente)
13. [Troubleshooting](#-troubleshooting)

---

## 📖 Descrizione

**DDG FF** pubblica automaticamente una nuova dedica musicale ogni giorno.
È un clone autonomo e indipendente di DDGPilliSite con:

- Repository GitHub separato (`dediche-musicali-ff`)
- Google Sheet dedicato (Sheet FF)
- Cloudflare Worker separato per reactions/voti (`ddgff-feedback`)
- Tema **rosso-blu Genoa** (al posto del viola/rosa originale)
- **Funzionalità nome/cognome**: raccolta una tantum per identificare chi lascia reactions e voti

**Funzionalità:**
- Homepage con dedica del giorno
- Pagina archivio con ricerca e filtri
- Pagina dettaglio per ogni dedica
- Reactions rapide (👎 👍 ❤️ ☀️) e votazione Plus con pensiero
- Immagini generate automaticamente con Python/Pillow
- Embed audio (Spotify, YouTube, SoundCloud, MP3)
- SEO automatico: title, description, OpenGraph, sitemap
- Dark mode premium tema rosso-blu
- Backup automatici come artifact GitHub Actions
- **Costo: 0 €/mese**

---

## 🏗 Architettura

```
Google Sheet FF (ID: 1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw)
    ↓ (sync_from_google_sheet.py)
JSON locali (data/dedications/)
    ↓ (validate_dedications.py)
Validazione dati
    ↓ (generate_image.py)
Immagini WebP (public/images/dedications/)
    ↓ (publish_daily.py)
Stato aggiornato → published
    ↓ (astro build)
Sito statico (dist/)
    ↓ (GitHub Actions)
GitHub Pages → https://legnaro72.github.io/dediche-musicali-ff/

Reactions/Voti:
localStorage (ottimismo UI) ↔ Cloudflare Worker ddgff-feedback
```

---

## 💻 Setup locale

### 1. Installa dipendenze frontend

```bash
npm install
```

### 2. Avvia server di sviluppo

```bash
npm run dev
# Il sito sarà disponibile su http://localhost:4321/dediche-musicali-ff/
```

### 3. Configura ambiente Python

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python -m venv .venv
source .venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt
```

### 4. Crea file .env locale

Il file `.env` è già configurato per DDG FF. Verifica che contenga:

```env
GOOGLE_SHEET_ID=1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw
SITE_NAME=DDG FF
SITE_URL=https://legnaro72.github.io/dediche-musicali-ff
IMAGE_PROVIDER=auto
```

> ⚠️ Il file `.env` contiene token segreti. Non committarlo mai. È già nel `.gitignore`.

### 5. Comandi Python disponibili

```bash
# Validazione dati
python scripts/validate_dedications.py

# Sync da Google Sheet DDG FF
python scripts/sync_from_google_sheet.py

# Pubblicazione manuale
python scripts/publish_daily.py --date 2026-05-12

# Dry run (simula senza scrivere)
python scripts/publish_daily.py --date 2026-05-12 --dry-run

# Genera immagini per una data
python scripts/generate_image.py --date 2026-05-12
```

### 6. Build produzione

```bash
npm run build
npm run preview
```

---

## 📊 Configurazione Google Sheet

Il Google Sheet FF è già creato: `Dediche Musicali FF` (stesso Google Drive).

**ID Sheet:** `1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw`

### Condividi il foglio con il Service Account

1. Apri il Google Sheet FF
2. Clicca "Condividi"
3. Aggiungi l'email del service account (la stessa usata per DDGPilliSite)
4. Imposta permesso: **Lettore** (o Editor)

---

## 🔐 Configurazione GitHub Secrets

Da GitHub: `Repository → Settings → Secrets and variables → Actions → New repository secret`

| Secret | Valore |
|--------|--------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Contenuto JSON del service account |
| `GOOGLE_SHEET_ID` | `1wYqRKJ0xdHXzLKAT09PlFSn4v42JsCG9NaWcfebm9fw` |
| `DEFAULT_VOTE_URL` | URL Google Form voti |
| `SITE_NAME` | `DDG FF` |
| `SITE_URL` | `https://legnaro72.github.io/dediche-musicali-ff` |
| `GEMINI_API_KEY` | Chiave API Gemini |
| `PEXELS_API_KEY` | Chiave Pexels |
| `UNSPLASH_ACCESS_KEY` | Chiave Unsplash |
| `IMAGE_PROVIDER` | `auto` |
| `PUBLIC_DDGFF_FEEDBACK_API_URL` | URL Cloudflare Worker DDG FF |
| `SMTP_HOST` / `SMTP_*` | Credenziali SMTP per email notifiche |
| `DEPLOY_NOTIFICATION_TO` | Email destinatario notifiche |

> `GITHUB_TOKEN` è fornito automaticamente da GitHub Actions.

---

## 🌐 Configurazione GitHub Pages

### 1. Crea il repository

Crea `legnaro72/dediche-musicali-ff` su GitHub (pubblico).

### 2. Abilita GitHub Pages

Da GitHub: `Repository → Settings → Pages`
- **Source:** GitHub Actions

### 3. Imposta permessi workflow

Da GitHub: `Repository → Settings → Actions → General`
- **Workflow permissions:** Read and write permissions ✓
- **Allow GitHub Actions to create and approve pull requests** ✓

---

## 🚀 Deploy

### Primo push

```bash
# Verifica che il remote punti al nuovo repo
git remote -v
# origin → https://github.com/legnaro72/dediche-musicali-ff.git  ✓

# Primo push
git push -u origin main
```

Il workflow `deploy.yml` si attiverà automaticamente.

### URL finale

```
https://legnaro72.github.io/dediche-musicali-ff/
```

---

## ⏰ Pubblicazione automatica

Il workflow `daily-publish.yml` si esegue automaticamente ogni giorno alle **08:15 ora italiana**.

Flusso automatico:
1. Legge il Google Sheet FF
2. Trova la dedica del giorno (status = `scheduled`, date = oggi)
3. Valida i dati
4. Genera le immagini
5. Aggiorna lo status a `published`
6. Build Astro
7. Commit e push
8. Deploy su GitHub Pages

---

## 🔧 Pubblicazione manuale

Da GitHub: `Actions → 🎵 Pubblicazione Giornaliera DDG FF → Run workflow`

| Input | Descrizione |
|-------|-------------|
| `date` | Data da pubblicare (es. `2026-05-12`). Vuoto = oggi |
| `force_republish` | `true` per forzare anche se già pubblicata |
| `dry_run` | `true` per simulare senza modifiche reali |

---

## 📁 Struttura repository

```
/
├── .github/workflows/
│   ├── deploy.yml              ← Deploy su push a main
│   ├── daily-publish.yml       ← Pubblicazione giornaliera DDG FF
│   └── backup.yml              ← Backup automatico
│
├── data/dedications/           ← JSON delle dediche FF
│
├── public/
│   ├── config/site-settings.json  ← URL Cloudflare Worker DDG FF
│   ├── images/dedications/     ← Immagini generate
│   └── manifest.json           ← PWA DDG FF
│
├── scripts/
│   ├── utils.py
│   ├── sync_from_google_sheet.py   ← Legge Sheet FF
│   ├── validate_dedications.py
│   ├── generate_image.py
│   └── publish_daily.py
│
├── src/
│   ├── components/
│   │   ├── DedicationPlus.astro    ← Reactions + voti (con nome/cognome)
│   │   └── UserIdentityModal.astro ← Modale nome/cognome (NUOVO)
│   ├── layouts/BaseLayout.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── archive/index.astro
│   │   ├── statistiche/index.astro
│   │   ├── link-utili/index.astro
│   │   └── dediche/[id].astro
│   └── styles/global.css       ← Tema rosso-blu Genoa
│
├── astro.config.mjs            ← base: '/dediche-musicali-ff'
├── package.json
├── requirements.txt
└── .env                        ← ⚠️ Non committare mai
```

---

## 📋 Campi Google Sheet

| Campo | Obbligatorio | Descrizione |
|-------|:---:|-------------|
| `id` | ✅ | Identificativo univoco. Es. `2026-05-12-nome-canzone` |
| `date` | ✅ | Data pubblicazione. Formato: `YYYY-MM-DD` |
| `status` | ✅ | `draft` / `scheduled` / `published` / `disabled` |
| `song_title` | ✅ | Titolo della canzone |
| `artist` | ✅ | Nome dell'artista |
| `dedication_title` | ✅ | Titolo della dedica |
| `dedication_text` | ✅ | Testo completo |
| `audio_url` | ✅ | Link audio (inizia con `https://`) |
| `audio_type` | ✅ | `spotify` / `youtube` / `soundcloud` / `mp3` |
| `vote_url` | ⚪ | Link Google Form. Se vuoto, usa `DEFAULT_VOTE_URL` |
| `image_mode` | ⚪ | `auto` / `upload` / `none`. Default: `auto` |
| `short_phrase` | ⚪ | Frase breve per l'immagine |
| `tags` | ⚪ | Tag separati da virgola |
| `seo_title` | ⚪ | Titolo SEO (auto-generato se vuoto) |
| `seo_description` | ⚪ | Descrizione SEO (auto-generata se vuota) |

---

## 👤 Identificazione Utente

DDG FF include un modal "una tantum" che appare al primo accesso e chiede nome e cognome.

- I dati sono salvati **solo in localStorage** sul dispositivo
- Non viene creato nessun account o cookie
- Il nome viene usato per taggare reactions e voti inviati al server
- L'utente può modificare nome/cognome dal bottone **✏️ Profilo** nel footer
- localStorage keys: `ddgff-user-nome`, `ddgff-user-cognome`

---

## 🔧 Troubleshooting

### Il sito non si aggiorna
- Verifica che `status = scheduled` nel Google Sheet FF
- Verifica che la data sia corretta (`YYYY-MM-DD`)
- Controlla che GitHub Pages sia su "Source: GitHub Actions"

### Errore autenticazione Google Sheet
- Verifica che `GOOGLE_SERVICE_ACCOUNT_JSON` sia valido
- Verifica che il Google Sheet FF sia condiviso con il service account
- Controlla che le API (Sheets + Drive) siano abilitate

### Le reactions non funzionano
- Verifica che il Cloudflare Worker `ddgff-feedback` sia deployato
- Aggiorna `public/config/site-settings.json` con l'URL corretto del Worker
- Aggiungi `PUBLIC_DDGFF_FEEDBACK_API_URL` ai Secrets GitHub

### Relazione con il sito originale
- Il sito originale è `legnaro72/dediche-musicali` (non modificato)
- Il remote `upstream` punta al repo originale (sola lettura, solo per riferimento)
- I due siti condividono lo stesso service account ma hanno Sheet separati

---

*DDG FF — fatto con ♪ Python e ❤️*
