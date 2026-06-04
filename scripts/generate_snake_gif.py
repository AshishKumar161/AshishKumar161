from PIL import Image, ImageDraw
import os

COLS = 52
ROWS = 7
CELL = 14
GAP = 4
PADDING_X = 20
PADDING_Y = 20

BG = (13, 17, 23)
GRID = (22, 27, 34)
BODY = (0, 255, 65)
HEAD = (180, 0, 255)
FOOD = (57, 211, 83)
BORDER = (0, 120, 40)

FRAME_REPEAT_NORMAL = 2
FRAME_REPEAT_EAT = 5
DURATION = 100

PATH = [
    (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3),
    (11, 3), (12, 3), (13, 3), (14, 3), (15, 3), (16, 3), (17, 3), (18, 3),
    (18, 2), (19, 2), (20, 2), (21, 2), (22, 2), (23, 2), (24, 2), (25, 2),
    (25, 3), (26, 3), (27, 3), (28, 3), (29, 3), (30, 3), (31, 3), (32, 3),
    (32, 4), (33, 4), (34, 4), (35, 4), (36, 4), (37, 4), (38, 4), (39, 4),
    (39, 3), (40, 3), (41, 3), (42, 3), (43, 3), (44, 3), (45, 3), (46, 3),
    (47, 3), (48, 3)
]

FOOD_POINTS = {
    (8, 3),
    (18, 2),
    (25, 3),
    (32, 4),
    (39, 3),
    (46, 3),
}

INITIAL_LENGTH = 4


def cell_rect(x, y):
    left = PADDING_X + x * (CELL + GAP)
    top = PADDING_Y + y * (CELL + GAP)
    return [left, top, left + CELL, top + CELL]


def draw_grid(draw):
    for y in range(ROWS):
        for x in range(COLS):
            draw.rounded_rectangle(cell_rect(x, y), radius=3, fill=GRID)


def draw_food(draw, foods):
    for fx, fy in foods:
        rect = cell_rect(fx, fy)
        glow = [rect[0] - 1, rect[1] - 1, rect[2] + 1, rect[3] + 1]
        draw.rounded_rectangle(glow, radius=4, fill=(0, 80, 20))
        draw.rounded_rectangle(rect, radius=3, fill=FOOD)


def draw_snake(draw, body):
    for i, (sx, sy) in enumerate(body):
        rect = cell_rect(sx, sy)
        color = BODY if i < len(body) - 1 else HEAD
        draw.rounded_rectangle(rect, radius=3, fill=color)

        inner = [rect[0] + 3, rect[1] + 3, rect[2] - 3, rect[3] - 3]

        if i < len(body) - 1:
            draw.rounded_rectangle(inner, radius=2, fill=(0, 190, 50))
        else:
            draw.rounded_rectangle(inner, radius=2, fill=(220, 90, 255))


def generate_frames():
    width = PADDING_X * 2 + COLS * CELL + (COLS - 1) * GAP
    height = PADDING_Y * 2 + ROWS * CELL + (ROWS - 1) * GAP

    frames = []
    length = INITIAL_LENGTH
    eaten = set()

    for i, head in enumerate(PATH):
        just_ate = False

        if head in FOOD_POINTS and head not in eaten:
            eaten.add(head)
            length += 1
            just_ate = True

        start = max(0, i - length + 1)
        body = PATH[start:i + 1]

        img = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [2, 2, width - 3, height - 3],
            radius=10,
            outline=BORDER,
            width=2
        )

        draw_grid(draw)
        draw_food(draw, FOOD_POINTS - eaten)
        draw_snake(draw, body)

        repeat = FRAME_REPEAT_EAT if just_ate else FRAME_REPEAT_NORMAL

        for _ in range(repeat):
            frames.append(img.copy())

    return frames


def save_gif():
    os.makedirs("dist", exist_ok=True)
    frames = generate_frames()

    frames[0].save(
        "dist/custom-snake.gif",
        save_all=True,
        append_images=frames[1:],
        duration=DURATION,
        loop=0,
        optimize=False,
        disposal=2,
    )

    frames[0].save("dist/custom-snake-preview.png")


if __name__ == "__main__":
    save_gif()
    print("Generated custom snake GIF")
