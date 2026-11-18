import json
from pathlib import Path

from jsonschema import Draft202012Validator
from PIL import Image, UnidentifiedImageError

from render import input_path

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def read_json(path, schema):
    data = json.loads(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(json.loads((SCHEMAS / f"{schema}.schema.json").read_text()))
    error = next(validator.iter_errors(data), None)
    if error:
        location = ".".join(map(str, error.absolute_path))
        raise ValueError(f"{path.name} {location}：{error.message}")
    return data


def read_pack(root):
    pack = read_json(input_path(root, "pack.json"), "pack")
    identifiers = [item["id"] for item in pack["items"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("表情编号重复")
    if "character" in pack:
        path = input_path(root, pack["character"])
        character = read_json(path, "character")
        for key in ("reference", "expression_sheet"):
            if key in character:
                input_path(path.parent, character[key])
    return pack


def expected_files(item):
    yield f"{item['id']}.{item['kind']}", item
    if item.get("no_text_copy") and item.get("caption", "").strip():
        yield f"{item['id']}-no-text.{item['kind']}", {**item, "caption": ""}


def inspect(path, item, size):
    result = {"file": path.name, "errors": []}
    errors = result["errors"]
    if not path.is_file():
        errors.append("缺少导出文件")
        return result
    try:
        with Image.open(path) as image:
            count = image.n_frames
            result.update(bytes=path.stat().st_size, dimensions=list(image.size), frames=count)
            if image.format != item["kind"].upper() or image.size != (size, size):
                errors.append("导出格式或尺寸不符")
            if item["kind"] == "gif":
                if count < 2:
                    errors.append("GIF 有效画面少于两帧")
                loop = image.info.get("loop")
                result["loop"] = loop
                if loop != (0 if item.get("loop", "repeat") == "repeat" else None):
                    errors.append("GIF 循环设置不符")
            durations = []
            for index in range(count):
                image.seek(index)
                alpha = image.convert("RGBA").getchannel("A")
                box = alpha.getbbox()
                if box is None or alpha.getextrema()[0] != 0:
                    errors.append(f"第 {index + 1} 帧缺少可见主体或透明背景")
                elif box[0] == 0 or box[1] == 0 or box[2] == size or box[3] == size:
                    errors.append(f"第 {index + 1} 帧贴到画布边缘")
                durations.append(image.info.get("duration", 0))
            if item["kind"] == "gif":
                source = item["frames"] if "frames" in item else item["layers"][0]["poses"]
                result["duration_ms"] = sum(durations)
                if min(durations) < 20 or sum(durations) != sum(pose["ms"] for pose in source):
                    errors.append("GIF 帧时长或总时长不符")
    except (OSError, EOFError, UnidentifiedImageError) as error:
        errors.append(f"图像无法完整解码：{error}")
    return result
