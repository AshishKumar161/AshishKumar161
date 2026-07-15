import json
import math
import os
import random
import time
import urllib.request
from collections import deque
from datetime import date

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# =========================================================
# CYBER SNAKE GAME  -- Enhanced Edition v3
#
# FIX: GIF palette quantization was washing out colour
#      differences.  Each skin now uses bright, radically
#      distinct colours that survive 256-colour GIF export.
#      A full-body FLASH fires for 10 frames on every phase
#      transition so the colour change is unmissable.
# =========================================================

GITHUB_USER_NAME = os.environ.get("GITHUB_USER_NAME", "AshishKumar161")
LAST_WEEKS = 53

CELL          = 13
GAP           = 3
SIDE_W        = 88
PADDING_X     = 14
PADDING_Y     = 48
BOTTOM_PAD    = 40
MONTH_OFFSET  = 14

FRAMES_PER_CELL   = 4
FRAME_DURATION_MS = 45

INITIAL_SNAKE_LENGTH  = 14
GROW_PER_FOOD         = 4
MAX_GROW_FROM_ONE_DAY = 8
MAX_SNAKE_LENGTH      = 180

RANDOM_TARGET_CHANCE = 0.35
NEAR_TARGET_LIMIT    = 6
MAX_ATTEMPTS         = 800

# Skin changes at these food-eaten ratios
LEVEL_THRESHOLDS = [0.0, 0.20, 0.40, 0.60, 0.80]
LEVELUP_FLASH_FRAMES = 22   # banner duration
SKIN_FLASH_FRAMES    = 10   # full-body colour flash frames

# ── Colors ────────────────────────────────────────────────
BG           = (6,  10, 16)
PANEL_BG     = (9,  14, 20)
SIDE_BG      = (7,  12, 17)
HEADER_BG    = (8,  13, 21)
HUD_CYAN     = (0, 220, 230)
WHITE        = (255, 255, 255)
DIM          = ( 95, 112, 128)
BLACK        = (  0,   0,   0)
CYAN         = (  0, 220, 230)
PROG_BG      = ( 15,  21,  30)

LEVEL_COLORS = [
    (18, 24, 32),
    (14, 68, 41),
    (0, 109, 50),
    (38, 166, 65),
    (57, 211, 83),
]
LEVEL_HIGHLIGHT = [
    (26, 34, 44),
    (22, 95, 60),
    (12, 148, 70),
    (60, 200, 85),
    (90, 248, 110),
]
LEVEL_SHADOW = [
    (10, 14, 20),
    ( 8, 44, 28),
    ( 0, 72, 34),
    (22, 112, 44),
    (32, 148, 54),
]
GLOW_COLORS  = [None, (14,68,41), (0,150,65), (57,200,80), (100,255,120)]
EATEN_COLOR  = (8, 12, 18)
FLASH_COLOR  = (215, 255, 215)

