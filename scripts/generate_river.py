#!/usr/bin/env python3
"""Generate a flowing, repository-labelled SVG commit river for a GitHub profile."""
import argparse
import datetime as dt
import json
import math
import os
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

WIDTH, HEIGHT = 1200, 430
LEFT, RIGHT = 72, 1128
MONTHS = 12
PALETTE = ["#8f9da5", "#73848d", "#a17c83", "#87949b", "#6d7f88",
           "#b18c91", "#7f8e96", "#9aa5aa", "#806d75", "#aab3b7"]

def api(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "vo1dfull-commit-river"
    })
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)

def collect(username, token):
    now = dt.datetime.now(dt.timezone.utc)
    month_number = now.year * 12 + now.month - 1 - 11
    start_year, start_month_zero = divmod(month_number, 12)
    start = dt.datetime(start_year, start_month_zero + 1, 1, tzinfo=dt.timezone.utc)
    start_iso = start.isoformat().replace("+00:00", "Z")
    end_iso = now.isoformat().replace("+00:00", "Z")

    repos = []
    page = 1
    while page <= 5:
        url = f"https://api.github.com/users/{urllib.parse.quote(username)}/repos?type=owner&visibility=public&sort=pushed&per_page=100&page={page}"
        batch = api(url, token)
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    result = []
    # Most recently pushed repositories first; cap API work and keep the SVG legible.
    for repo in repos[:30]:
        owner = repo["owner"]["login"]
        name = repo["name"]
        counts = [0] * MONTHS
        page = 1
        while page <= 10:
            query = urllib.parse.urlencode({
                "author": username,
                "since": start_iso,
                "until": end_iso,
                "per_page": 100,
                "page": page
            })
            url = f"https://api.github.com/repos/{owner}/{name}/commits?{query}"
            try:
                commits = api(url, token)
            except Exception as exc:
                print(f"Skipping {name}: {exc}")
                break
            if not commits:
                break
            for item in commits:
                raw = item.get("commit", {}).get("author", {}).get("date")
                if not raw:
                    continue
                when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                idx = (when.year - start.year) * 12 + when.month - start.month
                if 0 <= idx < MONTHS:
                    counts[idx] += 1
            if len(commits) < 100:
                break
            page += 1
        if sum(counts):
            result.append({"name": name, "counts": counts, "total": sum(counts)})

    result.sort(key=lambda row: row["total"], reverse=True)
    if len(result) > 5:
        rest = [0] * MONTHS
        for row in result[5:]:
            rest = [a + b for a, b in zip(rest, row["counts"])]
        result = result[:5] + [{"name": "other activity", "counts": rest, "total": sum(rest)}]
    return result[:6], start, now

def demo_data():
    # Only used for the local visual preview; Actions replaces this with live GitHub data.
    names = ["systems-lab", "rust-tools", "security-notes", "linux-playground",
             "packet-watch", "other activity"]
    profiles = [
        [0,1,2,0,4,3,8,2,1,0,5,3],
        [0,0,1,3,2,7,4,2,6,3,1,0],
        [1,0,0,2,5,3,1,7,2,1,4,2],
        [0,2,3,1,0,2,4,1,0,3,5,2],
        [0,0,0,1,3,1,0,4,2,5,1,0],
        [2,1,0,1,1,0,2,0,1,3,1,2],
    ]
    return [{"name": n, "counts": c, "total": sum(c)} for n,c in zip(names,profiles)], dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=365), dt.datetime.now(dt.timezone.utc)

def catmull(points):
    if len(points) < 2:
        return ""
    d = f"M {points[0][0]:.1f},{points[0][1]:.1f}"
    for i in range(len(points)-1):
        p0 = points[i-1] if i > 0 else points[i]
        p1, p2 = points[i], points[i+1]
        p3 = points[i+2] if i+2 < len(points) else p2
        c1x = p1[0] + (p2[0]-p0[0])/6
        c1y = p1[1] + (p2[1]-p0[1])/6
        c2x = p2[0] - (p3[0]-p1[0])/6
        c2y = p2[1] - (p3[1]-p1[1])/6
        d += f" C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d

