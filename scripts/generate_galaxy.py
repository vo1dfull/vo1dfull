#!/usr/bin/env python3
"""Render an animated, data-backed repository galaxy for vo1dfull's profile."""
import argparse, datetime as dt, json, math, os, random, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageOps

W, H = 900, 500
FRAMES, DURATION = 32, 200
BG = (10, 12, 16)
PINK = (211, 151, 173)
PALE = (205, 211, 216)
MUTED = (116, 128, 139)

FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
def font(size, bold=False):
    name = 'DejaVuSansMono-Bold.ttf' if bold else 'DejaVuSansMono.ttf'
    path = FONT_DIR/name
    try: return ImageFont.truetype(str(path), size)
    except OSError: return ImageFont.load_default()

F_TITLE = font(17, True); F_LABEL = font(13, True); F_SMALL = font(10); F_TINY = font(9)

def api_get(url, token):
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vo1dfull-repository-galaxy'
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def collect_data(username, token):
    now = dt.datetime.now(dt.timezone.utc)
    start_month = (now.year * 12 + now.month - 1) - 11
    sy, sm0 = divmod(start_month, 12)
    start = dt.datetime(sy, sm0 + 1, 1, tzinfo=dt.timezone.utc)
    since = start.isoformat().replace('+00:00', 'Z')
    repos = api_get(f'https://api.github.com/users/{urllib.parse.quote(username)}/repos?type=owner&per_page=100&sort=pushed', token)
    repos = [r for r in repos if not r.get('fork') and not r.get('archived')]
    by_name = {r['name'].lower(): r for r in repos}

    # Keep the two featured worlds visible. If not created yet, label them as works in progress.
    focus = [
        ('rust-systems-lab', 'RUST / SYSTEMS'),
        ('security-lab', 'CYBERSECURITY / NETWORKS')
    ]
    selected = []
    used = set()
    for name, subtitle in focus:
        repo = by_name.get(name.lower())
        if repo:
            selected.append((repo, subtitle, False)); used.add(repo['full_name'])
        else:
            selected.append(({'name': name, 'full_name': f'{username}/{name}', 'html_url': f'https://github.com/{username}/{name}'}, subtitle, True))

    result = []
    for repo, subtitle, planned in selected:
        monthly = [0] * 12
        if not planned:
            for page in range(1, 4):
                query = urllib.parse.urlencode({'author': username, 'since': since, 'per_page': 100, 'page': page})
                try:
                    commits = api_get(f"https://api.github.com/repos/{repo['full_name']}/commits?{query}", token)
                except Exception as exc:
                    print(f"Could not read {repo['full_name']}: {exc}")
                    break
                if not commits: break
                older_than_window = False
                for commit in commits:
                    raw = commit.get('commit', {}).get('author', {}).get('date')
                    if not raw: continue
                    date = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
                    if date < start:
                        older_than_window = True
                        continue
                    idx = (date.year - start.year) * 12 + date.month - start.month
                    if 0 <= idx < 12: monthly[idx] += 1
                if older_than_window or len(commits) < 100: break
        result.append({
            'name': repo['name'], 'subtitle': subtitle, 'url': repo['html_url'],
            'monthly': monthly, 'commits': sum(monthly), 'planned': planned
        })
    total = sum(r['commits'] for r in result)
    active = sum(1 for r in result if r['commits'] > 0)
    return {'repos': result, 'total_commits': total, 'active_repos': active, 'updated': now.strftime('%Y-%m-%d')}

def demo_data():
    rows = [
        {'name':'rust-systems-lab','subtitle':'RUST / SYSTEMS','url':'#','monthly':[0,1,2,1,3,5,2,4,3,7,4,6],'commits':38,'planned':False},
        {'name':'security-lab','subtitle':'CYBERSECURITY / NETWORKS','url':'#','monthly':[0,0,1,3,2,4,5,2,6,3,5,8],'commits':39,'planned':False},
    ]
    return {'repos':rows,'total_commits':77,'active_repos':2,'updated':'DEMO DATA'}

def rotated_ellipse(cx, cy, rx, ry, angle, steps=220):
    ca, sa = math.cos(angle), math.sin(angle)
    pts=[]
    for i in range(steps+1):
        t=2*math.pi*i/steps
        x=rx*math.cos(t); y=ry*math.sin(t)
        pts.append((cx+x*ca-y*sa, cy+x*sa+y*ca))
    return pts

