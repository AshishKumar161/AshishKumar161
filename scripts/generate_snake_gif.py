import json
import math
import os
import urllib.request
from collections import deque
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

GITHUB_USER_NAME = os.environ.get("GITHUB_USER_NAME", "AshishKumar161")

LAST_WEEKS = 53

CELL = 10
GAP = 3
PADDING_X = 20
PADDING_Y = 20

FRAMES_PER_CELL = 4
FRAME_DURATION_MS = 45

INITIAL_SNAKE_LENGTH = 12
GROW_PER_FOOD = 5
MAX_GROW_FROM_ONE_DAY = 10
MAX_SNAKE_LENGTH = 180

MAX_SEGMENT_STEPS = 500
MAX_RESTARTS = 8

BG = (13, 17, 23)
PANEL = (8, 13, 20)
GRID_EMPTY = (22, 27, 34)
GRID_EATEN = (10, 16, 22)

LEVEL_COLORS = [
    (22, 27, 34),
    (14, 68, 41),
    (0, 109, 50),
    (38, 166, 65),
    (57, 211, 83),
]

SNAKE_OUTER = (0, 120, 55)
SNAKE_INNER = (0, 255, 65)
SNAKE_HEAD = (170, 0, 255)
SNAKE_HEAD_INNER = (240, 140, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
TONGUE = (255, 40, 120)


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
            "User-Agent": "left-start-restart-snake",
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

    return result


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def row_priority(rows, target_y):
    return sorted(range(rows), key=lambda y: (abs(y - target_y), y))


def choose_left_start(cols, rows, remaining_food):
    target_y = rows // 2

    if remaining_food:
        leftmost_target = min(remaining_food, key=lambda c: (c[0], abs(c[1] - rows // 2)))
        target_y = leftmost_target[1]

    for x in range(min(3, cols)):
        for y in row_priority(rows, target_y):
            return (x, y)

    return (0, rows // 2)


def bfs_path(start, goal, cols, rows, blocked, allow_tail=None):
    blocked = set(blocked)
    blocked.discard(start)

    if allow_tail is not None:
        blocked.discard(allow_tail)

    q = deque([start])
    parent = {start: None}

    while q:
        cur = q.popleft()

        if cur == goal:
            break

        for nxt in neighbors(cur, cols, rows):
            if nxt in parent:
                continue
            if nxt in blocked and nxt != goal:
                continue
            parent[nxt] = cur
            q.append(nxt)

    if goal not in parent:
        return None

    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]

    path.reverse()
    return path


def find_path_to_any_food(head, remaining_food, cols, rows, body_set, allow_tail):
    if not remaining_food:
        return None, None

    candidates = sorted(
        remaining_food,
        key=lambda cell: (manhattan(head, cell), cell[0], cell[1])
    )[:15]

    for target in candidates:
        path = bfs_path(head, target, cols, rows, body_set, allow_tail)
        if path and len(path) >= 2:
            return path, target

    return None, None


def build_segments(cols, rows, counts):
    food_cells = {cell for cell, count in counts.items() if count > 0}
    remaining_food = set(food_cells)

    segments = []
    restart_count = 0

    while remaining_food and restart_count <= MAX_RESTARTS:
        start = choose_left_start(cols, rows, remaining_food)

        body = deque([start])
        body_set = {start}
        snake_length = INITIAL_SNAKE_LENGTH

        segment = [start]
        step_count = 0

        if start in remaining_food:
            remaining_food.remove(start)
            snake_length += GROW_PER_FOOD + min(counts.get(start, 0), MAX_GROW_FROM_ONE_DAY)
            snake_length = min(snake_length, MAX_SNAKE_LENGTH)

        while remaining_food and step_count < MAX_SEGMENT_STEPS:
            head = body[-1]
            tail = body[0]

            path, _ = find_path_to_any_food(head, remaining_food, cols, rows, body_set, tail)

            if not path:
                break

            next_head = path[1]

            # move
            body.append(next_head)
            body_set.add(next_head)
            segment.append(next_head)

            ate_food = False

            if next_head in remaining_food:
                remaining_food.remove(next_head)
                snake_length += GROW_PER_FOOD + min(counts.get(next_head, 0), MAX_GROW_FROM_ONE_DAY)
                snake_length = min(snake_length, MAX_SNAKE_LENGTH)
                ate_food = True

            if not ate_food:
                while len(body) > snake_length:
                    removed = body.popleft()
                    body_set.remove(removed)
            else:
                while len(body) > snake_length:
                    removed = body.popleft()
                    body_set.remove(removed)

            step_count += 1

        segments.append(segment)
        restart_count += 1

    return segments


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


def make_snake_glow(width, height, body_points):
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    if len(body_points) >= 2:
        gd.line(body_points, fill=(0, 255, 65, 105), width=15, joint="curve")
        hx, hy = body_points[-1]
        gd.ellipse([hx - 12, hy - 12, hx + 12, hy + 12], fill=(180, 0, 255, 145))

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
    height = PADDING_Y * 2 + rows * CELL + (rows - 1) * GAP

    segments = build_segments(cols, rows, counts)

    frames = []
    eaten = set()

    for segment in segments:
        points, cell_at_frame = smooth_points(segment)
        snake_length = INITIAL_SNAKE_LENGTH

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
            draw_grid(draw, cols, rows, counts, eaten)

            glow = make_snake_glow(width, height, body_points)
            image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

            draw = ImageDraw.Draw(image)
            draw_snake(draw, body_points)

            frames.append(image)

        # small pause at end of each segment
        for _ in range(4):
            frames.append(frames[-1].copy())

    return frames


def main():
    os.makedirs("dist", exist_ok=True)

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