def render(rows, username, start, end, output):
    # Keep at least one quiet stream so a brand-new account still gets a designed composition.
    if not rows:
        rows = [{"name": "first-commits", "counts": [0]*MONTHS, "total": 0}]
    xvals = [LEFT + (RIGHT-LEFT)*i/(MONTHS-1) for i in range(MONTHS)]
    total_commits = sum(r["total"] for r in rows)
    max_repo = max(1, max(max(r["counts"]) for r in rows))
    # The lanes gently overlap, like the reference image, but labels remain readable.
    lane_gap = 48
    first_y = 112 if len(rows) > 5 else 126
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
      '<defs>',
      '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#202a2f"/><stop offset="1" stop-color="#1b2429"/></linearGradient>',
      '<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="7"/></filter>',
      '<linearGradient id="ribbon" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a8b4ba" stop-opacity=".02"/><stop offset=".5" stop-color="#a8b4ba" stop-opacity=".14"/><stop offset="1" stop-color="#a8b4ba" stop-opacity=".02"/></linearGradient>',
      '</defs>',
      '<rect width="100%" height="100%" fill="url(#bg)"/>',
      '<text x="42" y="34" fill="#aebbc1" font-family="monospace" font-size="11" letter-spacing="3">VO1DFULL / THE COMMIT STREAM</text>',
      '<text x="1158" y="34" text-anchor="end" fill="#75858d" font-family="monospace" font-size="10">CODE IN MOTION</text>']

    # Very subtle vertical month guides.
    for i, x in enumerate(xvals):
        svg.append(f'<path d="M{x:.1f} 62 V344" stroke="#53616a" stroke-opacity=".12" stroke-dasharray="2 8"/>')

    for idx, row in enumerate(rows):
        counts = row["counts"]
        color = PALETTE[idx % len(PALETTE)]
        lane = first_y + idx*lane_gap
        peak = max(counts) if counts else 0
        # Per-stream amplitude keeps quiet repos visible without flattening active ones.
        amp = 28 + 48 * (math.sqrt(peak) / math.sqrt(max_repo))
        smooth_counts = []
        for i, v in enumerate(counts):
            prev = counts[max(0, i-1)]
            nxt = counts[min(MONTHS-1, i+1)]
            smooth_counts.append((prev + 2*v + nxt)/4)
        center = []
        local_widths = []
        for i, v in enumerate(smooth_counts):
            activity_level = (math.sqrt(v)/math.sqrt(max_repo)) if max_repo else 0
            wave = (math.sin(i*0.72 + idx*0.91)*23
                    + math.sin(i*1.43 + idx*0.37)*13
                    + math.cos(i*0.39 + idx*0.63)*9
                    + math.sin(i*0.31 + idx*1.7)*7)
            pulse = activity_level * amp
            center.append((xvals[i], lane + wave - pulse*0.72))
            local_widths.append(4 + activity_level*31 + abs(math.sin(i*.63 + idx))*5)
        # Contours fan out around busy months and gather back together in quiet stretches.
        levels = [-1.0,-.82,-.64,-.46,-.28,-.10,.10,.28,.46,.64,.82,1.0]
        for j, level in enumerate(levels):
            pts = []
            for i,(x,y) in enumerate(center):
                wobble = math.sin(i*.9 + idx*.7 + j*.35)*2.4 + math.cos(i*.42 + j*.3)*1.2
                pts.append((x, y + level*local_widths[i] + wobble))
            path = catmull(pts)
            opacity = .18 if abs(level) > .5 else (.30 if level else .76)
            width = 1.0 if level else 1.55
            svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{width}"/>')
        # A translucent ribbon core, narrow in quiet periods and wide around commit bursts.
        upper = [(x, y-local_widths[k]*.24) for k,(x,y) in enumerate(center)]
        lower = [(x, y+local_widths[k]*.24) for k,(x,y) in reversed(list(enumerate(center)))]
        body = catmull(upper) + " " + " ".join(f"L{x:.1f},{y:.1f}" for x,y in lower) + " Z"
        svg.append(f'<path d="{body}" fill="{color}" fill-opacity=".075" stroke="none"/>')

        # Place repository label near its strongest activity, avoiding the edge labels.
        peak_i = max(range(MONTHS), key=lambda i: counts[i]) if counts else 5
        label_i = min(10, max(1, peak_i))
        lx, ly = center[label_i]
        label = escape(row["name"][:24])
        svg.append(f'<text x="{lx:.1f}" y="{ly-local_widths[label_i]*.24-9:.1f}" text-anchor="middle" fill="#c0cbd0" font-family="monospace" font-size="10" opacity=".94">{label}</text>')

        # A few glowing rose "commit pulses" on active months.
        active = [i for i,v in enumerate(counts) if v > 0]
        if active:
            chosen = sorted(active, key=lambda i: counts[i], reverse=True)[:2]
            for k, i in enumerate(chosen):
                x,y = center[i]
                rx = 12 + min(16, counts[i]*1.3)
                ry = 4 + min(4, counts[i]*.35)
                svg.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx+7:.1f}" ry="{ry+5:.1f}" fill="#d88da9" opacity=".24" filter="url(#glow)"/>')
                svg.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#d98eaa" opacity=".88"/>')
                svg.append(f'<path d="M{x-rx-9:.1f},{y+1:.1f} Q{x-rx-2:.1f},{y-ry-2:.1f} {x-2:.1f},{y-1:.1f}" fill="none" stroke="#f0b4c8" stroke-opacity=".7" stroke-width="1.2"/>')

    # Timeline and footer.
    svg.append('<path d="M42 355 H1158" stroke="#64727a" stroke-opacity=".45"/>')
    month_names = []
    cursor = start.date().replace(day=1)
    for _ in range(MONTHS):
        month_names.append(cursor.strftime("%b"))
        cursor = (cursor.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    for i, (x, month) in enumerate(zip(xvals, month_names)):
        svg.append(f'<text x="{x:.1f}" y="379" text-anchor="middle" fill="#81919a" font-family="monospace" font-size="10">{month}</text>')
    svg.append(f'<text x="42" y="407" fill="#a7b4ba" font-family="monospace" font-size="10">{escape(username)} · 12 months · {total_commits:,} commits across {len(rows)} repositories</text>')
    svg.append('<text x="1158" y="407" text-anchor="end" fill="#6f7f87" font-family="monospace" font-size="9">UPDATED AUTOMATICALLY</text>')
    svg.append("</svg>")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text("\n".join(svg), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--username", default=os.getenv("GITHUB_REPOSITORY_OWNER", "vo1dfull"))
    parser.add_argument("--output", default="dist/commit-river.svg")
    args = parser.parse_args()
    if args.demo:
        rows, start, end = demo_data()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("GH_TOKEN is required outside demo mode.")
        rows, start, end = collect(args.username, token)
    render(rows, args.username, start, end, args.output)
    print(f"Generated {args.output}")

if __name__ == "__main__":
    main()
