// src/pages/sitemap.xml.ts
// Endpoint Astro — genera /sitemap.xml corretto per GitHub Pages
import type { APIRoute } from 'astro';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const SITE_BASE = 'https://legnaro72.github.io/dediche-musicali-ff';

function escapeXml(url: string): string {
  return url.replace(/&/g, '&amp;');
}

export const GET: APIRoute = () => {
  const today = new Date().toISOString().split('T')[0];

  // Pagine statiche
  const entries: string[] = [
    `  <url>
    <loc>${escapeXml(`${SITE_BASE}/`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>`,
    `  <url>
    <loc>${escapeXml(`${SITE_BASE}/archive/`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>`,
  ];

  // Pagine dediche pubblicate
  const dataDir = join(process.cwd(), 'data', 'dedications');
  if (existsSync(dataDir)) {
    const files = readdirSync(dataDir).filter(f => f.endsWith('.json')).sort();
    for (const f of files) {
      try {
        const ded = JSON.parse(readFileSync(join(dataDir, f), 'utf-8'));
        if (ded.status === 'published' && ded.id) {
          const lastmod = (ded.updated_at ?? ded.created_at ?? ded.date).split('T')[0];
          entries.push(`  <url>
    <loc>${escapeXml(`${SITE_BASE}/dediche/${ded.id}/`)}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>`);
        }
      } catch (_) { /* ignora file corrotti */ }
    }
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries.join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
    },
  });
};
