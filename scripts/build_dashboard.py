#!/usr/bin/env python3
"""
SYNTHETICMIND // LAB OS — dashboard generator.

Pulls REAL data from the GitHub GraphQL API and writes one SVG per dashboard row
into assets/generated/. Standard library only (no pip installs).

    GH_TOKEN=... python3 scripts/build_dashboard.py            # live data (used by the Action)
    python3 scripts/build_dashboard.py --mock --out /tmp/prev   # offline layout preview ONLY (fake numbers)
"""
import argparse, base64, datetime as dt, html, json, os, sys, urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "src"
CFG = json.loads((ROOT / "config.json").read_text())

BG, PANEL = "#050b16", "#070f1e"
CYAN, BLUE, PURPLE, GREEN, GOLD, PINK = "#22d3ee", "#38bdf8", "#a855f7", "#22c55e", "#f59e0b", "#ec4899"
TXT, DIM, WHITE = "#9fb3c8", "#5b7089", "#ffffff"
MONO = "'JetBrains Mono','Fira Code',SFMono-Regular,Consolas,'Courier New',monospace"
DISP = "Orbitron,Rajdhani,'Segoe UI',Arial,Helvetica,sans-serif"
W = 1536
esc = html.escape

# ───────────────────────── SVG helpers ─────────────────────────
def T(x, y, s, size=16, fill=TXT, weight=400, ls=0, anchor="start", font=None, extra=""):
    f = f' font-family="{font}"' if font else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{l}{f} {extra}>{esc(str(s))}</text>')

DEFS = f'''<defs>
<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#040911"/><stop offset="1" stop-color="#07101f"/></linearGradient>
<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{CYAN}" stroke-opacity=".035"/></pattern>
</defs>'''

def svg(h, body, extra_defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {W} {h}" width="{W}" height="{h}" font-family="{MONO}">'
            + DEFS.replace("</defs>", extra_defs + "</defs>")
            + f'<rect width="{W}" height="{h}" fill="url(#bg)"/><rect width="{W}" height="{h}" fill="url(#grid)"/>'
            + body + "</svg>")

def panel(x, y, w, h, c=CYAN, title=None):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{PANEL}" stroke="{c}" stroke-opacity=".38" stroke-width="1.2"/>'
         f'<path d="M{x+w-28} {y+1} H{x+w-1} V{y+28}" fill="none" stroke="{c}" stroke-width="2" filter="url(#glow)"/>'
         f'<path d="M{x+1} {y+h-28} V{y+h-1} H{x+28}" fill="none" stroke="{c}" stroke-width="2" filter="url(#glow)"/>')
    if title:
        s += T(x + 22, y + 34, "> " + title, 15, WHITE, ls=2)
        s += f'<line x1="{x+22}" y1="{y+46}" x2="{x+w-22}" y2="{y+46}" stroke="{c}" stroke-opacity=".18"/>'
    return s

def typed(x, y, s, size, fill, begin, dur, cid):
    wpx = round(len(s) * size * 0.6)
    tl = f'textLength="{wpx}" lengthAdjust="spacingAndGlyphs"'
    return (f'<clipPath id="{cid}"><rect x="{x}" y="{y-size}" height="{size+6}" width="0">'
            f'<animate attributeName="width" values="0;{wpx};{wpx};0" keyTimes="0;0.3;0.92;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></rect></clipPath>'
            f'<g clip-path="url(#{cid})">{T(x, y, s, size, fill, extra=tl)}</g>')

def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()

def fmt(n):
    return f"{int(n):,}"

