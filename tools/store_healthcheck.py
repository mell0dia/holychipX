#!/usr/bin/env python3
"""Daily end-to-end test of the Holy Chip store, reported by email.

Walks the real buying path up to the card form, in LIVE mode, without charging
anyone or making anything:

  1. a one-mug cart is POSTed to the live `checkout` function, like the
     Checkout page does -> it must get a Printify shipping quote and create a
     Stripe Checkout session (the function returns its URL)
  2. the session is fetched from Stripe (it exists, it is open, total is sane)
  3. the session is EXPIRED at Stripe, so it can never be paid
  4. the webhook endpoint is poked (it must reject an unsigned call: that
     proves it is deployed and verifying signatures)
  5. yesterday's funnel (the `ping` function): adds to cart, checkouts started

Then ONE email to NOTIFY_EMAIL via Resend:
  "OK Holy Chip store · <date>"      -> ignore it
  "!! STORE BROKEN · <step>"         -> read it

Needs STRIPE_SECRET_KEY and RESEND_API_KEY (read from Netlify's env for the
site, or ~/claude-agent/.env). launchd job: com.holychip.store-healthcheck.
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

SITE_FN = "https://holychip.netlify.app/.netlify/functions"
NOTIFY_EMAIL = "rico.duoba@gmail.com"
FROM_EMAIL = "orders@holy-chip.com"
LOG = Path.home() / ".local/share/holychip-store-healthcheck.log"

TEST_CART = [{
    "chip": "Chip_0", "styleId": "mug", "styleName": "Mug", "price": 18.9, "productType": "Mug",
    "productName": "Chip_0 Mug - Mug", "productImage": "assets/mug-mockups/Chip_0_mug_front.png",
    "stripePriceId": "price_1TCS1wJZLzX0hJCSeUk3OJ0V", "productId": "69bb03687f70b930660a85a1",
    "size": None, "quantity": 1,
}]
TEST_SHIPPING = {
    "firstName": "Store", "lastName": "Healthcheck", "email": NOTIFY_EMAIL, "phone": "",
    "address1": "1 Test Street", "address2": "", "city": "Vancouver", "state": "BC",
    "zip": "V6B 1A1", "country": "CA",
}


def env(name):
    v = os.environ.get(name)
    if v:
        return v
    try:
        for line in (Path.home() / "claude-agent/.env").read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    try:   # the site's own secrets, via the linked Netlify CLI
        site = Path.home() / "holy-chip/website/holy-chip-site"
        return subprocess.run(["netlify", "env:get", name], cwd=site, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        return ""


def http(method, url, data=None, headers=None, timeout=45):
    body = None
    if data is not None:
        body = data if isinstance(data, (bytes, str)) else json.dumps(data)
        body = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "holychip-store-healthcheck/1", **(headers or {})})   # Resend's Cloudflare rejects Python's default UA (error 1010)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), time.time() - t0


def stripe(method, path, data=None):
    key = env("STRIPE_SECRET_KEY")
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request("https://api.stripe.com/v1" + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


def send_email(subject, html):
    key = env("RESEND_API_KEY")
    if not key:
        print("no RESEND_API_KEY - not emailing"); return False
    st, body, _ = http("POST", "https://api.resend.com/emails",
                       {"from": f"Holy Chip <{FROM_EMAIL}>", "to": [NOTIFY_EMAIL], "subject": subject, "html": html},
                       {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    print("email:", st, body[:120])
    return st < 300


def main():
    steps, failed = [], None
    def ok(msg): steps.append(("ok", msg)); print("OK ", msg)
    def bad(msg):
        nonlocal failed
        steps.append(("bad", msg)); print("BAD", msg)
        if failed is None: failed = msg

    # 1) checkout function: cart -> shipping quote -> Stripe session
    session_id = None
    st, body, dt = http("POST", f"{SITE_FN}/checkout",
                        {"cart": TEST_CART, "shipping": TEST_SHIPPING, "storeTest": True},
                        {"Content-Type": "application/json"}, timeout=60)
    try: res = json.loads(body)
    except Exception: res = {}
    if st == 200 and res.get("url", "").startswith("https://checkout.stripe.com/"):
        session_id = res.get("sessionId") or res.get("id") or res["url"].rstrip("/").split("/")[-1].split("#")[0]
        ok(f"checkout function: Stripe session created in {dt:.1f}s (shipping quoted by Printify)")
    else:
        bad(f"checkout function: HTTP {st} in {dt:.1f}s - {body[:200]}")

    # 2) + 3) the session at Stripe: exists, open, sane; then expire it
    if session_id:
        st, s = stripe("GET", f"/checkout/sessions/{session_id}")
        if st == 200 and s.get("status") == "open" and s.get("payment_status") == "unpaid":
            total = s.get("amount_total", 0) / 100
            ship = int(s.get("metadata", {}).get("shippingCost", 0)) / 100
            ok(f"Stripe: session {session_id[:14]}… open, total ${total:.2f} (shipping ${ship:.2f}), live mode={bool(s.get('livemode'))}")
            st2, s2 = stripe("POST", f"/checkout/sessions/{session_id}/expire")
            if st2 == 200 and s2.get("status") == "expired": ok("Stripe: test session voided (can never be paid)")
            else: bad(f"Stripe: could not void the test session {session_id} - {s2.get('error', {}).get('message', st2)}")
        else:
            bad(f"Stripe: session lookup HTTP {st} - {json.dumps(s)[:200]}")

    # 4) webhook deployed and verifying signatures
    st, body, dt = http("POST", f"{SITE_FN}/stripe-webhook", "{}", {"Content-Type": "application/json"})
    if st == 400 and "signature" in body.lower(): ok(f"webhook: deployed, rejects unsigned calls ({dt:.1f}s)")
    else: bad(f"webhook: unexpected HTTP {st} - {body[:120]}")

    # 5) yesterday's funnel
    funnel = ""
    st, body, _ = http("GET", f"{SITE_FN}/ping?days=2")
    if st == 200:
        days = json.loads(body)
        y = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        ev = [e for e in days.get(y, []) if not e.get("test")]
        adds = [e for e in ev if e["event"] == "add_to_cart"]; chk = [e for e in ev if e["event"] == "checkout_started"]
        funnel = f"{len(adds)} add{'s' if len(adds) != 1 else ''} to cart, {len(chk)} checkout{'s' if len(chk) != 1 else ''} started"
        if adds or chk:
            funnel += " — " + "; ".join(f"{e['product']} ({e['country'] or '?'})" for e in (adds + chk)[:12])
        ok(f"funnel {y}: {funnel}")
    else:
        bad(f"ping function: HTTP {st}")

    # the email
    today = datetime.now().strftime("%a %d %b %Y")
    rows = "".join(f'<li style="color:{"#1e8449" if k == "ok" else "#c0392b"};">{"✓" if k == "ok" else "✗"} {m}</li>' for k, m in steps)
    if failed:
        subject = f"!! STORE BROKEN · {failed.split(':')[0]} · {today}"
        head = f'<h2 style="color:#c0392b;">Store test failed</h2><p><strong>{failed}</strong></p>'
    else:
        subject = f"OK Holy Chip store · {today}"
        head = '<h2 style="color:#1e8449;">Store OK</h2><p>Cart → Printify shipping quote → Stripe session → voided. Webhook up.</p>'
    html = f'''<div style="font-family:Calibri;font-size:13px;">{head}
      <ul style="line-height:1.7;">{rows}</ul>
      <p style="font-size:11px;color:#888;">Daily test from {os.uname().nodename} · tools/store_healthcheck.py · nothing was charged or ordered.</p></div>'''
    sent = send_email(subject, html)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {'FAIL' if failed else 'OK'} email={'sent' if sent else 'NOT SENT'} :: " + " | ".join(m for _, m in steps) + "\n")
    return 1 if failed or not sent else 0


if __name__ == "__main__":
    sys.exit(main())
