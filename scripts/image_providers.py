"""
image_providers.py — Pipeline multi-provider: Gemini, Pexels, Unsplash,
                      Openverse, Wikimedia Commons, fallback locale.
"""
import io
import os
import random
import logging
import urllib.parse

logger = logging.getLogger('generate_image')
_TIMEOUT = 15


def _get(url, params=None, headers=None):
    import requests
    try:
        r = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.warning(f'      HTTP error: {e}')
        return None


def _img_from_url(url: str):
    """Scarica immagine da URL → PIL.Image RGB (EXIF-corretto)."""
    from PIL import Image, ImageOps
    r = _get(url)
    if r:
        try:
            img = Image.open(io.BytesIO(r.content))
            img = ImageOps.exif_transpose(img)  # corregge rotazione EXIF
            return img.convert('RGB')
        except Exception as e:
            logger.warning(f'      Decode error: {e}')
    return None


# ── Gemini: image generation (richiede billing) ───────────────────────────────
def try_gemini(prompt: str):
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        logger.info('      Gemini: GEMINI_API_KEY assente — skip')
        return None, None
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=api_key)

        # Modelli image generation (richiedono billing attivo)
        for model_name in (
            'gemini-2.5-flash-image',
            'gemini-3.1-flash-image-preview',
        ):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_modalities=['IMAGE', 'TEXT'],
                    ),
                )
                for cand in (response.candidates or []):
                    for part in (cand.content.parts or []):
                        if part.inline_data and part.inline_data.data:
                            from PIL import Image
                            img = Image.open(
                                io.BytesIO(part.inline_data.data)
                            ).convert('RGB')
                            logger.info(f'      ✓ Gemini: immagine generata ({model_name})')
                            return img, {
                                'provider': 'gemini', 'model': model_name,
                                'prompt_summary': prompt[:200],
                                'license': 'generated', 'source_page': 'gemini_api',
                            }
            except Exception as e:
                err = str(e)
                # Billing / quota = 0 → inutile ritentare altri modelli
                if 'paid plan' in err or ('RESOURCE_EXHAUSTED' in err and 'limit: 0' in err):
                    logger.warning('      Gemini: image generation richiede billing — skip (fallback a provider open)')
                    return None, None
                logger.warning(f'      Gemini {model_name}: {e}')

        # Imagen 4 via generate_images
        for img_model in ('imagen-4.0-fast-generate-001', 'imagen-4.0-generate-001'):
            try:
                response = client.models.generate_images(
                    model=img_model, prompt=prompt,
                    config=genai_types.GenerateImagesConfig(
                        number_of_images=1, aspect_ratio='3:4',
                        person_generation='DONT_ALLOW',
                    ),
                )
                if response.generated_images:
                    from PIL import Image
                    img_bytes = response.generated_images[0].image.image_bytes
                    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                    logger.info(f'      ✓ Gemini: immagine generata ({img_model})')
                    return img, {
                        'provider': 'gemini', 'model': img_model,
                        'prompt_summary': prompt[:200],
                        'license': 'generated', 'source_page': 'gemini_api',
                    }
            except Exception as e:
                if 'paid plan' in str(e):
                    logger.warning('      Gemini Imagen: solo piani a pagamento — skip')
                    return None, None
                logger.warning(f'      Gemini {img_model}: {e}')

        logger.warning('      Gemini: nessun modello image disponibile')
    except ImportError:
        logger.warning('      Gemini: google-genai non installato')
    except Exception as e:
        logger.warning(f'      Gemini: {e}')
    return None, None


