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
# COMPLETE RANDOM REAL CONTRIBUTION SNAKE
# - Starts from left side
# - Eats ALL real green contribution blocks
# - Shows completion line + progress bar
# - Does NOT use one fixed scanning path
# - If it gets stuck, it restarts from the left side
# =========================================================

GITHUB_USER_NAME = os.environ.get("GITHUB_USER_NAME", "AshishKumar161")

# 53 = full year, 26 = half year
LAST_WEEKS = 53

# Layout
CELL = 10
GAP = 3
PADDING_X = 20
PADDING_Y = 44
BOTTOM_PADDING = 32

# Animation speed/smoothness
FRAMES_PER_CELL = 3
FRAME_DURATION_MS = 50

# Snake settings
INITIAL_SNAKE_LENGTH = 12
GROW_PER_FOOD = 4
MAX_GROW_FROM_ONE_DAY = 8
MAX_SNAKE_LENGTH = 155

# Safety limit
MAX_RESTARTS = 250

# Random target behavior
RANDOM_TARGET_CHANCE = 0.45
NEAR_TARGET_LIMIT = 8

# Colors
BG = (13, 17, 23)
PANEL = (8, 13, 20)
GRID_EMPTY = (22, 27, 34)
GRID_EATEN = (8, 14, 20)

LEVEL_COLORS = [
    (22, 27, 34),    # 0 contributions
    (14, 68, 41),    # low
    (0, 109, 50),    # medium
    (38, 166, 65),   # high
    (57, 211, 83),   # very high
]