# ── Snake Skins ───────────────────────────────────────────
# Each skin uses BRIGHT, VISUALLY DISTINCT colours that
# survive GIF 256-colour palette quantization.
#
# Keys: tail, body, inner  -- body gradient colours
#       head, head_inner   -- head polygon colours
#       glow_rgb           -- 3-tuple for glow (alpha added in code)
#       tongue, eye_fill   -- accent colours
#       hud_label          -- side-panel + border accent
#       flash_col          -- full-body flash colour on level-up
#       style              -- head shape
SNAKE_SKINS = [
    # Phase 0 — Cyber Green  (bright neon green)
    {
        "name":       "CYBER GREEN",
        "tail":       (0,   80,  30),
        "body":       (0,  200,  70),
        "inner":      (80, 255, 120),
        "head":       (160,  0, 255),
        "head_inner": (230, 140, 255),
        "glow_rgb":   (0, 255, 80),
        "tongue":     (255,  30, 110),
        "eye_fill":   (0, 255, 70),
        "eye_shine":  (200, 255, 200),
        "hud_label":  (0, 220, 80),
        "flash_col":  (120, 255, 160),
        "style":      "diamond",
    },
    # Phase 1 — Electric Blue  (vivid sky blue)
    {
        "name":       "ELECTRIC BLUE",
        "tail":       (0,   40, 160),
        "body":       (0,  140, 255),
        "inner":      (120, 210, 255),
        "head":       (0,  220, 255),
        "head_inner": (200, 245, 255),
        "glow_rgb":   (0, 180, 255),
        "tongue":     (0, 200, 255),
        "eye_fill":   (0, 230, 255),
        "eye_shine":  (210, 248, 255),
        "hud_label":  (0, 200, 255),
        "flash_col":  (100, 220, 255),
        "style":      "arrow",
    },
    # Phase 2 — Plasma Purple  (hot magenta-purple)
    {
        "name":       "PLASMA PURPLE",
        "tail":       (100,  0, 150),
        "body":       (200,  0, 255),
        "inner":      (240, 120, 255),
        "head":       (255,  0, 200),
        "head_inner": (255, 180, 240),
        "glow_rgb":   (220, 0, 255),
        "tongue":     (255, 80, 200),
        "eye_fill":   (255, 80, 220),
        "eye_shine":  (255, 210, 245),
        "hud_label":  (210, 80, 255),
        "flash_col":  (240, 100, 255),
        "style":      "cobra",
    },
    # Phase 3 — Fire Orange  (deep orange/red)
    {
        "name":       "FIRE ORANGE",
        "tail":       (160,  30,  0),
        "body":       (255, 100,  0),
        "inner":      (255, 200,  60),
        "head":       (255,  60,  0),
        "head_inner": (255, 220, 100),
        "glow_rgb":   (255, 120, 0),
        "tongue":     (255,  40,  0),
        "eye_fill":   (255, 180,  0),
        "eye_shine":  (255, 240, 160),
        "hud_label":  (255, 150,  0),
        "flash_col":  (255, 180,  60),
        "style":      "dragon",
    },
    # Phase 4 — Golden Elite  (rich gold)
    {
        "name":       "GOLDEN ELITE",
        "tail":       (140, 100,  0),
        "body":       (240, 190,  0),
        "inner":      (255, 240,  80),
        "head":       (255, 215,  0),
        "head_inner": (255, 252, 180),
        "glow_rgb":   (255, 220, 0),
        "tongue":     (255, 210,  0),
        "eye_fill":   (255, 240,  0),
        "eye_shine":  (255, 255, 220),
        "hud_label":  (255, 220,  0),
        "flash_col":  (255, 240, 100),
        "style":      "crown",
    },
]

LEVELUP_COLORS = [
    (80, 255, 120),
    (100, 220, 255),
    (240, 100, 255),
    (255, 180,  60),
    (255, 240, 100),
]


def _font(size):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

F_LG = _font(13)
F_MD = _font(11)
F_SM = _font(9)
F_XL = _font(18)


def fetch_contribution_calendar(username):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not found.")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date  contributionCount }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "User-Agent":    "cyber-snake-game-v3",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    user = data.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"User not found: {username}")
    return user["contributionsCollection"]["contributionCalendar"]


def count_to_level(count):
    if count <= 0:  return 0
    if count <= 2:  return 1
    if count <= 5:  return 2
    if count <= 10: return 3
    return 4


def build_grid(calendar):
    weeks = calendar["weeks"][-LAST_WEEKS:]
    cols, rows = len(weeks), 7
    counts, total, month_labels = {}, 0, {}
    for x, week in enumerate(weeks):
        for day in week["contributionDays"]:
            d     = date.fromisoformat(day["date"])
            y     = (d.weekday() + 1) % 7
            count = int(day["contributionCount"])
            counts[(x, y)] = count
            total += count
            if d.day <= 7 and x not in month_labels:
                month_labels[x] = d.strftime("%b")
    return cols, rows, counts, total, month_labels


def cell_rect(x, y, ox, oy):
    l = ox + x * (CELL + GAP)
    t = oy + y * (CELL + GAP)
    return [l, t, l + CELL, t + CELL]

def center_of_cell(x, y, ox, oy):
    r = cell_rect(x, y, ox, oy)
    return (r[0] + r[2]) / 2, (r[1] + r[3]) / 2


def _neighbors(cell, cols, rows):
    x, y = cell
    n = []
    if x > 0:      n.append((x-1, y))
    if x < cols-1: n.append((x+1, y))
    if y > 0:      n.append((x, y-1))
    if y < rows-1: n.append((x, y+1))
    random.shuffle(n)
    return n

