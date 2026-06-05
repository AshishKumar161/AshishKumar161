import json
import math
import os
import random
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

MAX_RANDOM_STEPS = 700
EXTRA_STEPS_AFTER_ALL_EATEN = 40
TARGET_CHASE_CHANCE = 0.78

INITIAL_SNAKE_LENGTH = 12
GROW_PER_FOOD = 5
MAX_GROW_FROM_ONE_DAY = 10
MAX_SNAKE_LENGTH = 180

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
            "User-Agent": "random-no-overlap-snake",
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


def choose_start(cols, rows, food_cells):
    if food_cells:
        fx, fy = random.choice(list(food_cells))
        candidates = neighbors((fx, fy), cols, rows)
        if candidates:
            return random.choice(candidates)
    return (random.randint(0, cols - 1), random.randint(0, rows - 1))


def build_non_overlapping_cell_path(cols, rows, counts):
    food_cells = {cell for cell, count in counts.items() if count > 0}

    head = choose_start(cols, rows, food_cells)
    body = deque([head])
    body_set = {head}
    eaten = set()
    path = [head]

    snake_length = INITIAL_SNAKE_LENGTH
    previous = None
    target = None
    extra_steps = 0

    for _ in range(MAX_RANDOM_STEPS):
        if head in food_cells and head not in eaten:
            eaten.add(head)
            snake_length += GROW_PER_FOOD + min(counts.get(head, 0), MAX_GROW_FROM_ONE_DAY)
            snake_length = min(snake_length, MAX_SNAKE_LENGTH)

        remaining_food = list(food_cells - eaten)

        if not remaining_food:
            extra_steps += 1
            if extra_steps >= EXTRA_STEPS_AFTER_ALL_EATEN:
                break
            target = None
        else:
            if target not in remaining_food or random.random() < 0.20:
                remaining_food.sort(key=lambda cell: manhattan(head, cell))
                target = random.choice(remaining_food[:min(8, len(remaining_food))])

        next_moves = neighbors(head, cols, rows)

        # avoid current body overlap
        filtered = [cell for cell in next_moves if cell not in body_set]

        # if no move found, allow tail cell because tail can move away next step
        if not filtered and len(body) > 1:
            tail = body[0]
            filtered = [cell for cell in next_moves if cell == tail]

        if not filtered:
            break

        # avoid immediate backtracking when possible
        non_back = [cell for cell in filtered if cell != previous]
        if non_back:
            filtered = non_back

        if target and random.random() < TARGET_CHASE_CHANCE:
            best_dist = min(manhattan(cell, target) for cell in filtered)
            best_moves = [cell for cell in filtered if manhattan(cell, target) == best_dist]
            next_head = random.choice(best_moves)
        else:
            next_head = random.choice(filtered)

        previous = head
        head = next_head

        body.append(head)
        body_set.add(head)
        path.append(head)

        while len(body) > snake_length:
            removed = body.popleft()
            body_set.remove(removed)

    return path


def smooth_points(cell_path):
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

    # oval head
    head_w = 9
    head_h = 7

    draw.ellipse(
        [hx - head_w, hy - head_h, hx + head_w, hy + head_h],
        fill=SNAKE_HEAD,
    )

    draw.ellipse(
        [hx - 5, hy - 4, hx + 5, hy + 4],
        fill=SNAKE_HEAD_INNER,
    )

    # eyes
    for side in (-1, 1):
        ex = hx + dx * 3.2 + nx * 2.6 * side
        ey = hy + dy * 3.2 + ny * 2.6 * side
        draw.ellipse([ex - 1.4, ey - 1.4, ex + 1.4, ey + 1.4], fill=WHITE)
        draw.ellipse([ex - 0.5, ey - 0.5, ex + 0.5, ey + 0.5], fill=BLACK)

    # tongue
    sx = hx + dx * 7
    sy = hy + dy * 7
    mx = hx + dx * 11
    my = hy + dy * 11
    left_x = mx + nx * 1.5
    left_y = my + ny * 1.5
    right_x = mx - nx * 1.5
    right_y = my - ny * 1.5

    draw.line([(sx, sy), (mx, my)], fill=TONGUE, width=2)
    draw.line([(mx, my), (left_x, left_y)], fill=TONGUE, width=1)
    draw.line([(mx, my), (right_x, right_y)], fill=TONGUE, width=1)


def draw_snake(draw, body_points):
    if len(body_points) < 2:
        return

    draw.line(body_points, fill=SNAKE_OUTER, width=10, joint="curve")
    draw.line(body_points, fill=SNAKE_INNER, width=6, joint="curve")

    # tail
    tx, ty = body_points[0]
    draw.ellipse([tx - 3.5, ty - 3.5, tx + 3.5, ty + 3.5], fill=SNAKE_INNER)

    # head direction
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

    cell_path = build_non_overlapping_cell_path(cols, rows, counts)
    points, cell_at_frame = smooth_points(cell_path)

    frames = []
    eaten = set()
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

    return frames


def main():
    os.makedirs("dist", exist_ok=True)

    random.seed()

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
