#!/usr/bin/env python3
"""Generate a compact SVG streamgraph from the account's last-year commit contributions."""
import json
import os
import urllib.request
import datetime as dt
import calendar
import math
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

TOKEN = os.environ["GH_TOKEN"]
OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "vo1dfull")
END = dt.datetime.now(dt.timezone.utc)
START = END - dt.timedelta(days=365)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 30) {
        repository { name }
        contributions(first: 100) {
          nodes { occurredAt }
        }
      }
    }
  }
}
"""
payload = {
    "query": query,
    "variables": {
        "login": OWNER,
        "from": START.isoformat(),
        "to": END.isoformat()
    }
}
req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "vo1dfull-commit-river"
    }
)
with urllib.request.urlopen(req, timeout=30) as response:
    result = json.load(response)

if result.get("errors"):
    raise RuntimeError(result["errors"])

months = []
cursor = dt.date(START.year, START.month, 1)
while cursor <= END.date().replace(day=1):
    months.append(cursor.strftime("%b"))
    cursor = (cursor.replace(day=28) + dt.timedelta(days=4)).replace(day=1)

rows = []
repos = result["data"]["user"]["contributionsCollection"]["commitContributionsByRepository"]
for item in repos:
    name = item["repository"]["name"]
    counts = [0] * len(months)
    for node in item["contributions"]["nodes"]:
        when = dt.datetime.fromisoformat(node["occurredAt"].replace("Z", "+00:00"))
        index = (when.year - START.year) * 12 + when.month - START.month
        if 0 <= index < len(counts):
            counts[index] += 1
    if sum(counts):
        rows.append((name, counts))

# Keep the display legible: top 8 repositories, with remaining activity grouped.
rows.sort(key=lambda x: sum(x[1]), reverse=True)
if len(rows) > 8:
    rest = [0] * len(months)
    for _, counts in rows[8:]:
        rest = [a + b for a, b in zip(rest, counts)]
    rows = rows[:8] + [("other activity", rest)]
if not rows:
    rows = [("no public commit activity yet", [0] * len(months))]

W, H = 1040, 340
left, right = 52, 1018
top, bottom = 36, 270
plot_h = bottom - top
max_total = max(1, max(sum(row[1][i] for row in rows) for i in range(len(months))))
palette = ["#a9bac4", "#718895", "#a65a61", "#c0c8cc", "#647780", "#8c6d72", "#d0d5d7", "#596c76", "#9b777c"]

# Smooth stacked bands using quadratic curves between monthly sample points.
def x_at(i):
    return left + (right-left) * i / max(1, len(months)-1)

totals = [sum(row[1][i] for row in rows) for i in range(len(months))]
scale = plot_h / max(1, max_total) * 0.88
baseline = top + plot_h * 0.58
lower = [baseline - (totals[i] * scale / 2) for i in range(len(months))]
svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
    '<rect width="100%" height="100%" fill="#171c20"/>',
    '<text x="52" y="22" fill="#d9e0e4" font-family="monospace" font-size="11" letter-spacing="2">VO1DFULL / REPOSITORY ACTIVITY</text>',
    '<line x1="52" y1="286" x2="1018" y2="286" stroke="#4b565d" stroke-width="1"/>'
]
for i, (name, counts) in enumerate(rows):
    color = palette[i % len(palette)]
    heights = [counts[j] * scale for j in range(len(months))]
    center_offset = sum((rows[k][1][j] * scale) for k in range(i) for j in [0]) if False else 0
    # Center the total stack around the baseline for each month.
    lower_band = []
    upper_band = []
    for j in range(len(months)):
        total_height = totals[j] * scale
        prior = sum(rows[k][1][j] for k in range(i)) * scale
        lo = baseline - total_height/2 + prior
        hi = lo + heights[j]
        lower_band.append((x_at(j), lo))
        upper_band.append((x_at(j), hi))
    points = upper_band + list(reversed(lower_band))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x,y in points) + " Z"
    svg.append(f'<path d="{d}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.65" stroke-width="1.2"/>')
    peak = max(range(len(counts)), key=lambda j: counts[j])
    if counts[peak] > 0:
        ymid = (upper_band[peak][1] + lower_band[peak][1]) / 2
        label = escape(name[:25])
        svg.append(f'<text x="{x_at(peak):.1f}" y="{ymid-5:.1f}" text-anchor="middle" fill="#d8e0e4" font-family="monospace" font-size="10">{label}</text>')

for i, month in enumerate(months):
    if i % 2 == 0 or i == len(months)-1:
        svg.append(f'<text x="{x_at(i):.1f}" y="306" text-anchor="middle" fill="#89979f" font-family="monospace" font-size="10">{month}</text>')
svg.append(f'<text x="52" y="328" fill="#9eabb2" font-family="monospace" font-size="10">{OWNER} · last 12 months · commit contributions</text>')
svg.append("</svg>")

out = Path("dist")
out.mkdir(exist_ok=True)
(out / "commit-river.svg").write_text("\n".join(svg), encoding="utf-8")
print(f"Generated river for {len(rows)} repository streams.")