# ── Gemini: keyword enhancement GRATUITO (text model) ────────────────────────
def enhance_keywords_with_gemini(song_title: str, artist: str,
                                  dedication_text: str, tags: str) -> str:
    """
    Usa gemini-2.0-flash (GRATUITO) per generare keyword di ricerca
    ottimizzate in inglese da usare con Openverse/Wikimedia.
    Restituisce una query stringa oppure '' se non disponibile.
    """
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return ''
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        excerpt = dedication_text[:150]
        text_prompt = (
            f'You are a visual search expert for a music dedication website.\n'
            f'Song: "{song_title}" by {artist}\n'
            f'Dedication: "{excerpt}"\nTags: {tags}\n\n'
            f'Generate 3-4 English keywords for searching a beautiful landscape photo '
            f'that evokes the emotional mood of this song. '
            f'NO text, no artist faces, no album covers. '
            f'Only landscapes, skies, cityscapes, nature scenes.\n'
            f'Reply with ONLY the keywords, comma-separated, no explanation.'
        )
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=text_prompt,
        )
        kws = response.text.strip().strip('"').strip("'")
        if kws:
            logger.info(f'      ✓ Gemini text: keyword migliorate → "{kws}"')
            return kws
    except Exception as e:
        logger.warning(f'      Gemini text keywords: {e}')
    return ''


# ── Pexels ────────────────────────────────────────────────────────────────────
def try_pexels(query: str):
    api_key = os.environ.get('PEXELS_API_KEY', '').strip()
    if not api_key:
        logger.info('      Pexels: PEXELS_API_KEY assente — skip')
        return None, None
    r = _get('https://api.pexels.com/v1/search',
             params={'query': query, 'orientation': 'portrait', 'per_page': 10},
             headers={'Authorization': api_key})
    if not r:
        return None, None
    photos = r.json().get('photos', [])
    if not photos:
        logger.warning(f'      Pexels: nessun risultato per "{query}"')
        return None, None
    photo = random.choice(photos[:5])
    img_url = photo.get('src', {}).get('large2x') or photo.get('src', {}).get('large', '')
    img = _img_from_url(img_url)
    if img:
        logger.info(f'      ✓ Pexels: {photo.get("photographer", "?")}')
        return img, {
            'provider': 'pexels', 'query': query,
            'image_url': img_url,
            'photographer': photo.get('photographer', 'Unknown'),
            'photographer_url': photo.get('photographer_url', ''),
            'license': 'Pexels License', 'source_page': photo.get('url', ''),
        }
    return None, None


# ── Unsplash ──────────────────────────────────────────────────────────────────
def try_unsplash(query: str):
    api_key = os.environ.get('UNSPLASH_ACCESS_KEY', '').strip()
    if not api_key:
        logger.info('      Unsplash: UNSPLASH_ACCESS_KEY assente — skip')
        return None, None
    r = _get('https://api.unsplash.com/search/photos',
             params={'query': query, 'orientation': 'portrait', 'per_page': 10},
             headers={'Authorization': f'Client-ID {api_key}'})
    if not r:
        return None, None
    results = r.json().get('results', [])
    if not results:
        logger.warning(f'      Unsplash: nessun risultato per "{query}"')
        return None, None
    photo = random.choice(results[:5])
    img_url = photo.get('urls', {}).get('regular', '')
    user = photo.get('user', {})
    img = _img_from_url(img_url)
    if img:
        logger.info(f'      ✓ Unsplash: {user.get("name", "?")}')
        return img, {
            'provider': 'unsplash', 'query': query,
            'image_url': img_url,
            'photographer': user.get('name', 'Unknown'),
            'photographer_url': f'https://unsplash.com/@{user.get("username", "")}',
            'license': 'Unsplash License',
            'source_page': photo.get('links', {}).get('html', ''),
        }
    return None, None