SNAKE_OUTER = (0, 120, 55)
SNAKE_INNER = (0, 255, 65)
SNAKE_HEAD = (170, 0, 255)
SNAKE_HEAD_INNER = (240, 140, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
TONGUE = (255, 40, 120)
PROGRESS_BG = (22, 27, 34)
PROGRESS_FILL = (0, 255, 65)


def load_font(size=13):
    possible = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for font_path in possible:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass

    return ImageFont.load_default()


FONT = load_font(13)
SMALL_FONT = load_font(11)


def fetch_contribution_calendar(username):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    if not token:
        raise RuntimeError("GITHUB_TOKEN not found. Run this inside GitHub Actions.")

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    payload = json.dumps({
        "query": query,
        "variables": {"login": username}
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "complete-random-contribution-snake",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if "errors" in data:
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")

    user = data.get("data", {}).get("user")

    if not user:
        raise RuntimeError(f"GitHub user not found: {username}")

    return user["contributionsCollection"]["contributionCalendar"]


def count_to_level(count):
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 10:
        return 3
    return 4


def cell_rect(x, y):
    left = PADDING_X + x * (CELL + GAP)
    top = PADDING_Y + y * (CELL + GAP)
    return [left, top, left + CELL, top + CELL]


def center_of_cell(x, y):
    rect = cell_rect(x, y)
    return (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2


def build_grid(calendar):
    weeks = calendar["weeks"][-LAST_WEEKS:]
    cols = len(weeks)
    rows = 7

    counts = {}
    total = 0

    for x, week in enumerate(weeks):
        for day in week["contributionDays"]:
            d = date.fromisoformat(day["date"])

            # GitHub grid starts from Sunday.
            y = (d.weekday() + 1) % 7

            count = int(day["contributionCount"])
            counts[(x, y)] = count
            total += count

    return cols, rows, counts, total


def neighbors(cell, cols, rows):
    x, y = cell
    result = []

    if x > 0:
        result.append((x - 1, y))
    if x < cols - 1:
        result.append((x + 1, y))
    if y > 0:
        result.append((x, y - 1))
    if y < rows - 1:
        result.append((x, y + 1))

    random.shuffle(result)
    return result


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def choose_left_start(rows):
    return (0, rows // 2)


def choose_target(current, remaining_food):
    remaining = list(remaining_food)

    if not remaining:
        return None

    # Sometimes choose any random contribution block.
    # Sometimes choose one of the nearest blocks.
    # This prevents the same fixed path in every run.
    if random.random() < RANDOM_TARGET_CHANCE:
        return random.choice(remaining)

    remaining.sort(key=lambda cell: manhattan(current, cell))
    return random.choice(remaining[:min(NEAR_TARGET_LIMIT, len(remaining))])


def bfs_path(start, goal, cols, rows, blocked=None):
    blocked = set(blocked or [])
    blocked.discard(start)
    blocked.discard(goal)

    queue = deque([start])
    parent = {start: None}

    while queue:
        current = queue.popleft()

        if current == goal:
            break

        for nxt in neighbors(current, cols, rows):
            if nxt in parent:
                continue
            if nxt in blocked:
                continue

            parent[nxt] = current
            queue.append(nxt)

    if goal not in parent:
        return None

    path = []
    current = goal

    while current is not None:
        path.append(current)
        current = parent[current]

    path.reverse()
    return path


def build_segments(cols, rows, counts):
    food_cells = {cell for cell, count in counts.items() if count > 0}
    remaining_food = set(food_cells)

    segments = []
    restart_count = 0

    while remaining_food and restart_count < MAX_RESTARTS:
        current = choose_left_start(rows)

        snake_body = deque([current])
        snake_body_set = {current}
        snake_length = INITIAL_SNAKE_LENGTH

        segment = [current]
        made_progress = False

        if current in remaining_food:
            remaining_food.remove(current)
            snake_length += GROW_PER_FOOD + min(counts.get(current, 0), MAX_GROW_FROM_ONE_DAY)
            made_progress = True

        while remaining_food:
            target = choose_target(current, remaining_food)
            path = bfs_path(current, target, cols, rows, blocked=snake_body_set)

            if not path:
                break

            stuck = False

            for next_cell in path[1:]:
                tail = snake_body[0]

                if next_cell in snake_body_set and next_cell != tail:
                    stuck = True
                    break

                current = next_cell
                segment.append(current)

                snake_body.append(current)
                snake_body_set.add(current)

                ate = False

                if current in remaining_food:
                    remaining_food.remove(current)
                    snake_length += GROW_PER_FOOD + min(counts.get(current, 0), MAX_GROW_FROM_ONE_DAY)
                    snake_length = min(snake_length, MAX_SNAKE_LENGTH)
                    ate = True
                    made_progress = True

                while len(snake_body) > snake_length:
                    removed = snake_body.popleft()
                    if removed not in snake_body:
                        snake_body_set.discard(removed)

                if ate:
                    break

            if stuck:
                break

        if len(segment) > 1:
            segments.append(segment)

        # Fallback so all green blocks definitely complete.
        # If current body logic gets stuck, start from left and eat one block.
        if not made_progress and remaining_food:
            current = choose_left_start(rows)
            target = choose_target(current, remaining_food)
            force_path = bfs_path(current, target, cols, rows, blocked=None)

            if force_path and len(force_path) > 1:
                segments.append(force_path)
                remaining_food.remove(target)
            else:
                break

        restart_count += 1

    return segments, food_cells


def smooth_points(cell_path):
    if len(cell_path) == 1:
        point = center_of_cell(*cell_path[0])
        return [point], [cell_path[0]]

    points = []
    cell_at_frame = []

    for i in range(len(cell_path) - 1):
        x1, y1 = center_of_cell(*cell_path[i])
        x2, y2 = center_of_cell(*cell_path[i + 1])

        for step in range(FRAMES_PER_CELL):
            t = step / FRAMES_PER_CELL
            t = t * t * (3 - 2 * t)

            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t

            points.append((px, py))
            cell_at_frame.append(cell_path[i])

    points.append(center_of_cell(*cell_path[-1]))
    cell_at_frame.append(cell_path[-1])

    return points, cell_at_frame


def draw_panel(draw, width, height):
    draw.rounded_rectangle(
        [2, 2, width - 3, height - 3],
        radius=16,
        fill=PANEL,
        outline=(0, 120, 55),
        width=2,
    )


def draw_grid(draw, cols, rows, counts, eaten):
    for y in range(rows):
        for x in range(cols):
            count = counts.get((x, y), 0)
            rect = cell_rect(x, y)

            fill = GRID_EATEN if (x, y) in eaten else LEVEL_COLORS[count_to_level(count)]
            draw.rounded_rectangle(rect, radius=3, fill=fill)

            if count > 0 and (x, y) not in eaten:
                glow_rect = [rect[0] - 1, rect[1] - 1, rect[2] + 1, rect[3] + 1]
                draw.rounded_rectangle(glow_rect, radius=4, outline=(0, 255, 65), width=1)


def draw_status(draw, width, eaten_count, total_food):
    ratio = 1.0 if total_food == 0 else eaten_count / total_food

    if total_food > 0 and eaten_count >= total_food:
        text = f"Contribution Snake  |  Green blocks: {eaten_count}/{total_food}  |  COMPLETE"
    else:
        text = f"Contribution Snake  |  Green blocks: {eaten_count}/{total_food}"

    draw.text((PADDING_X, 14), text, fill=(0, 255, 65), font=FONT)

    graph_bottom = PADDING_Y + 7 * CELL + 6 * GAP
    bar_x = PADDING_X
    bar_y = graph_bottom + 14
    bar_w = width - PADDING_X * 2
    bar_h = 8

    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=4,
        fill=PROGRESS_BG,
    )

    fill_w = int(bar_w * ratio)

    if fill_w > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
            radius=4,
            fill=PROGRESS_FILL,
        )

    percent_text = f"{int(ratio * 100)}%"
    draw.text((bar_x + bar_w - 34, bar_y - 3), percent_text, fill=WHITE, font=SMALL_FONT)


def make_snake_glow(width, height, body_points):
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    if len(body_points) >= 2:
        glow_draw.line(body_points, fill=(0, 255, 65, 105), width=15, joint="curve")
        hx, hy = body_points[-1]
        glow_draw.ellipse([hx - 12, hy - 12, hx + 12, hy + 12], fill=(180, 0, 255, 145))

    return glow.filter(ImageFilter.GaussianBlur(4))


def draw_snake_head(draw, hx, hy, dx, dy):
    nx = -dy
    ny = dx

    nose = (hx + dx * 10, hy + dy * 10)
    left = (hx - dx * 6 + nx * 7, hy - dy * 6 + ny * 7)
    right = (hx - dx * 6 - nx * 7, hy - dy * 6 - ny * 7)
    back = (hx - dx * 10, hy - dy * 10)

    draw.polygon([nose, left, back, right], fill=SNAKE_HEAD)

    nose2 = (hx + dx * 5, hy + dy * 5)
    left2 = (hx - dx * 3 + nx * 4, hy - dy * 3 + ny * 4)
    right2 = (hx - dx * 3 - nx * 4, hy - dy * 3 - ny * 4)
    back2 = (hx - dx * 5, hy - dy * 5)

    draw.polygon([nose2, left2, back2, right2], fill=SNAKE_HEAD_INNER)

    for side in (-1, 1):
        ex = hx + dx * 2.8 + nx * 2.6 * side
        ey = hy + dy * 2.8 + ny * 2.6 * side
        draw.ellipse([ex - 1.5, ey - 1.5, ex + 1.5, ey + 1.5], fill=WHITE)
        draw.ellipse([ex - 0.6, ey - 0.6, ex + 0.6, ey + 0.6], fill=BLACK)

    sx = hx + dx * 7
    sy = hy + dy * 7
    mx = hx + dx * 11
    my = hy + dy * 11
    lx = mx + nx * 1.4
    ly = my + ny * 1.4
    rx = mx - nx * 1.4
    ry = my - ny * 1.4

    draw.line([(sx, sy), (mx, my)], fill=TONGUE, width=2)
    draw.line([(mx, my), (lx, ly)], fill=TONGUE, width=1)
    draw.line([(mx, my), (rx, ry)], fill=TONGUE, width=1)


def draw_snake(draw, body_points):
    if len(body_points) < 2:
        return

    draw.line(body_points, fill=SNAKE_OUTER, width=10, joint="curve")
    draw.line(body_points, fill=SNAKE_INNER, width=6, joint="curve")

    tx, ty = body_points[0]
    draw.ellipse([tx - 3.5, ty - 3.5, tx + 3.5, ty + 3.5], fill=SNAKE_INNER)

    hx, hy = body_points[-1]
    px, py = body_points[-2]

    dx = hx - px
    dy = hy - py
    distance = math.hypot(dx, dy) or 1
    dx /= distance
    dy /= distance

    draw_snake_head(draw, hx, hy, dx, dy)


def create_frames(cols, rows, counts):
    width = PADDING_X * 2 + cols * CELL + (cols - 1) * GAP
    height = PADDING_Y + rows * CELL + (rows - 1) * GAP + BOTTOM_PADDING

    segments, food_cells = build_segments(cols, rows, counts)

    frames = []
    eaten = set()
    snake_length = INITIAL_SNAKE_LENGTH
    total_food = len(food_cells)

    for segment in segments:
        points, cell_at_frame = smooth_points(segment)

        for frame_index in range(len(points)):
            head_cell = cell_at_frame[frame_index]
            count = counts.get(head_cell, 0)

            if count > 0 and head_cell not in eaten:
                eaten.add(head_cell)
                snake_length += GROW_PER_FOOD + min(count, MAX_GROW_FROM_ONE_DAY)
                snake_length = min(snake_length, MAX_SNAKE_LENGTH)

            start = max(0, frame_index - snake_length)
            body_points = points[start:frame_index + 1]

            image = Image.new("RGB", (width, height), BG)
            draw = ImageDraw.Draw(image)

            draw_panel(draw, width, height)
            draw_status(draw, width, len(eaten), total_food)
            draw_grid(draw, cols, rows, counts, eaten)

            glow = make_snake_glow(width, height, body_points)
            image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

            draw = ImageDraw.Draw(image)
            draw_snake(draw, body_points)

            frames.append(image)

        if frames:
            for _ in range(3):
                frames.append(frames[-1].copy())

    if frames:
        for _ in range(12):
            frames.append(frames[-1].copy())

    return frames


def main():
    os.makedirs("dist", exist_ok=True)

    # New route each workflow run.
    random.seed(time.time_ns())

    calendar = fetch_contribution_calendar(GITHUB_USER_NAME)
    cols, rows, counts, total = build_grid(calendar)

    frames = create_frames(cols, rows, counts)

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

    print("Generated dist/custom-snake.gif")
    print(f"User: {GITHUB_USER_NAME}")
    print(f"Real contributions in shown weeks: {total}")
    print(f"Frames: {len(frames)}")


if __name__ == "__main__":
    main()