# ───────────────────────── Data ─────────────────────────
QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!,$from30:DateTime!){
  user(login:$login){
    followers{ totalCount }
    repositories(ownerAffiliations:OWNER, privacy:PUBLIC, isFork:false, first:100, orderBy:{field:PUSHED_AT,direction:DESC}){
      totalCount
      nodes{ name stargazerCount pushedAt primaryLanguage{ name } }
    }
    year: contributionsCollection(from:$from,to:$to){
      totalCommitContributions
      contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date } } }
    }
    recent: contributionsCollection(from:$from30,to:$to){
      commitContributionsByRepository(maxRepositories:10){
        repository{ name isPrivate } contributions{ totalCount }
      }
    }
  }
}"""

def fetch_live(user, token):
    now = dt.datetime.now(dt.timezone.utc)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps({"query": QUERY, "variables": {
        "login": user, "from": iso(now - dt.timedelta(days=364)), "to": iso(now),
        "from30": iso(now - dt.timedelta(days=30))}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "lab-os-dashboard"})
    with urllib.request.urlopen(req, timeout=40) as r:
        res = json.load(r)
    if res.get("errors") or not (res.get("data") or {}).get("user"):
        sys.exit(f"GitHub API error: {res.get('errors')}")
    u = res["data"]["user"]
    repos = u["repositories"]["nodes"]
    weeks = [[d["contributionCount"] for d in w["contributionDays"]] for w in u["year"]["contributionCalendar"]["weeks"]]
    dates = [d["date"] for w in u["year"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    recent = [(x["repository"]["name"], x["contributions"]["totalCount"])
              for x in u["recent"]["commitContributionsByRepository"] if not x["repository"]["isPrivate"]]
    recent.sort(key=lambda t: -t[1])
    return dict(
        repos=u["repositories"]["totalCount"], stars=sum(r["stargazerCount"] for r in repos),
        followers=u["followers"]["totalCount"], commits=u["year"]["totalCommitContributions"],
        contributions=u["year"]["contributionCalendar"]["totalContributions"],
        weeks=weeks, first=dates[0] if dates else "", last=dates[-1] if dates else "",
        recent=recent[:5], recent_pushed=[(r["name"], r["pushedAt"][:10]) for r in repos[:5]],
        langs=[l for l, _ in Counter(r["primaryLanguage"]["name"] for r in repos if r["primaryLanguage"]).most_common(8)],
        now=now)

def fetch_mock():  # layout preview only — NEVER commit output produced with this
    import random
    random.seed(4)
    now = dt.datetime.now(dt.timezone.utc)
    weeks = [[random.choice([0, 0, 1, 2, 4, 7, 11]) for _ in range(7)] for _ in range(53)]
    return dict(repos=12, stars=56, followers=24, commits=428, contributions=sum(map(sum, weeks)), weeks=weeks,
                first="2025-09-28", last="2026-09-27", recent=[("repo-one", 40), ("repo-two", 30), ("repo-three", 22), ("repo-four", 14), ("repo-five", 6)],
                recent_pushed=[], langs=["Python", "JavaScript", "TypeScript", "HTML"], now=now)

# ───────────────────────── Icons ─────────────────────────
LANG_ICON = {"Python": "py", "JavaScript": "js", "TypeScript": "ts", "HTML": "html", "CSS": "css", "Shell": "bash",
             "Rust": "rust", "Go": "go", "Solidity": "solidity", "Java": "java", "C++": "cpp", "C": "c", "PHP": "php",
             "Ruby": "ruby", "Vue": "vue", "Dart": "dart", "Kotlin": "kotlin", "Swift": "swift", "Jupyter Notebook": "py"}

def skill_icon(icon_id):
    try:
        req = urllib.request.Request(f"https://skillicons.dev/icons?i={icon_id}&theme=dark", headers={"User-Agent": "lab-os-dashboard"})
        data = urllib.request.urlopen(req, timeout=20).read()
        if b"<svg" in data:
            return "data:image/svg+xml;base64," + base64.b64encode(data).decode()
    except Exception as e:
        print(f"  icon {icon_id}: fetch failed ({e})", file=sys.stderr)
    return None

def glyph(kind, x, y, c):
    g = f'<g transform="translate({x},{y})" fill="none" stroke="{c}" stroke-width="2.2" filter="url(#glow)">'
    if kind == "brain":
        g += ('<path d="M30 6C18 2 8 12 12 22C4 26 4 40 14 44C16 54 30 56 30 50C30 56 44 54 46 44C56 40 56 26 48 22C52 12 42 2 30 6Z"/>'
              '<path d="M30 6V50M30 20L18 26M30 30L42 24M30 40L20 36"/>')
    elif kind == "cap":
        g += '<polygon points="30,8 58,22 30,36 2,22"/><path d="M14 30V42C22 51 38 51 46 42V30M58 22V38"/>'
    elif kind == "sol":
        g += (f'<polygon points="12,8 56,8 48,20 4,20" fill="#2dd4bf" fill-opacity=".85" stroke="none"/>'
              f'<polygon points="4,24 48,24 56,36 12,36" fill="#60a5fa" fill-opacity=".85" stroke="none"/>'
              f'<polygon points="12,40 56,40 48,52 4,52" fill="{PURPLE}" fill-opacity=".9" stroke="none"/>')
    elif kind == "gear":
        g += '<circle cx="30" cy="30" r="22" stroke-width="8" stroke-dasharray="7 6.8"/><circle cx="30" cy="30" r="16"/><circle cx="30" cy="30" r="7"/>'
    return g + "</g>"

# ───────────────────────── Rows ─────────────────────────
def row_header(d):
    b = ""
    cx, cy = 70, 68
    pts = [(cx-18, cy-14), (cx+2, cy-26), (cx+22, cy-10), (cx+14, cy+14), (cx-8, cy+22), (cx-24, cy+6)]
    b += f'<g filter="url(#glow)" stroke="{CYAN}" fill="none" stroke-width="2"><circle cx="{cx}" cy="{cy}" r="40" stroke-opacity=".9"/>'
    for i, p in enumerate(pts):
        n = pts[(i+1) % len(pts)]
        b += f'<line x1="{p[0]}" y1="{p[1]}" x2="{cx}" y2="{cy}"/><line x1="{p[0]}" y1="{p[1]}" x2="{n[0]}" y2="{n[1]}"/>'
    b += "".join(f'<circle cx="{p[0]}" cy="{p[1]}" r="3.6" fill="{CYAN}"/>' for p in pts) + f'<circle cx="{cx}" cy="{cy}" r="5" fill="{CYAN}"/></g>'
    b += T(128, 74, "SYNTHETICMIND", 52, WHITE, 700, font=DISP, extra='textLength="440" lengthAdjust="spacingAndGlyphs"')
    b += T(585, 74, "// LAB OS", 38, CYAN, 700, font=DISP, extra='textLength="205" lengthAdjust="spacingAndGlyphs"')
    b += T(800, 74, "v1.0", 20, CYAN, 700, font=DISP)
    b += T(128, 108, "BUILD  ·  AUTOMATE  ·  EXPERIMENT  ·  LEARN  ·  SHARE", 16, CYAN, extra='textLength="620" lengthAdjust="spacing"')
    # sparkline = REAL contributions, last 42 days
    flat = [c for w in d["weeks"] for c in w][-42:]
    mx = max(flat) or 1
    pts_s = " ".join(f"{922 + i*(120/(len(flat)-1)):.1f},{108 - (c/mx)*62:.1f}" for i, c in enumerate(flat))
    b += panel(912, 22, 140, 100, CYAN)
    b += f'<polygon points="922,108 {pts_s} 1042,108" fill="{CYAN}" fill-opacity=".12"/><polyline points="{pts_s}" fill="none" stroke="{CYAN}" stroke-width="1.6" filter="url(#glow)"/>'
    # status panel
    b += panel(1066, 15, 310, 112, GREEN)
    b += f'<circle cx="1090" cy="38" r="5" fill="{GREEN}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>' + T(1104, 43, "SYSTEM: ONLINE", 14, "#86efac", ls=1)
    for i, (lab, vals, dur) in enumerate([("AI", "70;130;95", 4), ("LEARNING", "60;100;75", 5), ("ON-CHAIN", "90;140;110", 3.6), ("AUTOMATION", "50;120;85", 4.4)]):
        y = 66 + i * 19
        b += T(1086, y + 4, lab, 12, TXT) + f'<rect x="1196" y="{y-5}" width="150" height="8" fill="#0c2a2d"/>'
        b += f'<rect x="1196" y="{y-5}" width="90" height="8" fill="{CYAN}"><animate attributeName="width" values="{vals}" dur="{dur}s" repeatCount="indefinite"/></rect>'
    # sync panel — real timestamp of the last Action run
    b += panel(1390, 15, 131, 115, CYAN)
    n = d["now"]
    b += T(1404, 43, n.strftime("%Y.%m.%d"), 15, WHITE, ls=1) + T(1404, 63, n.strftime("%H:%M UTC"), 14, WHITE)
    b += T(1404, 88, "BUILDING", 12, CYAN, ls=1) + T(1404, 104, "IN PUBLIC", 12, CYAN, ls=1) + T(1404, 120, "GLOBALLY", 12, CYAN, ls=1)
    return svg(135, b)

def row_hero(d):
    lines = CFG["tagline_lines"]
    defs = ('<linearGradient id="fadeG" x1="0" x2="1"><stop offset="0" stop-color="#000"/><stop offset=".32" stop-color="#fff"/><stop offset="1" stop-color="#fff"/></linearGradient>'
            '<mask id="fadeL" maskUnits="userSpaceOnUse" x="215" y="8" width="342" height="334"><rect x="215" y="8" width="342" height="334" fill="url(#fadeG)"/></mask>'
            '<radialGradient id="fadeR"><stop offset=".62" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>'
            '<mask id="fadeGlobe" maskUnits="userSpaceOnUse" x="1098" y="14" width="244" height="250"><rect x="1098" y="14" width="244" height="250" fill="url(#fadeR)"/></mask>')
    b = panel(15, 5, 545, 340, CYAN)
    b += f'<image x="215" y="8" width="342" height="334" xlink:href="{b64(SRC/"portrait.jpg","image/jpeg")}" preserveAspectRatio="xMidYMid slice" mask="url(#fadeL)"/>'
    for i, s in enumerate(["IDEAS", "TO", "REAL", "WORLD", "SYSTEMS_"]):
        b += T(40, 45 + i * 20, s, 16, WHITE, ls=3)
    b += f'<rect x="40" y="140" width="30" height="4" fill="{CYAN}" filter="url(#glow)"/>'
    for i, s in enumerate(["AI", "LEARNING", "ON-CHAIN", "AUTOMATION"]):
        b += T(40, 178 + i * 20, s, 16, WHITE, ls=3)
    b += f'<rect x="40" y="272" width="30" height="4" fill="{CYAN}" filter="url(#glow)"/>'
    b += T(40, 312, "SYNTHETICMIND", 21, WHITE, 400, extra='font-style="italic"') + T(40, 330, "// BUILDING A MORE OPEN FUTURE", 11, TXT, ls=1)
    # identity
    b += panel(575, 5, 500, 340, CYAN, "SYSTEM.IDENTITY")
    b += T(598, 132, "SYNTHETIC", 50, WHITE, 700, font=DISP, extra='textLength="284" lengthAdjust="spacingAndGlyphs"')
    b += T(890, 132, "MIND", 50, CYAN, 700, font=DISP, extra='textLength="126" lengthAdjust="spacingAndGlyphs"')
    b += T(598, 176, "AI × LEARNING TECHNOLOGY × SOLANA × AUTOMATION", 16, WHITE, ls=1, extra='textLength="452" lengthAdjust="spacing"')
    for i, s in enumerate(lines[:3]):
        b += typed(598, 216 + i * 22, s, 14, TXT, i * 1.2, 11, f"ty{i}")
    x = 593
    for lab, c, w in [("BUILDING", GREEN, 104), ("EXPERIMENTAL", PURPLE, 122), ("OPEN SOURCE", CYAN, 116), ("IN PUBLIC", BLUE, 92)]:
        b += f'<rect x="{x}" y="288" width="{w}" height="36" rx="5" fill="{c}" fill-opacity=".1" stroke="{c}" stroke-opacity=".8"/>'
        b += T(x + w / 2, 311, lab, 12, WHITE, anchor="middle", ls=.5)
        x += w + 11
    # globe + network
    b += panel(1090, 5, 431, 340, CYAN)
    b += f'<image x="1098" y="14" width="244" height="250" xlink:href="{b64(SRC/"globe.jpg","image/jpeg")}" mask="url(#fadeGlobe)"/>'
    b += panel(1350, 14, 164, 144, CYAN)
    for i, s in enumerate(["AI SYSTEMS", "LEARNING TECH", "SOLANA / PUMP.FUN", "AUTOMATION", "OPEN SOURCE"]):
        b += T(1368, 44 + i * 25, "> " + s, 12, WHITE)
    b += f'<image x="1350" y="168" width="164" height="96" xlink:href="{b64(SRC/"worldmap.jpg","image/jpeg")}"/>'
    b += T(1107, 296, "GLOBAL REACH", 13, CYAN, ls=1) + f'<line x1="1235" y1="292" x2="1500" y2="292" stroke="{CYAN}" stroke-opacity=".3"/>'
    b += f'<circle cx="1235" cy="292" r="4" fill="{CYAN}" filter="url(#glow)"><animate attributeName="cx" values="1235;1500;1235" dur="6s" repeatCount="indefinite"/></circle>'
    b += f'<line x1="1107" y1="312" x2="1500" y2="312" stroke="{CYAN}" stroke-opacity=".18"/>'
    b += T(1107, 334, "IDEA → BUILD → TEST → SHARE → IMPACT", 13, TXT, extra='textLength="393" lengthAdjust="spacing"')
    return svg(350, b, defs)

def row_pillars(d):
    cards = [("AI SYSTEMS", CYAN, "brain", ["LLM TOOLS", "RAG SYSTEMS", "AI AGENTS", "CREATOR TOOLS"]),
             ("LEARNING TECH", PURPLE, "cap", ["COURSE BUILDERS", "STORYBOARD SYSTEMS", "INSTRUCTIONAL DESIGN", "LEARNING WORKFLOWS"]),
             ("SOLANA / ON-CHAIN", GREEN, "sol", ["PUMP.FUN TOOLS", "TOKEN INTELLIGENCE", "MONITORING SYSTEMS", "TRADING INFRASTRUCTURE"]),
             ("AUTOMATION", GOLD, "gear", ["APIS & BOTS", "WORKFLOW AUTOMATION", "DATA UTILITIES", "DEVELOPER TOOLS"])]
    b = ""
    for i, (t, c, g, items) in enumerate(cards):
        x = 15 + i * 381
        b += panel(x, 5, 361, 152, c)
        b += glyph(g, x + 22, 40, c) + T(x + 100, 46, t, 19, c, 700, ls=1.5) + T(x + 318, 42, f"0{i+1}", 14, c, extra='fill-opacity=".45"')
        for j, s in enumerate(items):
            b += T(x + 100, 76 + j * 23, "▸ " + s, 14, TXT)
        b += f'<circle cx="{x+322}" cy="{112}" r="20" fill="none" stroke="{c}" stroke-width="1.6" filter="url(#glow)"/><path d="M{x+314} 112H{x+330}M{x+324} 105L{x+331} 112L{x+324} 119" fill="none" stroke="{c}" stroke-width="2"/>'
    return svg(162, b)

HEAT = ["#0b1526", "#3a1f7a", "#6d3fe0", "#2a8fe8", CYAN]

def row_telemetry(d):
    b = panel(15, 5, 540, 165, CYAN, "GITHUB TELEMETRY")
    stats = [("REPOSITORIES", d["repos"], "repo"), ("COMMITS · 12MO", d["commits"], "commit"), ("STARS", d["stars"], "star"), ("FOLLOWERS", d["followers"], "user")]
    for i, (lab, val, k) in enumerate(stats):
        x = 40 + i * 128
        ic = f'<g transform="translate({x},62)" fill="none" stroke="{PURPLE}" stroke-width="1.8">'
        ic += {"repo": '<rect x="0" y="4" width="26" height="20" rx="3"/><path d="M0 8H10L13 4"/>', "commit": '<circle cx="13" cy="14" r="7"/><path d="M0 14H6M20 14H26"/>',
               "star": '<polygon points="13,2 16.5,10 25,11 18.5,17 20.5,26 13,21.5 5.5,26 7.5,17 1,11 9.5,10"/>', "user": '<circle cx="10" cy="9" r="5"/><path d="M1 24C1 16 19 16 19 24"/><circle cx="21" cy="11" r="4"/>'}[k] + "</g>"
        b += ic + T(x, 118, fmt(val), 30, WHITE, 700) + T(x, 142, lab, 12, TXT, ls=.5)
        if i: b += f'<line x1="{x-16}" y1="62" x2="{x-16}" y2="148" stroke="{CYAN}" stroke-opacity=".15"/>'
    b += T(40, 162, "PUBLIC DATA · LIVE FROM GITHUB API", 10, DIM, ls=1)
    # heatmap
    b += panel(570, 5, 600, 165, CYAN, "CONTRIBUTION ACTIVITY")
    b += T(1150, 39, f"{fmt(d['contributions'])} CONTRIBUTIONS · 12 MO", 12, CYAN, anchor="end", ls=1)
    allc = [c for w in d["weeks"] for c in w]
    mx = max(allc) or 1
    def lvl(c):
        return 0 if c == 0 else 1 if c <= mx * .25 else 2 if c <= mx * .5 else 3 if c <= mx * .75 else 4
    for wi, w in enumerate(d["weeks"]):
        for di, c in enumerate(w):
            b += f'<rect x="{592 + wi*10.4:.1f}" y="{62 + di*11.2:.1f}" width="8.6" height="8.6" rx="1.5" fill="{HEAT[lvl(c)]}"/>'
    b += T(592, 158, d["first"][:4], 12, DIM) + T(1148, 158, d["last"][:4], 12, DIM, anchor="end")
    # currently building = REAL commits per public repo, last 30 days
    b += panel(1185, 5, 336, 165, CYAN, "CURRENTLY BUILDING")
    rows = d["recent"]
    if rows:
        top = max(c for _, c in rows) or 1
        cols = [GREEN, GREEN, GOLD, PINK, PURPLE]
        for i, (name, c) in enumerate(rows):
            y = 70 + i * 19
            nm = name if len(name) <= 22 else name[:21] + "…"
            b += f'<circle cx="1212" cy="{y-4}" r="4" fill="{cols[i]}"/>' + T(1226, y, nm, 13, WHITE)
            b += f'<rect x="1440" y="{y-9}" width="56" height="7" fill="#0f2233"/><rect x="1440" y="{y-9}" width="{max(4, 56*c/top):.0f}" height="7" fill="{CYAN}"/>'
        b += T(1207, 165, "BAR = COMMITS · LAST 30 DAYS", 10, DIM, ls=1)
    else:
        b += T(1207, 90, "NO PUBLIC COMMITS IN LAST 30 DAYS", 12, TXT)
        for i, (name, dte) in enumerate(d["recent_pushed"][:4]):
            b += T(1207, 116 + i * 20, f"{name[:20]}  {dte}", 12, WHITE)
    return svg(175, b)

def row_snake_header(d):
    b = panel(15, 4, 1506, 44, CYAN)
    b += T(37, 32, "> CONTRIBUTION SNAKE", 15, WHITE, ls=2) + T(1499, 32, "LIVE · REGENERATED BY GITHUB ACTIONS", 12, CYAN, anchor="end", ls=1)
    return svg(52, b)

def row_stack(d):
    ids = []
    for l in d["langs"]:
        i = LANG_ICON.get(l)
        if i and i not in ids: ids.append(i)
    for i in CFG.get("stack_extra", []):
        if i not in ids: ids.append(i)
    ids = ids[: CFG.get("max_icons", 13)]
    b = panel(15, 5, 1095, 150, CYAN, "TECH STACK")
    for k, i in enumerate(ids):
        x = 42 + k * 78
        data = None if os.environ.get("NO_ICON_FETCH") else skill_icon(i)
        if data:
            b += f'<image x="{x}" y="66" width="60" height="60" xlink:href="{data}"/>'
        else:
            b += f'<rect x="{x}" y="66" width="60" height="60" rx="12" fill="#0f1b2d" stroke="{CYAN}" stroke-opacity=".4"/>' + T(x + 30, 102, i.upper()[:4], 13, WHITE, anchor="middle")
    b += panel(1125, 5, 396, 150, CYAN, "SYSTEM LOG")
    n = d["now"]
    ts = lambda s: (n + dt.timedelta(seconds=s)).strftime("%H:%M:%S")
    logs = [(f"[{ts(0)}] Initializing SyntheticMind...", None), (f"[{ts(1)}] Loading repositories ({fmt(d['repos'])})...", "OK"),
            (f"[{ts(2)}] Loading contributions ({fmt(d['contributions'])})...", "OK"), (f"[{ts(3)}] Loading followers ({fmt(d['followers'])})...", "OK"), (f"[{ts(4)}] System Ready.", None)]
    for i, (s, ok) in enumerate(logs):
        y = 72 + i * 17
        t = T(1147, y, s, 11, TXT if i < 4 else CYAN) + (T(1500, y, ok, 11, GREEN, anchor="end") if ok else "")
        b += f'<g opacity="0"><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.02;.9;1" dur="9s" begin="{i*.7}s" repeatCount="indefinite"/>{t}</g>'
    return svg(160, b)

def row_footer(d):
    b = f'<line x1="15" y1="4" x2="1521" y2="4" stroke="{CYAN}" stroke-opacity=".3"/>'
    b += T(30, 28, "SYNTHETICMIND // LAB OS", 13, WHITE, ls=1) + T(262, 28, "v1.0.0", 13, CYAN)
    b += f'<rect x="330" y="21" width="150" height="5" fill="#0f2233"/><rect x="330" y="21" width="60" height="5" fill="{CYAN}"><animate attributeName="width" values="30;150;30" dur="7s" repeatCount="indefinite"/></rect>'
    b += T(768, 28, "AI × LEARNING TECHNOLOGY × SOLANA × AUTOMATION", 12, TXT, anchor="middle", ls=2)
    b += T(1490, 28, "ALWAYS BUILDING  //  LEARN IN PUBLIC", 12, TXT, anchor="end", ls=1)
    return svg(40, b)

# ───────────────────────── Main ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fake data, layout preview only")
    ap.add_argument("--out", default=str(ROOT / "assets" / "generated"))
    a = ap.parse_args()
    if a.mock:
        d = fetch_mock()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token: sys.exit("GH_TOKEN is not set")
        d = fetch_live(CFG["user"], token)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for name, fn in [("header", row_header), ("hero", row_hero), ("pillars", row_pillars), ("telemetry", row_telemetry),
                     ("snake-header", row_snake_header), ("stack", row_stack), ("footer", row_footer)]:
        (out / f"{name}.svg").write_text(fn(d), encoding="utf-8")
        print("wrote", out / f"{name}.svg")

if __name__ == "__main__":
    main()