def _manhattan(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def _bfs(start, goal, cols, rows, blocked=None):
    blocked = set(blocked or [])
    blocked.discard(start)
    blocked.discard(goal)
    q, parent = deque([start]), {start: None}
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for nxt in _neighbors(cur, cols, rows):
            if nxt not in parent and nxt not in blocked:
                parent[nxt] = cur
                q.append(nxt)
    if goal not in parent:
        return None
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path

def _choose_target(current, remaining):
    rem = list(remaining)
    if not rem:
        return None
    if random.random() < RANDOM_TARGET_CHANCE:
        return random.choice(rem)
    rem.sort(key=lambda c: _manhattan(current, c))
    return random.choice(rem[:min(NEAR_TARGET_LIMIT, len(rem))])


def build_path(cols, rows, counts):
    food_cells     = {cell for cell, c in counts.items() if c > 0}
    remaining_food = set(food_cells)
    start          = (0, rows // 2)
    full_path      = [start]
    snake_body     = deque([start])
    snake_body_set = {start}
    snake_length   = INITIAL_SNAKE_LENGTH
    if start in remaining_food:
        remaining_food.remove(start)
        snake_length += GROW_PER_FOOD + min(counts.get(start, 0), MAX_GROW_FROM_ONE_DAY)
    attempts = 0
    while remaining_food and attempts < MAX_ATTEMPTS:
        current = full_path[-1]
        target  = _choose_target(current, remaining_food)
        path = _bfs(current, target, cols, rows, blocked=snake_body_set)
        if path is None:
            path = _bfs(current, target, cols, rows, blocked=None)
        if path is None:
            for food in sorted(remaining_food, key=lambda c: _manhattan(current, c)):
                path = _bfs(current, food, cols, rows, blocked=None)
                if path:
                    target = food
                    break
        if path is None:
            break
        for next_cell in path[1:]:
            current = next_cell
            full_path.append(current)
            snake_body.append(current)
            snake_body_set.add(current)
            if current in remaining_food:
                remaining_food.remove(current)
                snake_length += GROW_PER_FOOD + min(counts.get(current, 0), MAX_GROW_FROM_ONE_DAY)
                snake_length  = min(snake_length, MAX_SNAKE_LENGTH)
            while len(snake_body) > snake_length:
                removed = snake_body.popleft()
                snake_body_set.discard(removed)
            if current == target:
                break
        attempts += 1
    return full_path, food_cells


def smooth_path(cell_path, ox, oy):
    if len(cell_path) == 1:
        return [center_of_cell(*cell_path[0], ox, oy)], [cell_path[0]]
    points, cell_at = [], []
    for i in range(len(cell_path) - 1):
        x1, y1 = center_of_cell(*cell_path[i],   ox, oy)
        x2, y2 = center_of_cell(*cell_path[i+1], ox, oy)
        for step in range(FRAMES_PER_CELL):
            t = step / FRAMES_PER_CELL
            t = t * t * (3 - 2 * t)
            points.append((x1 + (x2-x1)*t, y1 + (y2-y1)*t))
            cell_at.append(cell_path[i])
    points.append(center_of_cell(*cell_path[-1], ox, oy))
    cell_at.append(cell_path[-1])
    return points, cell_at


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))


def get_skin_phase(eaten, total_food):
    """Return 0-4 based on fraction of food eaten."""
    if total_food == 0:
        return 0
    ratio = eaten / total_food
    phase = 0
    for i, thresh in enumerate(LEVEL_THRESHOLDS):
        if ratio >= thresh:
            phase = i
    return phase


# ─────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────
def draw_frame(draw, width, height, skin):
    border = skin["hud_label"]
    draw.rounded_rectangle([2, 2, width-3, height-3],
                            radius=13, fill=PANEL_BG, outline=border, width=2)
    bk = 15
    for cx, cy in [(6,6),(width-7,6),(6,height-7),(width-7,height-7)]:
        sx = 1 if cx < width//2 else -1
        sy = 1 if cy < height//2 else -1
        draw.line([(cx,cy),(cx+sx*bk,cy)],     fill=HUD_CYAN, width=2)
        draw.line([(cx,cy),(cx,cy+sy*bk)],     fill=HUD_CYAN, width=2)


