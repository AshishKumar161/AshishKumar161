import json
import math
import os
import random
import urllib.request
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

# =========================================================
# RANDOM REAL GITHUB CONTRIBUTION GROWING SNAKE
# =========================================================

GITHUB_USER_NAME = os.environ.get("GITHUB_USER_NAME", "AshishKumar161")

# 53 = full year, 26 = half year
LAST_WEEKS = 53

# Clean full-year layout for README
CELL = 10
GAP = 3
PADDING_X = 20
PADDING_Y = 20

# Smooth movement
FRAMES_PER_CELL = 4
FRAME_DURATION_MS = 45

# Random movement behavior
MAX_RANDOM_STEPS = 520
EXTRA_STEPS_AFTER_ALL_EATEN = 45
TARGET_CHASE_CHANCE = 0.62
RANDOM_MOVE_CHANCE = 0.38

# Snake growth
INITIAL_SNAKE_LENGTH = 28
GROW_PER_FOOD = 5
MAX_GROW_FROM_ONE_DAY = 10
MAX_SNAKE_LENGTH = 230

# Colors
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
SNAKE_HEAD = (180, 0, 255)
SNAKE_HEAD_INNER = (245, 140, 255)
WHITE = (255, 255, 255)
TONGUE = (255, 0, 110)


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
            "User-Agent": "random-real-growing-snake",
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
    possible = []

    if x > 0:
        possible.append((x - 1, y))
    if x < cols - 1:
        possible.append((x + 1, y))
    if y > 0:
        possible.append((x, y - 1))
    if y < rows - 1:
        possible.append((x, y + 1))

    return possible


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def choose_random_start(cols, rows, food_cells):
    if food_cells:
        # Start near a real contribution block, but not always on it.
        fx, fy = random.choice(list(food_cells))
        options = neighbors((fx, fy), cols, rows)
        if options:
            return random.choice(options)

    return (random.randint(0, cols - 1), random.randint(0, rows - 1))


def build_random_path(cols, rows, counts):
    food_cells = {cell for cell, count in counts.items() if count > 0}

    current = choose_random_start(cols, rows, food_cells)
    previous = None
    path = [current]
    eaten = set()

    target = random.choice(list(food_cells)) if food_cells else None
    after_finish_steps = 0

    for _ in range(MAX_RANDOM_STEPS):
        if current in food_cells:
            eaten.add(current)

        remaining_food = list(food_cells - eaten)

        if not remaining_food:
            after_finish_steps += 1
            if after_finish_steps >= EXTRA_STEPS_AFTER_ALL_EATEN:
                break
            target = None
        else:
            # Change target sometimes so movement looks less robotic.
            if target not in remaining_food or random.random() < 0.18:
                # Prefer one of the nearer contribution blocks, but still random.
                remaining_food.sort(key=lambda c: manhattan(current, c))
                target = random.choice(remaining_food[:min(8, len(remaining_food))])

        moves = neighbors(current, cols, rows)

        # Avoid immediately going backward when possible.
        non_backtracking = [m for m in moves if m != previous]
        if non_backtracking:
            moves = non_backtracking

        next_cell = None

        if target and random.random() < TARGET_CHASE_CHANCE:
            best_distance = min(manhattan(m, target) for m in moves)
            best_moves = [m for m in moves if manhattan(m, target) == best_distance]

            # Add randomness even while chasing.
            if random.random() < RANDOM_MOVE_CHANCE:
                next_cell = random.choice(moves)
            else:
                next_cell = random.choice(best_moves)
        else:
            next_cell = random.choice(moves)

        previous = current
        current = next_cell
        path.append(current)

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

            points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
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


def draw_snake(draw, body_points):
    if len(body_points) < 2:
        return

    # Continuous snake body.
    draw.line(body_points, fill=SNAKE_OUTER, width=10, joint="curve")
    draw.line(body_points, fill=SNAKE_INNER, width=6, joint="curve")

    # Tail.
    tx, ty = body_points[0]
    draw.ellipse([tx - 3.5, ty - 3.5, tx + 3.5, ty + 3.5], fill=SNAKE_INNER)

    # Head.
    hx, hy = body_points[-1]
    px, py = body_points[-2]

    dx = hx - px
    dy = hy - py
    distance = math.hypot(dx, dy) or 1

    dx /= distance
    dy /= distance

    nx = -dy
    ny = dx

    head_radius = 8
    draw.ellipse(
        [hx - head_radius, hy - head_radius, hx + head_radius, hy + head_radius],
        fill=SNAKE_HEAD,
    )

    inner_radius = 5
    draw.ellipse(
        [hx - inner_radius, hy - inner_radius, hx + inner_radius, hy + inner_radius],
        fill=SNAKE_HEAD_INNER,
    )

    # Eyes.
    for side in (-1, 1):
        ex = hx + dx * 3.8 + nx * 3.0 * side
        ey = hy + dy * 3.8 + ny * 3.0 * side
        draw.ellipse([ex - 1.3, ey - 1.3, ex + 1.3, ey + 1.3], fill=WHITE)

    # Tongue.
    start = (hx + dx * 7, hy + dy * 7)
    end = (hx + dx * 12, hy + dy * 12)
    draw.line([start, end], fill=TONGUE, width=2)


def create_frames(cols, rows, counts):
    width = PADDING_X * 2 + cols * CELL + (cols - 1) * GAP
    height = PADDING_Y * 2 + rows * CELL + (rows - 1) * GAP

    random_cell_path = build_random_path(cols, rows, counts)
    points, cell_at_frame = smooth_points(random_cell_path)

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

    # Different random path each workflow run.
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
