#!/usr/bin/env python3
"""Animate one still on the M5 (Wan 2.2 I2V) - submit, poll, download.

    m5_video.py IMAGE "motion prompt" OUT.mp4 [--seed N] [--frames 81]

The M5 contract (user, 2026-10-13): POST /v1/videos/generations with image
(base64 or URL) + prompt -> job id + status_url; poll status_url until
status == succeeded; the clip is at data[0].url. The first job after a cold
start also waits for the model to load (5-15 min), so polling is patient.
"""
import base64, json, sys, time, urllib.error, urllib.request
from pathlib import Path

BASE = "https://ricardos-macbook-pro.tailfb1456.ts.net:8443"
URL = BASE + "/v1/videos/generations"


def _req(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                        "Authorization": "Bearer unused"})
    return json.load(urllib.request.urlopen(r, timeout=120))


def _abs(u):
    return u if u.startswith("http") else BASE + u


def animate(image, prompt, out, seed=42, frames=None, timeout=3 * 3600, poll=15):
    body = {"image": base64.b64encode(Path(image).read_bytes()).decode(), "prompt": prompt, "seed": seed}
    if frames:                                   # M5: num_frames = 4k+1, 5..81 (16 fps -> 81 = 5 s); default 33
        body["num_frames"] = frames
    job = _req(URL, body)
    status_url = _abs(job.get("status_url") or f"{URL}/{job['id']}")
    print(f"  job {job.get('id')} submitted", flush=True)
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            j = _req(status_url)
        except urllib.error.HTTPError as e:
            if e.code == 404:                     # server restarted and forgot the job: submit it again
                print("  job lost (M5 restarted?) - resubmitting", flush=True)
                job = _req(URL, body); status_url = _abs(job.get("status_url") or f"{URL}/{job['id']}")
                print(f"  job {job.get('id')} submitted", flush=True); continue
            print(f"  poll error ({e}), retrying", flush=True); continue
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"  poll warning ({e}), retrying", flush=True); continue
        st = j.get("status")
        if st != last:
            print(f"  {st} after {time.time() - t0:.0f}s", flush=True); last = st
        if st == "succeeded":
            urllib.request.urlretrieve(_abs(j["data"][0]["url"]), out)
            return out
        if st in ("failed", "error", "cancelled"):
            raise RuntimeError(f"M5 video job {st}: {j.get('error') or j}")
    raise TimeoutError(f"M5 video job not done after {timeout}s: {status_url}")


if __name__ == "__main__":
    av = sys.argv[1:]
    a = [x for i, x in enumerate(av) if not x.startswith("--") and not (i and av[i - 1].startswith("--"))]
    opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    animate(a[0], a[1], a[2], seed=opt("--seed", 42), frames=opt("--frames", 0) or None)
    print(a[2])