def draw_side_panel(draw, height, eaten, total_food, score, phase, skin):
    W  = SIDE_W
    cx = W // 2
    draw.rectangle([4, 4, W-2, height-4], fill=SIDE_BG)
    draw.line([(W-1, 4), (W-1, height-4)], fill=(0, 55, 28), width=1)

    ay      = 14
    eye_col = skin["eye_fill"]
    acc_col = skin["hud_label"]

    # Avatar ring
    draw.ellipse([cx-28, ay,   cx+28, ay+56], fill=(9,18,13), outline=acc_col, width=1)
    draw.ellipse([cx-25, ay+3, cx+25, ay+53], fill=(8,16,12),
                 outline=lerp(acc_col, BLACK, 0.5), width=1)
    draw.ellipse([cx-20, ay+4, cx+20, ay+37], fill=(11,28,17))
    draw.arc([cx-20, ay+4, cx+20, ay+37], 200, 340, fill=acc_col, width=1)
    draw.ellipse([cx-11, ay+17, cx+11, ay+32], fill=(7,15,11))
    # Eyes
    draw.ellipse([cx-9,  ay+20, cx-4,  ay+25], fill=eye_col)
    draw.ellipse([cx-8,  ay+21, cx-5,  ay+24], fill=skin["eye_shine"])
    draw.ellipse([cx+4,  ay+20, cx+9,  ay+25], fill=eye_col)
    draw.ellipse([cx+5,  ay+21, cx+8,  ay+24], fill=skin["eye_shine"])
    # Shoulders
    draw.arc([cx-22, ay+37, cx+22, ay+57], 0, 180, fill=acc_col, width=2)
    draw.line([(cx-19,ay+48),(cx-30,ay+56)], fill=acc_col, width=2)
    draw.line([(cx-30,ay+56),(cx-34,ay+52)], fill=acc_col, width=1)
    draw.line([(cx-30,ay+56),(cx-35,ay+57)], fill=acc_col, width=1)
    draw.line([(cx-30,ay+56),(cx-33,ay+61)], fill=acc_col, width=1)
    # Phase stars
    for pi in range(phase + 1):
        sx2 = cx - 12 + pi * 6
        draw.text((sx2, ay+2), "*", fill=LEVELUP_COLORS[pi], font=F_SM, anchor="lt")
    # Body dots
    for gx in range(cx-10, cx+12, 7):
        for gy in range(ay+38, ay+54, 6):
            draw.rectangle([gx, gy, gx+2, gy+2], fill=lerp(acc_col, BLACK, 0.6))

    draw.line([(8, ay+64), (W-8, ay+64)], fill=(0,48,24), width=1)

    sy2 = ay + 74
    draw.text((cx, sy2),      "SCORE",    fill=HUD_CYAN, font=F_SM, anchor="mm")
    draw.text((cx, sy2 + 16), str(score), fill=acc_col,  font=F_LG, anchor="mm")

    fy = sy2 + 38
    draw.text((cx, fy),       "FOOD",               fill=HUD_CYAN, font=F_SM, anchor="mm")
    draw.text((cx, fy + 16),  f"{eaten}/{total_food}", fill=acc_col, font=F_MD, anchor="mm")

    lv = fy + 38
    draw.text((cx, lv),       "LEVEL",      fill=HUD_CYAN,              font=F_SM, anchor="mm")
    draw.text((cx, lv + 16),  str(phase+1), fill=LEVELUP_COLORS[phase], font=F_LG, anchor="mm")

    li = lv + 38
    draw.text((cx, li), "LIFE", fill=HUD_CYAN, font=F_SM, anchor="mm")
    for i in range(3):
        ix = cx - 14 + i * 14
        draw.ellipse([ix-5, li+11, ix+5, li+21], fill=acc_col)
        draw.ellipse([ix-2, li+14, ix+2, li+18], fill=(0, 80, 35))


