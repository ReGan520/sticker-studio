from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def input_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"项目内素材不存在或路径越界：{name}")
    return path


def load_art(root, name):
    with Image.open(input_path(root, name)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"素材是全透明图：{name}")
    return image


def fitted(image, size, pixel_art=False):
    resample = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    return ImageOps.contain(image, size, resample)


def canvas_size(size, item):
    margin = max(2, round(size * 0.055))
    caption_space = round(size * 0.29) if item.get("caption", "").strip() else 0
    top = margin + (caption_space if item.get("caption_position") == "top" else 0)
    return (size - 2 * margin, size - 2 * margin - caption_space), top, caption_space


def place_art(art, size, item):
    available, top, _ = canvas_size(size, item)
    art = fitted(art, available, item.get("pixel_art", False))
    result = Image.new("RGBA", (size, size))
    result.alpha_composite(art, ((size - art.width) // 2, top + (available[1] - art.height) // 2))
    return result


def caption_layer(root, pack, item, size):
    layer = Image.new("RGBA", (size, size))
    caption = item.get("caption", "").strip()
    if not caption:
        return layer
    has_cjk = any(ord(char) > 127 for char in caption)
    system_fonts = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    font_path = input_path(root, pack["font"]) if "font" in pack else next(
        (candidate for candidate in system_fonts if Path(candidate).is_file()), None
    )
    if font_path is None and has_cjk:
        raise ValueError("请在 pack.font 指定项目内覆盖文案字符的字体")
    draw = ImageDraw.Draw(layer)
    _, _, space = canvas_size(size, item)
    for font_size in range(round(size * 0.18), max(8, round(size * 0.065)) - 1, -1):
        font = (ImageFont.truetype(str(font_path), font_size, index=pack.get("font_index", 0))
                if font_path else ImageFont.load_default(size=font_size))
        stroke = max(1, round(font_size * 0.08))
        spacing = max(2, font_size // 9)
        lines = []
        for line in caption.splitlines():
            current = ""
            for char in line:
                if current and draw.textlength(current + char, font=font) > size * 0.88:
                    lines.append(current)
                    current = ""
                current += char
            lines.append(current)
        text = "\n".join(lines)
        left, top, right, bottom = draw.multiline_textbbox(
            (0, 0), text, font=font, stroke_width=stroke, spacing=spacing, align="center"
        )
        if right - left <= size * 0.92 and bottom - top <= space * 0.9:
            band_y = size * 0.055 if item.get("caption_position") == "top" else size * 0.945 - space
            position = ((size - (right - left)) / 2 - left, band_y + (space - (bottom - top)) / 2 - top)
            draw.multiline_text(position, text, font=font, fill="#fffaf1", stroke_width=stroke,
                                stroke_fill="#1a1722", spacing=spacing, align="center")
            return layer
    raise ValueError(f"{item['id']} 文案超出版面，请缩短或增加画布尺寸")