def starfield(seed=21):
    rng=random.Random(seed)
    stars=[]
    for _ in range(105):
        stars.append((rng.randrange(W), rng.randrange(H), rng.choice([1,1,1,2]), rng.random()*math.tau, rng.uniform(.25,.9)))
    return stars

STARS=starfield()

def make_background(frame):
    # Generated cinematic galaxy artwork is the fixed canvas; only overlay details animate.
    artwork=Path(__file__).resolve().parents[1] / 'assets' / 'galaxy-background.png'
    if artwork.exists():
        source=Image.open(artwork).convert('RGB')
        im=ImageOps.fit(source,(W,H),method=Image.Resampling.LANCZOS,centering=(.5,.5)).convert('RGBA')
    else:
        im=Image.new('RGBA',(W,H),BG+(255,))
    shade=Image.new('RGBA',(W,H),(3,5,9,28))
    return Image.alpha_composite(im,shade)

def draw_galaxy(im, frame):
    # The backdrop carries the spiral; a restrained pulse gives its nucleus a little life.
    cx,cy=450,260
    pulse=.72+.28*math.sin(frame*math.tau/FRAMES)
    core=Image.new('RGBA',(W,H),(0,0,0,0)); cd=ImageDraw.Draw(core)
    cd.ellipse((cx-24,cy-13,cx+24,cy+13),fill=(228,164,190,int(72*pulse)))
    im.alpha_composite(core.filter(ImageFilter.GaussianBlur(17)))