# ── Openverse ─────────────────────────────────────────────────────────────────
def try_openverse(query: str):
    # Prova query progressivamente più brevi se necessario
    words = query.split()
    queries = [
        ' '.join(words[:3]),
        ' '.join(words[:2]),
        words[0] if words else 'sunset',
    ]
    for q in dict.fromkeys(queries):  # deduplica mantenendo ordine
        r = _get('https://api.openverse.org/v1/images/', params={
            'q': q, 'orientation': 'tall',
            'license_type': 'commercial,modification', 'page_size': 10,
        }, headers={'User-Agent': 'DDG FF Site/1.0'})
        if not r:
            continue
        results = [x for x in r.json().get('results', [])
                   if x.get('url') and x.get('width', 0) >= 400]
        if not results:
            logger.warning(f'      Openverse: nessun risultato per "{q}" — retry con query più breve')
            continue
        photo = random.choice(results[:5])
        img = _img_from_url(photo['url'])
        if img:
            logger.info(f'      ✓ Openverse: {photo.get("creator", "?")} (query: "{q}")')
            return img, {
                'provider': 'openverse', 'query': q,
                'image_url': photo.get('url', ''),
                'photographer': photo.get('creator', 'Unknown'),
                'photographer_url': photo.get('creator_url', ''),
                'license': photo.get('license', 'Creative Commons'),
                'source_page': photo.get('foreign_landing_url', ''),
            }
    logger.warning(f'      Openverse: nessun risultato utile')
    return None, None


# ── Wikimedia Commons ─────────────────────────────────────────────────────────
def try_wikimedia(query: str):
    words = query.split()
    queries = [' '.join(words[:2]), words[0] if words else 'sunset']
    for q in dict.fromkeys(queries):
        r = _get('https://commons.wikimedia.org/w/api.php', params={
            'action': 'query', 'list': 'search',
            'srsearch': f'{q} filetype:jpg|png',
            'srnamespace': '6', 'srlimit': '10', 'format': 'json',
        }, headers={'User-Agent': 'DDG FF Site/1.0'})
        if not r:
            continue
        items = r.json().get('query', {}).get('search', [])
        if not items:
            logger.warning(f'      Wikimedia: nessun risultato per "{q}"')
            continue
        for item in random.sample(items, min(3, len(items))):
            title = item.get('title', '')
            ir = _get('https://commons.wikimedia.org/w/api.php', params={
                'action': 'query', 'titles': title,
                'prop': 'imageinfo', 'iiprop': 'url|user|extmetadata', 'format': 'json',
            }, headers={'User-Agent': 'DDG FF Site/1.0'})
            if not ir:
                continue
            for page in ir.json().get('query', {}).get('pages', {}).values():
                ii = page.get('imageinfo', [{}])[0]
                url = ii.get('url', '')
                if not url or not url.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                img = _img_from_url(url)
                if img and img.width >= 400:
                    meta = ii.get('extmetadata', {})
                    logger.info(f'      ✓ Wikimedia: {ii.get("user", "?")}')
                    return img, {
                        'provider': 'wikimedia', 'query': q,
                        'image_url': url,
                        'photographer': ii.get('user', 'Unknown'),
                        'photographer_url': '',
                        'license': meta.get('License', {}).get('value', 'Wikimedia Commons'),
                        'source_page': f'https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}',
                    }
    return None, None


# ── Pipeline principale ───────────────────────────────────────────────────────
_PROVIDERS = {
    'gemini':    (try_gemini,    'prompt'),
    'pexels':    (try_pexels,    'query'),
    'unsplash':  (try_unsplash,  'query'),
    'openverse': (try_openverse, 'query'),
    'wikimedia': (try_wikimedia, 'query'),
}
_ORDER = ['gemini', 'pexels', 'unsplash', 'openverse', 'wikimedia']


def fetch_background(prompt: str, query: str, provider_override: str = 'auto'):
    """
    Prova i provider nell'ordine configurato.
    Restituisce (PIL.Image|None, attribution|None).
    """
    if provider_override and provider_override not in ('auto', 'local'):
        fn, arg_type = _PROVIDERS.get(provider_override, (None, None))
        if fn:
            arg = prompt if arg_type == 'prompt' else query
            logger.info(f'    Trying provider: {provider_override}')
            return fn(arg)
        logger.warning(f'    Provider sconosciuto: {provider_override}')
        return None, None

    if provider_override == 'local':
        return None, None

    for name in _ORDER:
        logger.info(f'    Trying provider: {name}')
        fn, arg_type = _PROVIDERS[name]
        arg = prompt if arg_type == 'prompt' else query
        img, attr = fn(arg)
        if img:
            return img, attr

    logger.warning('    Tutti i provider falliti — uso fallback locale')
    return None, None
