# Backend feedback DDG FF

Il sito statico su GitHub Pages non puo scrivere direttamente nei JSON del repository:
il browser non deve mai conoscere un token GitHub.

Il flusso corretto e':

1. Il sito pubblico chiama `PUBLIC_DDGFF_FEEDBACK_API_URL`.
2. La feedback API riceve `POST /save_vote` o `POST /save_reaction`.
3. La feedback API usa un token GitHub lato server.
4. La feedback API aggiorna `data/dedications/<dedication>.json` via GitHub Contents API.
5. Il sito rilegge i dati aggiornati da `GET /feedback` o `GET /feedback/all`.

## Soluzione consigliata: Cloudflare Worker

Il Worker e' in `workers/feedback-worker`. Sta sempre disponibile, non richiede boot visibile
all'utente e tiene il token GitHub fuori dal browser.

### Cosa devi fare una sola volta

1. Crea un token GitHub fine-grained per il repository `legnaro72/dediche-musicali-ff`.
   Permessi minimi:
   - `Contents: Read and write`
   - `Actions: Read and write`
2. Accedi a Cloudflare:

```bash
npm run worker:login
```

3. Salva il token GitHub come secret del Worker:

```bash
npx wrangler secret put GITHUB_TOKEN --config workers/feedback-worker/wrangler.toml
```

4. Pubblica il Worker:

```bash
npm run worker:deploy
```

5. Copia l'URL pubblico del Worker, per esempio:

```text
https://ddgff-feedback.<tuo-account>.workers.dev
```

6. Nel repository GitHub, aggiungi il secret:

```text
PUBLIC_DDGFF_FEEDBACK_API_URL=https://ddgff-feedback.<tuo-account>.workers.dev
```

7. Rilancia il deploy GitHub Pages. Il sito pubblico chiamera' il Worker e il Worker
   aggiornera' i JSON nel repository.

## Backend Python locale o alternativo

Per scrivere sul repository GitHub:

```env
DDGFF_FEEDBACK_BACKEND=github
DDGFF_GITHUB_REPO=legnaro72/dediche-musicali-ff
DDGFF_GITHUB_BRANCH=main
DDGFF_GITHUB_TOKEN=ghp_xxx
DDGFF_FEEDBACK_HOST=0.0.0.0
DDGFF_FEEDBACK_ORIGIN=https://legnaro72.github.io
```

Il token deve avere permessi `Contents: Read and write` e `Actions: Read and write` sul repository.

## Variabile ambiente frontend

Nel build del sito:

```env
PUBLIC_DDGFF_FEEDBACK_API_URL=https://URL-PUBBLICO-DELLA-FEEDBACK-API
```

Senza questa variabile, il sito statico non puo salvare voti persistenti dal telefono.

## Endpoint

```http
GET /feedback?id=2026-04-09-senza-un-perche-bowland
GET /feedback/all
POST /save_vote
POST /save_reaction
```

Payload voto:

```json
{
  "id": "2026-04-09-senza-un-perche-bowland",
  "userId": "uuid-utente",
  "userName": "Mario",
  "voteValue": 8,
  "thoughtText": "Testo libero"
}
```

Payload reaction:

```json
{
  "id": "2026-04-09-senza-un-perche-bowland",
  "userId": "uuid-utente",
  "userName": "Mario",
  "reaction": "heart",
  "previousReaction": "like"
}
```
