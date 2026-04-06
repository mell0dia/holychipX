#!/usr/bin/env python3
"""
Bundle the War Room into a single self-contained HTML file for mobile.
Fetches live data from the running server, embeds it all inline.
Output: ~/holy-chip/warroom/warroom-mobile.html

Usage:
  python3 ~/holy-chip/warroom/bundle-warroom.py
  # Then send warroom-mobile.html via Telegram
"""

import json
import re
import sys
import urllib.request
from datetime import datetime

SERVER = "http://localhost:8888"

ENDPOINTS = [
    ("costs",    "/api/costs"),
    ("phrases",  "/api/all-phrases"),
    ("stories",  "/api/stories"),
    ("videos",   "/api/videos"),
    ("campaigns","/api/campaigns"),
    ("dms",      "/api/dms"),
]

def fetch(path):
    try:
        r = urllib.request.urlopen(f"{SERVER}{path}", timeout=10)
        return json.loads(r.read())
    except Exception as e:
        print(f"  WARN: failed to fetch {path}: {e}", file=sys.stderr)
        return {}

def main():
    # 1) Read the original HTML
    with open("/Users/rmello/holy-chip/warroom/index.html", "r") as f:
        html = f.read()

    # 2) Fetch all data
    print("Fetching data from War Room server...")
    data = {}
    for name, path in ENDPOINTS:
        print(f"  → {name}")
        data[name] = fetch(path)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M PST")

    # 3) Build the injection script that replaces fetch() calls with embedded data
    inject_js = f"""
<script>
// ── MOBILE BUNDLE: embedded data (generated {ts}) ──
window.__WARROOM_BUNDLE__ = true;
window.__WARROOM_DATA__ = {json.dumps(data)};
window.__WARROOM_TS__ = "{ts}";

// Override fetch to serve embedded data
const _origFetch = window.fetch;
const ROUTE_MAP = {{
  '/api/costs':       'costs',
  '/api/all-phrases': 'phrases',
  '/api/stories':     'stories',
  '/api/videos':      'videos',
  '/api/campaigns':   'campaigns',
  '/api/dms':         'dms',
}};

window.fetch = function(url, opts) {{
  const path = typeof url === 'string' ? url : url.toString();

  // GET requests to known endpoints → return embedded data
  if (!opts || !opts.method || opts.method === 'GET') {{
    for (const [route, key] of Object.entries(ROUTE_MAP)) {{
      if (path === route || path.endsWith(route)) {{
        return Promise.resolve(new Response(
          JSON.stringify(window.__WARROOM_DATA__[key]),
          {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}
        ));
      }}
    }}
  }}

  // POST requests (keep/delete/comment) → show toast, update local state
  if (opts && opts.method === 'POST') {{
    // phrase actions
    const phraseMatch = path.match(/\\/api\\/phrases\\/(\\d+)\\/(keep|delete|reset|comment)/);
    if (phraseMatch) {{
      return Promise.resolve(new Response(
        JSON.stringify({{ ok: true, note: '(offline — changes not saved)' }}),
        {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}
      ));
    }}
    const infMatch = path.match(/\\/api\\/influencer-phrase\\/.+\\/(keep|delete|reset|comment)/);
    if (infMatch) {{
      return Promise.resolve(new Response(
        JSON.stringify({{ ok: true, note: '(offline — changes not saved)' }}),
        {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}
      ));
    }}
  }}

  // fallback
  return Promise.resolve(new Response('{{}}', {{ status: 200 }}));
}};
</script>
"""

    # 4) Add PWA manifest + mobile meta tags
    pwa_meta = """
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="War Room">
    <meta name="theme-color" content="#0a0a14">
    <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect fill='%230a0a14' width='100' height='100' rx='20'/><text y='70' x='15' font-size='60'>⚡</text></svg>">
"""

    # 5) Add offline banner CSS + HTML
    offline_banner_css = """
    .offline-banner {
      background: #1a1408;
      border: 1px solid #3a2a10;
      color: #c8a040;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      text-align: center;
      padding: 6px 12px;
      position: sticky;
      top: 0;
      z-index: 9999;
    }
    .offline-banner strong { color: #e8c060; }
"""

    offline_banner_html = f'<div class="offline-banner">📱 <strong>OFFLINE SNAPSHOT</strong> — {ts} · read-only · actions won\'t save</div>'

    # 6) Inject into HTML
    # Add mobile meta after existing <meta> tags
    html = html.replace('</head>', pwa_meta + '</head>')

    # Add offline banner CSS
    html = html.replace('</style>', offline_banner_css + '</style>', 1)

    # Add offline banner as first child of body
    html = html.replace('<body>', '<body>\n' + offline_banner_html)

    # Inject data script right before </body>
    html = html.replace('</body>', inject_js + '\n</body>')

    # 7) Replace image URLs that point to localhost with data placeholders
    # Story images won't load offline, so replace with placeholder
    html = html.replace(
        'src="${imgSrc}"',
        'src="${imgSrc}" onerror="this.style.display=\'none\'"'
    )

    # 8) Write output
    out_path = "/Users/rmello/holy-chip/warroom/warroom-mobile.html"
    with open(out_path, "w") as f:
        f.write(html)

    import os
    size_kb = os.path.getsize(out_path) / 1024
    print(f"\n✅ Bundle created: {out_path}")
    print(f"   Size: {size_kb:.0f} KB")
    print(f"   Snapshot: {ts}")
    print(f"\n   Send to phone via Telegram, open in browser, tap 'Add to Home Screen'")

if __name__ == "__main__":
    main()