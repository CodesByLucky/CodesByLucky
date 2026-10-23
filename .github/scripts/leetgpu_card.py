#!/usr/bin/env python3
"""Generate LeetGPU stats cards (SVG) for a GitHub profile README.

Reads public data from api.leetgpu.com and writes:
  assets/leetgpu-stats.svg     rank, score, submissions, success rate, solved ring
  assets/leetgpu-progress.svg  difficulty bars, languages, GPU usage
  assets/leetgpu-activity.svg  submission heatmap for the last 52 weeks

Standard library only. If the API cannot be reached, existing cards are kept.
"""

import datetime as dt
import html
import json
import os
import sys
import time
import urllib.request

USER = os.environ.get("LEETGPU_USER", "CodeByLucky")
DISPLAY_NAME = os.environ.get("LEETGPU_DISPLAY_NAME", "Lucky Samant")
OUT_DIR = os.environ.get("LEETGPU_OUT_DIR", "assets")
FIXTURE = os.environ.get("LEETGPU_FIXTURE")  # local JSON for testing
API = "https://api.leetgpu.com/api/v1"

LANGS = ["cuda", "triton", "pytorch", "mojo", "cute", "jax"]
LANG_NAMES = {"cuda": "CUDA", "triton": "Triton", "pytorch": "PyTorch",
              "mojo": "Mojo", "cute": "CuTe DSL", "jax": "JAX"}
LANG_COLORS = {"cuda": "#76b900", "triton": "#f97316", "pytorch": "#ee4c2c",
               "mojo": "#ff6b35", "cute": "#a78bfa", "jax": "#38bdf8"}

# Theme (matches tokyonight cards, with LeetGPU teal accent)
BG = "#1a1b27"
BORDER = "#2a2e42"
TITLE = "#70a5fd"
TEXT = "#c0caf5"
MUTED = "#787c99"
VALUE = "#38bdae"
ACCENT = "#2dd4bf"
TRACK = "#2a2e42"
DIFF_COLORS = {"easy": "#4ade80", "medium": "#facc15", "hard": "#f87171"}
HEAT = ["#262a3b", "#0f4f49", "#16796e", "#1fa696", "#2dd4bf"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def get_json(url, retries=3):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; leetgpu-readme-card/1.0)",
        "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"retrying {url}: {e}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))


def load_data():
    if FIXTURE:
        with open(FIXTURE, encoding="utf-8") as f:
            return json.load(f)
    profile = get_json(f"{API}/profiles/{USER}")
    boards = {}
    for lang in LANGS:
        try:
            boards[lang] = get_json(f"{API}/submissions/leaderboard/{lang}")
        except Exception as e:  # noqa: BLE001
            print(f"leaderboard {lang} unavailable: {e}", file=sys.stderr)
    return {"profile": profile, "leaderboards": boards}


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_int(n):
    return f"{int(n):,}"


def best_rank(boards):
    best = None
    for lang, board in boards.items():
        for entry in (board or {}).get("leaderboard", []) or []:
            if str(entry.get("username", "")).lower() == USER.lower():
                cand = {"lang": lang, "rank": entry.get("rank"),
                        "score": entry.get("globalScore", 0)}
                if best is None or cand["rank"] < best["rank"]:
                    best = cand
    return best


def gpu_name(name):
    return "NVIDIA Tesla T4" if name.upper() == "T4" else f"NVIDIA {name}"


