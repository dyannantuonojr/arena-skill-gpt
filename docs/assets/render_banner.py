"""Render the README's original dot-matrix GIF. Requires Pillow; no network calls."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = {
    'A': ['01110', '11011', '11011', '11111', '11011', '11011', '11011'],
    'C': ['01111', '11000', '11000', '11000', '11000', '11000', '01111'],
    'D': ['11110', '11011', '11011', '11011', '11011', '11011', '11110'],
    'E': ['11111', '11000', '11000', '11110', '11000', '11000', '11111'],
    'G': ['01111', '11000', '11000', '11011', '11011', '11011', '01111'],
    'H': ['11011', '11011', '11011', '11111', '11011', '11011', '11011'],
    'M': ['10001', '11011', '11111', '10101', '10001', '10001', '10001'],
    'N': ['11001', '11001', '11101', '11111', '11011', '11011', '11011'],
    'R': ['11110', '11011', '11011', '11110', '11100', '11010', '11011'],
    'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
    'U': ['11011', '11011', '11011', '11011', '11011', '11011', '01110'],
    ' ': ['00000'] * 7,
    '+': ['00000', '00100', '00100', '11111', '00100', '00100', '00000'],
}


def title(draw, text, x, color, phase):
    for char_index, char in enumerate(text):
        for row, bits in enumerate(FONT[char]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    pulse = 0.90 + 0.10 * math.sin(phase - char_index * 0.5)
                    fill = tuple(round(c * pulse) for c in color)
                    left, top = x + char_index * 42 + col * 7, 37 + row * 8
                    draw.rounded_rectangle((left, top, left + 5, top + 6), radius=1, fill=fill)


def render():
    frames = []
    font = ImageFont.load_default(size=16)
    small = ImageFont.load_default(size=12)
    for index in range(24):
        phase = 2 * math.pi * index / 24
        image = Image.new('RGB', (1000, 200), '#0c1117')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 999, 199), radius=13, outline='#303944', width=1)
        title(draw, 'ARENA', 122, (238, 133, 104), phase)
        title(draw, '+', 352, (128, 144, 157), phase)
        title(draw, 'GRUDGE MATCH', 420, (18, 190, 146), phase)
        draw.text((500, 118), 'one question  /  independent answers  /  stronger reasoning',
                  fill='#9aa7b4', font=font, anchor='mm')
        draw.text((500, 162), 'WORK IN PROGRESS  ·  GPT / CODEX',
                  fill='#748392', font=small, anchor='mm')
        for dot in range(16):
            active = (dot - index // 2) % 16 < 3
            draw.rounded_rectangle((425 + dot * 10, 181, 429 + dot * 10, 184), radius=1,
                                   fill='#16bd92' if active else '#27333d')
        frames.append(image)
    path = Path(__file__).with_name('arena-grudge-match.gif')
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=120,
                   loop=0, optimize=True, disposal=2)
    frames[0].save(path.with_suffix('.png'))
    print(path)


if __name__ == '__main__':
    render()