def draw_frame(data, frame):
    im=make_background(frame)
    d=ImageDraw.Draw(im,'RGBA')
    # Tiny twinkling stars.
    for x,y,r,phase,base in STARS:
        tw=.5+.5*math.sin(frame*.31+phase)
        alpha=int(35+base*90*tw)
        color=(204,211,218,alpha) if tw>.35 else (183,135,157,alpha)
        d.ellipse((x-r,y-r,x+r,y+r),fill=color)

    draw_galaxy(im,frame)
    d=ImageDraw.Draw(im,'RGBA')
    cx,cy=450,260
    # Orbit geometry: delicate silver tracks with a slow shimmer dash.
    orbit_specs=[(245,126,-.13),(340,178,.10)]
    for idx,(rx,ry,rot) in enumerate(orbit_specs):
        pts=rotated_ellipse(cx,cy,rx,ry,rot,260)
        d.line(pts,fill=(165,174,183,42 if idx<2 else 24),width=1)
        # Orbit markers, very restrained.
        for mark in (0.12,2.18,4.12):
            t=mark+idx*.42
            x=cx+math.cos(t)*rx*math.cos(rot)-math.sin(t)*ry*math.sin(rot)
            y=cy+math.cos(t)*rx*math.sin(rot)+math.sin(t)*ry*math.cos(rot)
            d.ellipse((x-1.4,y-1.4,x+1.4,y+1.4),fill=(205,183,194,110))

    # Header and corner metadata.
    d.text((34,25),'// THE REPOSITORY GALAXY',font=F_TITLE,fill=(218,222,226,245))
    d.text((35,49),'projects, experiments and ideas orbiting a common core.',font=F_SMALL,fill=(132,143,153,235))
    d.text((865,25),'VO1DFULL / 01',font=F_TINY,fill=(124,135,145,210),anchor='ra')
    d.text((865,47),'02 WORLDS',font=F_SMALL,fill=(184,190,196,225),anchor='ra')
    d.text((865,64),f"{data['total_commits']} COMMITS / 12 MONTHS",font=F_TINY,fill=(128,139,149,220),anchor='ra')

    # Center label and crosshair.
    d.text((cx,cy-61),'vo1dfull',font=F_LABEL,fill=(240,226,233,255),anchor='mm')
    d.line((cx-14,cy-42,cx-14,cy-31),fill=(210,169,187,180),width=1)
    d.line((cx+14,cy-42,cx+14,cy-31),fill=(210,169,187,180),width=1)
    d.line((cx-14,cy-42,cx-5,cy-42),fill=(210,169,187,180),width=1)
    d.line((cx+5,cy-42,cx+14,cy-42),fill=(210,169,187,180),width=1)

    # Each project has its own world. Focus repos occupy inner orbits; satellites sit farther out.
    positions=[]
    base_angles=[math.pi, 0.0]
    for idx,repo in enumerate(data['repos'][:2]):
        rx,ry,rot=orbit_specs[idx]
        base=base_angles[idx]
        angle=base + .10*math.sin(frame*math.tau/FRAMES)
        ca,sa=math.cos(rot),math.sin(rot)
        ox=math.cos(angle)*rx; oy=math.sin(angle)*ry
        x=cx+ox*ca-oy*sa; y=cy+ox*sa+oy*ca
        positions.append((x,y,repo,idx))

    for x,y,repo,idx in positions:
        main=idx<2
        radius=12 if main else 8
        # Pink halo and satellite body.
        halo=Image.new('RGBA',(W,H),(0,0,0,0)); h=ImageDraw.Draw(halo)
        h.ellipse((x-radius-13,y-radius-13,x+radius+13,y+radius+13),fill=(211,145,174,68 if main else 38))
        halo=halo.filter(ImageFilter.GaussianBlur(13)); im.alpha_composite(halo)
        d=ImageDraw.Draw(im,'RGBA')
        d.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(170,179,188,235),outline=(231,190,207,230),width=1)
        d.ellipse((x-radius*.45,y-radius*.55,x+radius*.2,y+radius*.12),fill=(245,222,231,130))
        # Labels are placed outward from the center to reduce collisions.
        left=x<cx
        label=repo['name']
        sub=repo['subtitle'] + (' / IN ORBIT' if repo['planned'] else f" / {repo['commits']} COMMITS")
        tx=min(330,x+22) if left else max(570,x-22)
        anchor='la' if left else 'ra'
        ty=max(104,min(H-76,y-10))
        d.text((tx,ty),label,font=F_LABEL,fill=(225,220,225,250),anchor=anchor)
        d.text((tx,ty+18),sub,font=F_TINY,fill=(142,151,160,235),anchor=anchor)
        if repo['planned']:
            d.text((tx,ty+32),'BUILDING',font=F_TINY,fill=(204,153,174,225),anchor=anchor)

    # Small activity pulse bar at the foot: actual monthly commits, no fabricated graph.
    d=ImageDraw.Draw(im,'RGBA')
    d.text((35,447),'ACTIVITY / LAST 12 MONTHS',font=F_TINY,fill=(132,143,153,220))
    monthly=[sum(r['monthly'][i] for r in data['repos']) for i in range(12)]
    peak=max(monthly) if monthly else 1
    bx,by=35,470
    for i,val in enumerate(monthly):
        height=3 if peak==0 else 3+int(18*val/peak)
        x=bx+i*9
        d.rounded_rectangle((x,by-height,x+5,by),radius=1,fill=(204,145,169,110+int(100*val/peak) if peak else 110))
    d.text((865,470),f"UPDATED {data['updated']}",font=F_TINY,fill=(111,123,134,220),anchor='ra')
    # Fine frame border.
    d.rounded_rectangle((10,10,W-11,H-11),radius=10,outline=(94,105,116,95),width=1)
    return im.convert('RGB')

def render(data, output):
    frames=[]
    for i in range(FRAMES):
        frames.append(draw_frame(data,i).resize((720,400),Image.Resampling.LANCZOS).convert('P',palette=Image.Palette.ADAPTIVE,colors=96))
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(output,save_all=True,append_images=frames[1:],duration=DURATION,loop=0,optimize=True,disposal=2)
    print(f"Rendered {output} ({Path(output).stat().st_size} bytes)")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--username',default=os.getenv('GITHUB_REPOSITORY_OWNER','vo1dfull'))
    ap.add_argument('--output',default='dist/repository-galaxy.gif')
    ap.add_argument('--demo',action='store_true')
    args=ap.parse_args()
    if args.demo: data=demo_data()
    else:
        token=os.environ.get('GH_TOKEN')
        if not token: raise SystemExit('GH_TOKEN is required')
        data=collect_data(args.username,token)
    render(data,args.output)

if __name__=='__main__': main()