def card(width, height, body, title):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<style>
  .t {{ font: 600 18px {FONT}; fill: {TITLE}; }}
  .h {{ font: 600 13px {FONT}; fill: {TEXT}; }}
  .l {{ font: 600 14px {FONT}; fill: {TEXT}; }}
  .v {{ font: 700 14px {FONT}; fill: {VALUE}; }}
  .s {{ font: 400 12px {FONT}; fill: {MUTED}; }}
  .big {{ font: 800 26px {FONT}; fill: {TEXT}; }}
  .rank {{ font: 800 15px {FONT}; fill: {ACCENT}; }}
  .fade {{ animation: fade .6s ease-in-out both; }}
  .grow {{ transform-box: fill-box; transform-origin: left; animation: grow 1s ease-out both; }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @media (prefers-reduced-motion: reduce) {{ .fade, .grow {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" rx="6" width="{width - 1}" height="{height - 1}" fill="{BG}" stroke="{BORDER}"/>
{body}
</svg>
"""


def stats_card(p, rank):
    total = sum(v["total"] for v in p["solvedProblems"].values())
    solved = sum(v["solved"] for v in p["solvedProblems"].values())
    subs = p.get("totalSubmissions", 0)
    ok = p.get("successfulSubmissions", 0)
    rate = f"{ok / subs * 100:.1f}%" if subs else "0%"
    streak = p.get("streak", 0)
    gpus = p.get("acceleratorBreakdown") or {}
    fav = gpu_name(max(gpus, key=gpus.get)) if gpus else "None yet"

    if rank:
        rank_val = f"#{rank['rank']} · {LANG_NAMES.get(rank['lang'], rank['lang'])}"
        score_val = fmt_int(rank["score"])
    else:
        rank_val, score_val = "Outside top 100", "-"

    rows = [("Global Rank", rank_val, "rank"), ("Global Score", score_val, "v"),
            ("Problems Solved", f"{solved} / {total}", "v"),
            ("Total Submissions", fmt_int(subs), "v"), ("Success Rate", rate, "v"),
            ("Current Streak", f"{streak} day{'s' if streak != 1 else ''}", "v")]
    body = [f'<text x="25" y="35" class="t">{esc(DISPLAY_NAME)}\'s LeetGPU Stats</text>']
    for i, (label, value, cls) in enumerate(rows):
        y = 66 + i * 22
        delay = 0.15 * i
        body.append(
            f'<g class="fade" style="animation-delay:{delay:.2f}s">'
            f'<circle cx="31" cy="{y - 5}" r="4" fill="{ACCENT if cls == "rank" else VALUE}"/>'
            f'<text x="43" y="{y}" class="l">{esc(label)}:</text>'
            f'<text x="190" y="{y}" class="{cls}">{esc(value)}</text></g>')

    # solved ring
    cx, cy, r = 400, 108, 46
    circ = 2 * 3.14159265 * r
    frac = solved / total if total else 0
    dash = circ * frac
    body.append(f"""<g transform="rotate(-90 {cx} {cy})">
  <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{TRACK}" stroke-width="8"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{ACCENT}" stroke-width="8" stroke-linecap="round"
    stroke-dasharray="{dash:.2f} {circ:.2f}" stroke-dashoffset="0">
    <animate attributeName="stroke-dashoffset" from="{dash:.2f}" to="0" dur="1.2s" fill="freeze"/>
  </circle>
</g>
<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="big">{solved}</text>
<text x="{cx}" y="{cy + 22}" text-anchor="middle" class="s">of {total} solved</text>
<text x="{cx}" y="182" text-anchor="middle" class="s">Favorite GPU: {esc(fav)}</text>""")
    return card(495, 195, "\n".join(body), f"{DISPLAY_NAME}'s LeetGPU Stats")


def progress_card(p):
    body = ['<text x="25" y="35" class="t">Progress on LeetGPU</text>',
            '<text x="25" y="62" class="h">Difficulty</text>']
    bar_w = 190
    for i, level in enumerate(["easy", "medium", "hard"]):
        d = p["solvedProblems"].get(level, {"solved": 0, "total": 0})
        y = 86 + i * 34
        frac = d["solved"] / d["total"] if d["total"] else 0
        body.append(
            f'<g class="fade" style="animation-delay:{0.15 * i:.2f}s">'
            f'<text x="25" y="{y}" class="l">{level.title()}</text>'
            f'<text x="{25 + bar_w}" y="{y}" text-anchor="end" class="s">{d["solved"]} / {d["total"]}</text>'
            f'<rect x="25" y="{y + 7}" width="{bar_w}" height="8" rx="4" fill="{TRACK}"/>'
            f'<rect class="grow" style="animation-delay:{0.15 * i:.2f}s" x="25" y="{y + 7}" '
            f'width="{max(frac * bar_w, 0 if frac == 0 else 8):.1f}" height="8" rx="4" fill="{DIFF_COLORS[level]}"/></g>')

    # languages
    total = sum(v["total"] for v in p["solvedProblems"].values()) or 1
    langs = p.get("languages") or {}
    used = sorted(((k, v.get("solved", 0)) for k, v in langs.items() if v.get("solved", 0) > 0),
                  key=lambda kv: -kv[1])[:3]
    x0 = 265
    body.append(f'<text x="{x0}" y="62" class="h">Solved by Language</text>')
    if not used:
        body.append(f'<text x="{x0}" y="86" class="s">No solves yet</text>')
    for i, (lang, n) in enumerate(used):
        y = 86 + i * 20
        body.append(
            f'<g class="fade" style="animation-delay:{0.15 * i:.2f}s">'
            f'<circle cx="{x0 + 5}" cy="{y - 5}" r="5" fill="{LANG_COLORS.get(lang, ACCENT)}"/>'
            f'<text x="{x0 + 16}" y="{y}" class="l">{esc(LANG_NAMES.get(lang, lang))}</text>'
            f'<text x="470" y="{y}" text-anchor="end" class="v">{n} <tspan class="s">({n / total * 100:.0f}%)</tspan></text></g>')

    # GPU usage
    gpus = p.get("acceleratorBreakdown") or {}
    gsum = sum(gpus.values())
    body.append(f'<text x="{x0}" y="148" class="h">GPU Usage</text>')
    palette = [ACCENT, "#bf91f3", "#facc15", "#f87171", "#38bdf8"]
    x, w_total = x0, 205
    legend = []
    body.append(f'<rect x="{x0}" y="156" width="{w_total}" height="8" rx="4" fill="{TRACK}"/>')
    for i, (name, count) in enumerate(sorted(gpus.items(), key=lambda kv: -kv[1])[:5]):
        w = w_total * count / gsum if gsum else 0
        color = palette[i % len(palette)]
        body.append(f'<rect class="grow" x="{x:.1f}" y="156" width="{w:.1f}" height="8" fill="{color}"/>')
        x += w
        legend.append((name, count / gsum * 100 if gsum else 0, color))
    lx = x0
    for name, pct, color in legend[:3]:
        label = f"{name} {pct:.0f}%"
        body.append(f'<circle cx="{lx + 4}" cy="178" r="4" fill="{color}"/>'
                    f'<text x="{lx + 12}" y="182" class="s">{esc(label)}</text>')
        lx += 12 + len(label) * 7 + 10
    if not gpus:
        body.append(f'<text x="{x0}" y="182" class="s">No runs yet</text>')
    return card(495, 195, "\n".join(body), "Progress on LeetGPU")


def activity_card(p):
    counts = {}
    for c in p.get("contributions") or []:
        counts[c["date"]] = counts.get(c["date"], 0) + int(c.get("count", 0))
    dates = [dt.date.fromisoformat(d) for d in counts] or [dt.date.today()]
    end = max(max(dates), dt.datetime.now(dt.timezone.utc).date())
    weeks = 52
    # grid starts on a Sunday so each column is one week
    end_sunday = end - dt.timedelta(days=(end.weekday() + 1) % 7)
    start = end_sunday - dt.timedelta(weeks=weeks - 1)
    cell, gap = 13, 4
    step = cell + gap
    x0, y0 = 50, 72
    vals = [v for v in counts.values() if v > 0]
    peak = max(vals) if vals else 1

    def level(v):
        if v <= 0:
            return 0
        return min(4, 1 + int((v / peak) * 3.999))

    body = []
    year_total = 0
    months_seen = set()
    for w in range(weeks):
        col_start = start + dt.timedelta(weeks=w)
        mkey = (col_start.year, col_start.month)
        if col_start.day <= 7 and mkey not in months_seen:
            months_seen.add(mkey)
            body.append(f'<text x="{x0 + w * step}" y="{y0 - 8}" class="s">{col_start.strftime("%b")}</text>')
        for d in range(7):
            day = col_start + dt.timedelta(days=d)
            if day > end:
                continue
            v = counts.get(day.isoformat(), 0)
            year_total += v
            body.append(f'<rect x="{x0 + w * step}" y="{y0 + d * step}" width="{cell}" height="{cell}" '
                        f'rx="2" fill="{HEAT[level(v)]}"/>')
    for d, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(f'<text x="18" y="{y0 + d * step + 10}" class="s">{name}</text>')

    width = x0 + weeks * step + 22
    height = y0 + 7 * step + 34
    joined = (p.get("joinedDate") or "")[:10]
    joined_txt = ""
    if joined:
        joined_txt = "Joined " + dt.date.fromisoformat(joined).strftime("%b %Y")
    header = [f'<text x="25" y="35" class="t">LeetGPU Submission Activity</text>',
              f'<text x="{width - 25}" y="35" text-anchor="end" class="h">{fmt_int(year_total)} submissions in the last year</text>']
    ly = y0 + 7 * step + 18
    more_x = width - 25 - 30
    boxes_x = more_x - 6 - 5 * step
    legend = [f'<text x="{x0}" y="{ly + 9}" class="s">{esc(joined_txt)}</text>',
              f'<text x="{boxes_x - 6}" y="{ly + 9}" text-anchor="end" class="s">Less</text>']
    for i, c in enumerate(HEAT):
        legend.append(f'<rect x="{boxes_x + i * step}" y="{ly}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    legend.append(f'<text x="{more_x}" y="{ly + 9}" class="s">More</text>')
    inner = "\n".join(header + ['<g class="fade">'] + body + ["</g>"] + legend)
    return card(width, height, inner, "LeetGPU Submission Activity")


def main():
    try:
        data = load_data()
    except Exception as e:  # noqa: BLE001
        print(f"LeetGPU API unavailable, keeping existing cards: {e}", file=sys.stderr)
        return 0
    p = data["profile"]
    if "solvedProblems" not in p:
        print("Unexpected profile response, keeping existing cards", file=sys.stderr)
        return 0
    rank = best_rank(data.get("leaderboards") or {})
    os.makedirs(OUT_DIR, exist_ok=True)
    outputs = {"leetgpu-stats.svg": stats_card(p, rank),
               "leetgpu-progress.svg": progress_card(p),
               "leetgpu-activity.svg": activity_card(p)}
    for name, svg in outputs.items():
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {name}")
    print(f"rank: {rank}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
