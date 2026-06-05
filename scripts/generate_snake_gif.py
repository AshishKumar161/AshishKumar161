import json
import math
import os
import urllib.request
from datetime import date
from PIL import Image, ImageDraw

GITHUB_USER_NAME = os.environ.get("GITHUB_USER_NAME", "AshishKumar161")
LAST_WEEKS = 26

CELL = 14
GAP = 5
PADDING_X = 24
PADDING_Y = 24

FRAMES_PER_CELL = 5
FRAME_DURATION_MS = 45

INITIAL_SNAKE_LENGTH = 18
GROW_PER_FOOD = 4
MAX_EXTRA_GROW = 8

BG = (13, 17, 23)
GRID_EMPTY = (22, 27, 34)
GRID_BORDER = (0, 110, 55)

LEVEL_COLORS = [
    (22, 27, 34),
    (14, 68, 41),
    (0, 109, 50),
    (38, 166, 65),
    (57, 211, 83),
]

SNAKE_BODY = (0, 255, 65)
SNAKE_BODY_DARK = (0, 150, 55)
SNAKE_HEAD = (185, 0, 255)
SNAKE_HEAD_INNER = (235, 110, 255)
FOOD_GLOW = (0, 255, 65)


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

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "real-contribution-snake-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as response:
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


def center_of_cell(x, y):
    cx = PADDING_X + x * (CELL + GAP) + CELL / 2
    cy = PADDING_Y + y * (CELL + GAP) + CELL / 2
    return cx, cy


def cell_rect(x, y):
    left = PADDING_X + x * (CELL + GAP)
    top = PADDING_Y + y * (CELL + GAP)
    return [left, top, left + CELL, top + CELL]


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


def build_serpentine_path(cols, rows):
    path = []

    for x in range(cols):
        if x % 2 == 0:
            yrange = range(rows)
        else:
            yrange = range(rows - 1, -1, -1)

        for y in yrange:
            path.append((x, y))

    return path


def interpolate_path(cell_path):
    points = []
    cells_for_frame = []

    for i in range(len(cell_path) - 1):
        x1, y1 = center_of_cell(*cell_path[i])
        x2, y2 = center_of_cell(*cell_path[i + 1])

        for step in range(FRAMES_PER_CELL):
            t = step / FRAMES_PER_CELL
            smooth = t * t * (3 - 2 * t)

            px = x1 + (x2 - x1) * smooth
            py = y1 + (y2 - y1) * smooth

            points.append((px, py))
            cells_for_frame.append(cell_path[i])

    points.append(center_of_cell(*cell_path[-1]))
    cells_for_frame.append(cell_path[-1])

    return points, cells_for_frame


def draw_background(draw, width, height):
    draw.rounded_rectangle(
        [2, 2, width - 3, height - 3],
        radius=16,
        fill=BG,
        outline=GRID_BORDER,
        width=2,
    )


def draw_grid(draw, cols, rows, counts, eaten):
    for y in range(rows):
        for x in range(cols):
            count = counts.get((x, y), 0)

            if (x, y) in eaten:
                fill = GRID_EMPTY
            else:
                fill = LEVEL_COLORS[count_to_level(count)]

            draw.rounded_rectangle(cell_rect(x, y), radius=4, fill=fill)

            if count > 0 and (x, y) not in eaten:
                rect = cell_rect(x, y)
                glow = [rect[0] - 2, rect[1] - 2, rect[2] + 2, rect[3] + 2]
                draw.rounded_rectangle(glow, radius=5, outline=FOOD_GLOW, width=1)


def draw_snake(draw, body_points):
    if len(body_points) < 2:
        return

    sampled = body_points[::2]

    if sampled[-1] != body_points[-1]:
        sampled.append(body_points[-1])

    n = max(1, len(sampled) - 1)

    for i, (x, y) in enumerate(sampled):
        progress = i / n

        radius = 2.2 + progress * 5.4
        green = int(SNAKE_BODY_DARK[1] + progress * (SNAKE_BODY[1] - SNAKE_BODY_DARK[1]))
        fill = (0, green, 65)

        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=fill,
        )

    hx, hy = body_points[-1]
    px, py = body_points[-2]

    dx = hx - px
    dy = hy - py

    length = math.hypot(dx, dy) or 1
    dx /= length
    dy /= length

    nx = -dy
    ny = dx

    head_r = 8.8

    draw.ellipse(
        [hx - head_r, hy - head_r, hx + head_r, hy + head_r],
        fill=SNAKE_HEAD,
    )

    inner_r = 5.2

    draw.ellipse(
        [hx - inner_r, hy - inner_r, hx + inner_r, hy + inner_r],
        fill=SNAKE_HEAD_INNER,
    )

    eye_forward = 3.6
    eye_side = 3.0

    for side in (-1, 1):
        ex = hx + dx * eye_forward + nx * eye_side * side
        ey = hy + dy * eye_forward + ny * eye_side * side

        draw.ellipse(
            [ex - 1.4, ey - 1.4, ex + 1.4, ey + 1.4],
            fill=(255, 255, 255),
        )


def create_frames(cols, rows, counts):
    width = PADDING_X * 2 + cols * CELL + (cols - 1) * GAP
    height = PADDING_Y * 2 + rows * CELL + (rows - 1) * GAP

    cell_path = build_serpentine_path(cols, rows)
    points, cells_for_frame = interpolate_path(cell_path)

    frames = []
    eaten = set()
    snake_length = INITIAL_SNAKE_LENGTH

    for index, head_point in enumerate(points):
        head_cell = cells_for_frame[index]
        count = counts.get(head_cell, 0)

        if count > 0 and head_cell not in eaten:
            eaten.add(head_cell)
            snake_length += GROW_PER_FOOD + min(count, MAX_EXTRA_GROW)

        start = max(0, index - snake_length)
        body_points = points[start:index + 1]

        img = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)

        draw_background(draw, width, height)
        draw_grid(draw, cols, rows, counts, eaten)
        draw_snake(draw, body_points)

        frames.append(img)

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