def draw_header(draw, width, username, eaten, total, skin):
    draw.rectangle([4, 4, width-4, PADDING_Y-4], fill=HEADER_BG)
    draw.line([(4, PADDING_Y-4),(width-4, PADDING_Y-4)], fill=(0,55,28), width=1)
    draw.text((SIDE_W + 16, PADDING_Y//2), "// CYBER SNAKE",
              fill=skin["hud_label"], font=F_LG, anchor="lm")
    pct = int(eaten/total*100) if total else 0
    draw.text((width-16, PADDING_Y//2), f"{eaten}/{total}  [{pct}%]",
              fill=HUD_CYAN, font=F_MD, anchor="rm")


def draw_month_labels(draw, month_labels, ox, oy):
    for x_col, label in month_labels.items():
        px = ox + x_col * (CELL + GAP)
        draw.text((px, oy - MONTH_OFFSET + 2), label, fill=DIM, font=F_SM)

def draw_weekday_labels(draw, rows, ox, oy):
    short = ["S","M","T","W","T","F","S"]
    for y in range(rows):
        py = oy + y * (CELL + GAP) + CELL // 2
        draw.text((ox - 10, py), short[y], fill=DIM, font=F_SM, anchor="rm")


def draw_grid(draw, cols, rows, counts, eaten, ox, oy, flash_cells=None):
    flash_cells = flash_cells or set()
    for y in range(rows):
        for x in range(cols):
            count = counts.get((x, y), 0)
            level = count_to_level(count)
            rect  = cell_rect(x, y, ox, oy)
            l, t, r, b = rect
            if (x, y) in flash_cells:
                base = FLASH_COLOR; hi = (240,255,240); sh = (170,220,170)
            elif (x, y) in eaten:
                base = hi = sh = EATEN_COLOR
            else:
                base = LEVEL_COLORS[level]
                hi   = LEVEL_HIGHLIGHT[level]
                sh   = LEVEL_SHADOW[level]
            draw.rounded_rectangle(rect, radius=2, fill=base)
            uneaten = (x, y) not in eaten and (x, y) not in flash_cells
            if uneaten and count > 0:
                draw.line([(l+2,t),(r-2,t)],     fill=hi, width=1)
                draw.line([(l,t+2),(l,b-2)],     fill=hi, width=1)
                draw.line([(l+2,b),(r-2,b)],     fill=sh, width=1)
                draw.line([(r,t+2),(r,b-2)],     fill=sh, width=1)
                gc = GLOW_COLORS[level]
                if gc:
                    draw.rounded_rectangle([l-1,t-1,r+1,b+1], radius=3, outline=gc, width=1)


def draw_progress_bar(draw, width, height, eaten, total, skin):
    ratio = eaten / total if total > 0 else 0
    oy    = height - BOTTOM_PAD + 10
    ox    = SIDE_W + 16
    bw    = width - ox - 16
    bh    = 8
    draw.rounded_rectangle([ox, oy, ox+bw, oy+bh], radius=4, fill=PROG_BG)
    fw = int(bw * ratio)
    if fw > 0:
        seg = max(1, fw // 40)
        c1  = skin["tail"]
        c2  = skin["inner"]
        for i in range(0, fw, seg):
            c  = lerp(c1, c2, i / bw)
            x0 = ox + i
            x1 = min(ox + i + seg + 1, ox + fw)
            draw.rectangle([x0, oy, x1, oy+bh], fill=c)
        draw.rounded_rectangle([ox, oy, ox+fw, oy+bh], radius=4,
                                outline=skin["inner"], width=1)
    if total > 0 and eaten >= total:
        draw.text((ox+bw//2, oy+bh//2), "COMPLETE", fill=(0,255,150), font=F_SM, anchor="mm")
    else:
        draw.text((ox-4,      oy+bh//2), "0",        fill=DIM, font=F_SM, anchor="rm")
        draw.text((ox+bw+4,   oy+bh//2), str(total), fill=DIM, font=F_SM, anchor="lm")
    pct = int(ratio * 100)
    draw.text((width-16, oy+bh//2), f"{pct}%", fill=CYAN, font=F_MD, anchor="rm")


def make_glow(width, height, body_points, skin):
    """Coloured glow behind the snake body."""
    glow  = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d     = ImageDraw.Draw(glow)
    if len(body_points) >= 2:
        r, g, b = skin["glow_rgb"]
        d.line(body_points, fill=(r, g, b, 55),  width=22, joint="curve")
        d.line(body_points, fill=(r, g, b, 35),  width=12, joint="curve")
        hx, hy = body_points[-1]
        d.ellipse([hx-16, hy-16, hx+16, hy+16], fill=(r, g, b, 90))
        d.ellipse([hx-8,  hy-8,  hx+8,  hy+8],  fill=(r, g, b, 140))
    return glow.filter(ImageFilter.GaussianBlur(4))


def draw_snake_body(draw, body_points, skin, flash_t=0.0):
    """
    Draw the snake body with the skin gradient.
    flash_t: 0.0 = normal, 1.0 = full flash colour (used on level-up transition).
    """
    n = len(body_points)
    if n < 2:
        return
    fc = skin["flash_col"]
    for i in range(n - 1):
        t     = i / max(n-1, 1)
        outer = lerp(skin["tail"],  skin["body"],  t)
        inner = lerp(skin["tail"],  skin["inner"], t)
        # Blend towards flash colour
        if flash_t > 0:
            outer = lerp(outer, fc, flash_t)
            inner = lerp(inner, fc, flash_t)
        draw.line([body_points[i], body_points[i+1]], fill=outer, width=11)
        draw.line([body_points[i], body_points[i+1]], fill=inner, width=7)
    tx, ty = body_points[0]
    tail_col = lerp(skin["inner"], fc, flash_t) if flash_t > 0 else skin["inner"]
    draw.ellipse([tx-3.5, ty-3.5, tx+3.5, ty+3.5], fill=tail_col)


def draw_snake_head(draw, hx, hy, dx, dy, skin, flash_t=0.0):
    nx, ny = -dy, dx
    style  = skin.get("style", "diamond")
    fc     = skin["flash_col"]
    hc     = lerp(skin["head"],       fc, flash_t * 0.6) if flash_t > 0 else skin["head"]
    hi     = lerp(skin["head_inner"], fc, flash_t * 0.4) if flash_t > 0 else skin["head_inner"]
    eye    = skin["eye_fill"]
    tongue = skin["tongue"]

    if style == "diamond":
        nose  = (hx+dx*11, hy+dy*11)
        left  = (hx-dx*6+nx*8,  hy-dy*6+ny*8)
        right = (hx-dx*6-nx*8,  hy-dy*6-ny*8)
        back  = (hx-dx*11, hy-dy*11)
        draw.polygon([nose, left, back, right], fill=hc)
        n2 = (hx+dx*6,        hy+dy*6)
        l2 = (hx-dx*3+nx*4.5, hy-dy*3+ny*4.5)
        r2 = (hx-dx*3-nx*4.5, hy-dy*3-ny*4.5)
        b2 = (hx-dx*6,        hy-dy*6)
        draw.polygon([n2, l2, b2, r2], fill=hi)

    elif style == "arrow":
        nose    = (hx+dx*13, hy+dy*13)
        left    = (hx-dx*2+nx*9,  hy-dy*2+ny*9)
        right   = (hx-dx*2-nx*9,  hy-dy*2-ny*9)
        notch   = (hx-dx*9,       hy-dy*9)
        notch_l = (hx-dx*7+nx*4,  hy-dy*7+ny*4)
        notch_r = (hx-dx*7-nx*4,  hy-dy*7-ny*4)
        draw.polygon([nose, left, notch_l, notch, notch_r, right], fill=hc)
        draw.line([(hx,hy),(hx+dx*10,hy+dy*10)], fill=hi, width=3)

    elif style == "cobra":
        nose   = (hx+dx*10, hy+dy*10)
        left   = (hx-dx*3+nx*13, hy-dy*3+ny*13)
        right  = (hx-dx*3-nx*13, hy-dy*3-ny*13)
        back   = (hx-dx*10, hy-dy*10)
        back_l = (hx-dx*8+nx*7,  hy-dy*8+ny*7)
        back_r = (hx-dx*8-nx*7,  hy-dy*8-ny*7)
        draw.polygon([nose, left, back_l, back, back_r, right], fill=hc)
        draw.ellipse([hx-5,hy-5,hx+5,hy+5], fill=hi)
        draw.line([(hx+nx*5,hy+ny*5),(hx-dx*2+nx*10,hy-dy*2+ny*10)], fill=hi, width=2)
        draw.line([(hx-nx*5,hy-ny*5),(hx-dx*2-nx*10,hy-dy*2-ny*10)], fill=hi, width=2)

    elif style == "dragon":
        nose  = (hx+dx*12, hy+dy*12)
        left  = (hx-dx*4+nx*9,  hy-dy*4+ny*9)
        right = (hx-dx*4-nx*9,  hy-dy*4-ny*9)
        back  = (hx-dx*10, hy-dy*10)
        draw.polygon([nose, left, back, right], fill=hc)
        draw.polygon([(hx+dx*6,hy+dy*6),(hx+dx*2+nx*5,hy+dy*2+ny*5),
                      (hx+dx*2-nx*5,hy+dy*2-ny*5)], fill=lerp(hc, BLACK, 0.3))
        horn_base_l = (hx-dx*4+nx*8, hy-dy*4+ny*8)
        horn_base_r = (hx-dx*4-nx*8, hy-dy*4-ny*8)
        draw.line([horn_base_l,(hx-dx*1+nx*12,hy-dy*1+ny*12)], fill=hi, width=2)
        draw.line([horn_base_r,(hx-dx*1-nx*12,hy-dy*1-ny*12)], fill=hi, width=2)
        draw.polygon([(hx+dx*8,hy+dy*8),(hx-dx*2+nx*5.5,hy-dy*2+ny*5.5),
                      (hx-dx*2-nx*5.5,hy-dy*2-ny*5.5),(hx-dx*6,hy-dy*6)], fill=hi)

    elif style == "crown":
        nose  = (hx+dx*11, hy+dy*11)
        left  = (hx-dx*5+nx*9,  hy-dy*5+ny*9)
        right = (hx-dx*5-nx*9,  hy-dy*5-ny*9)
        back  = (hx-dx*11, hy-dy*11)
        draw.polygon([nose, left, back, right], fill=hc)
        spike_m = (hx-dx*15, hy-dy*15)
        spike_l = (hx-dx*12+nx*7,  hy-dy*12+ny*7)
        spike_r = (hx-dx*12-nx*7,  hy-dy*12-ny*7)
        draw.polygon([back,(hx-dx*9+nx*3,hy-dy*9+ny*3),spike_m,
                      (hx-dx*9-nx*3,hy-dy*9-ny*3)], fill=hi)
        draw.polygon([left,(hx-dx*7+nx*8,hy-dy*7+ny*8),spike_l,
                      (hx-dx*3+nx*9,hy-dy*3+ny*9)], fill=hi)
        draw.polygon([right,(hx-dx*7-nx*8,hy-dy*7-ny*8),spike_r,
                      (hx-dx*3-nx*9,hy-dy*3-ny*9)], fill=hi)
        draw.ellipse([hx-3,hy-3,hx+3,hy+3], fill=(255,255,200))
        draw.ellipse([hx-1.5,hy-1.5,hx+1.5,hy+1.5], fill=WHITE)

    # Eyes
    for side in (-1, 1):
        ex = hx + dx*3 + nx*3*side
        ey = hy + dy*3 + ny*3*side
        draw.ellipse([ex-2,ey-2,ex+2,ey+2], fill=eye)
        draw.ellipse([ex-0.8,ey-0.8,ex+0.8,ey+0.8], fill=BLACK)
    # Tongue
    sx = hx+dx*8; sy = hy+dy*8
    mx = hx+dx*14; my = hy+dy*14
    draw.line([(sx,sy),(mx,my)],                      fill=tongue, width=2)
    draw.line([(mx,my),(mx+nx*2.5,my+ny*2.5)],        fill=tongue, width=1)
    draw.line([(mx,my),(mx-nx*2.5,my-ny*2.5)],        fill=tongue, width=1)


def draw_snake(draw, body_points, skin, flash_t=0.0):
    if len(body_points) < 2:
        return
    draw_snake_body(draw, body_points, skin, flash_t)
    hx, hy = body_points[-1]
    px, py = body_points[-2]
    dist   = math.hypot(hx-px, hy-py) or 1
    draw_snake_head(draw, hx, hy, (hx-px)/dist, (hy-py)/dist, skin, flash_t)


def draw_levelup_banner(draw, width, height, phase, progress):
    """Fade-in/hold/fade-out banner. progress 0.0→1.0."""
    skin  = SNAKE_SKINS[phase]
    color = LEVELUP_COLORS[phase]
    if progress < 0.2:
        alpha = progress / 0.2
    elif progress > 0.8:
        alpha = (1.0 - progress) / 0.2
    else:
        alpha = 1.0
    strip_h = 38
    strip_y = height // 2 - strip_h // 2
    bx0, bx1 = SIDE_W + 4, width - 6
    backdrop  = lerp(BG, lerp(skin["body"], BLACK, 0.2), alpha)
    draw.rounded_rectangle([bx0, strip_y, bx1, strip_y+strip_h],
                            radius=6, fill=backdrop)
    border_c = lerp(BG, color, alpha)
    draw.rounded_rectangle([bx0, strip_y, bx1, strip_y+strip_h],
                            radius=6, outline=border_c, width=2)
    cx  = (bx0 + bx1) // 2
    cy  = strip_y + strip_h // 2
    col = lerp(BG, color, alpha)
    draw.text((cx, cy - 8),  "* LEVEL UP! *",  fill=col, font=F_XL, anchor="mm")
    draw.text((cx, cy + 12), skin["name"],
              fill=lerp(BG, WHITE, alpha * 0.85), font=F_MD, anchor="mm")


def create_frames(cols, rows, counts, month_labels):
    ox = SIDE_W + 20 + 10
    oy = PADDING_Y
    grid_w = cols * (CELL + GAP) - GAP
    grid_h = rows * (CELL + GAP) - GAP
    width  = ox + grid_w + PADDING_X
    height = oy + grid_h + BOTTOM_PAD

    full_path, food_cells = build_path(cols, rows, counts)
    points, cell_at       = smooth_path(full_path, ox, oy)

    frames            = []
    eaten             = set()
    snake_length      = INITIAL_SNAKE_LENGTH
    total_food        = len(food_cells)
    score             = 0
    prev_phase        = 0
    levelup_countdown = 0   # frames left to show LEVEL UP! banner
    skin_flash_left   = 0   # frames left for body colour flash

    for fi in range(len(points)):
        head_cell   = cell_at[fi]
        count       = counts.get(head_cell, 0)
        flash_cells = set()

        if count > 0 and head_cell not in eaten:
            eaten.add(head_cell)
            snake_length += GROW_PER_FOOD + min(count, MAX_GROW_FROM_ONE_DAY)
            snake_length  = min(snake_length, MAX_SNAKE_LENGTH)
            flash_cells   = {head_cell}
            score        += count * 10

        phase = get_skin_phase(len(eaten), total_food)
        skin  = SNAKE_SKINS[phase]

        # Detect phase transition — trigger both banner and body flash
        if phase > prev_phase:
            levelup_countdown = LEVELUP_FLASH_FRAMES
            skin_flash_left   = SKIN_FLASH_FRAMES
        prev_phase = phase

        # Body flash intensity: peaks at 1.0 then ramps down to 0.0
        if skin_flash_left > 0:
            flash_t = skin_flash_left / SKIN_FLASH_FRAMES   # 1.0 → near 0
            skin_flash_left -= 1
        else:
            flash_t = 0.0

        start       = max(0, fi - snake_length)
        body_points = points[start:fi + 1]

        img  = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)
        draw_frame(draw, width, height, skin)
        draw_header(draw, width, GITHUB_USER_NAME, len(eaten), total_food, skin)
        draw_side_panel(draw, height, len(eaten), total_food, score, phase, skin)
        draw_month_labels(draw, month_labels, ox, oy)
        draw_weekday_labels(draw, rows, ox, oy)
        draw_grid(draw, cols, rows, counts, eaten, ox, oy, flash_cells)
        draw_progress_bar(draw, width, height, len(eaten), total_food, skin)

        glow = make_glow(width, height, body_points, skin)
        img  = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw_snake(draw, body_points, skin, flash_t)

        if levelup_countdown > 0:
            progress_val = 1.0 - (levelup_countdown / LEVELUP_FLASH_FRAMES)
            draw_levelup_banner(draw, width, height, phase, progress_val)
            levelup_countdown -= 1

        frames.append(img)

    if frames:
        for _ in range(20):
            frames.append(frames[-1].copy())

    return frames


def main():
    os.makedirs("dist", exist_ok=True)
    random.seed(time.time_ns())
    calendar                          = fetch_contribution_calendar(GITHUB_USER_NAME)
    cols, rows, counts, total, months = build_grid(calendar)
    frames                            = create_frames(cols, rows, counts, months)
    frames[0].save(
        "dist/custom-snake.gif",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )
    frames[0].save("dist/custom-snake-preview.png")
    print(f"Generated  : dist/custom-snake.gif")
    print(f"User       : {GITHUB_USER_NAME}")
    print(f"Contributions : {total}")
    print(f"Grid       : {cols}w x {rows}h")
    print(f"Frames     : {len(frames)}")

if __name__ == "__main__":
    main()
