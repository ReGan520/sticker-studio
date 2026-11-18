"""Build a local WeChat album with a configurable submission profile."""

import json
import re
from datetime import date
from io import BytesIO
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageFilter, ImageOps, ImageSequence

from animation import save_gif
from render import input_path

DRAFT_PROFILE = {
    "counts": [8, 12, 16, 20, 24],
    "allowed_kinds": ["png", "gif"],
    "allow_mixed": False,
    "outline_px": 2,
    "title_chars": 8,
    "meaning_chars": 4,
    "main": {"size": [240, 240], "bytes": 100_000, "transparent": True},
    "thumbnail": {"size": [120, 120], "bytes": 50_000, "transparent": True},
    "banner": {"size": [750, 400], "bytes": 80_000, "transparent": False, "format": "jpg"},
    "cover": {"size": [240, 240], "bytes": 80_000, "transparent": True, "format": "png"},
    "icon": {"size": [50, 50], "bytes": 30_000, "transparent": True, "format": "png"},
}

ROLES = ("main", "thumbnail", "banner", "cover", "icon")
EXTRAS = ("reward_guide", "reward_thanks")


def profile_for(config):
    custom = config.get("profile", {})
    if not isinstance(custom, dict):
        raise ValueError("wechat.profile 必须是对象")
    keys = set(DRAFT_PROFILE) | {"verified_on", "source", "description_chars"} | set(EXTRAS)
    unknown = set(custom) - keys
    if unknown:
        raise ValueError(f"未知微信配置字段：{', '.join(sorted(unknown))}")
    profile = dict(DRAFT_PROFILE)
    for key, value in custom.items():
        if key in ROLES + EXTRAS:
            if not isinstance(value, dict):
                raise ValueError(f"微信配置 {key} 必须是对象")
            profile[key] = {**DRAFT_PROFILE.get(key, {}), **value}
        else:
            profile[key] = value

    if "verified_on" in custom or "source" in custom:
        if not isinstance(custom.get("source"), str) or not custom["source"].strip():
            raise ValueError("经核对的配置须提供官方规则链接或上传表单来源")
        try:
            date.fromisoformat(custom.get("verified_on", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("微信 verified_on 须使用 YYYY-MM-DD") from exc
    if not isinstance(profile["allow_mixed"], bool):
        raise ValueError("微信 allow_mixed 必须是布尔值")
    if (not isinstance(profile["counts"], list) or not profile["counts"]
            or any(type(n) is not int or not 1 <= n <= 100 for n in profile["counts"])):
        raise ValueError("微信 counts 须为 1–100 的整数列表")
    if (not isinstance(profile["allowed_kinds"], list) or not profile["allowed_kinds"]
            or any(kind not in ("png", "gif") for kind in profile["allowed_kinds"])):
        raise ValueError("微信 allowed_kinds 须为 png、gif 或两者")
    for name in ("outline_px", "title_chars", "meaning_chars", "description_chars"):
        if name in profile and (type(profile[name]) is not int or profile[name] < (0 if name == "outline_px" else 1)):
            raise ValueError(f"微信 {name} 的取值无效")
    if profile["outline_px"] > 8:
        raise ValueError("微信 outline_px 须为 0–8 的整数")
    for role in (*ROLES, *(role for role in EXTRAS if role in profile)):
        rule = profile[role]
        size, limit, transparent = rule.get("size"), rule.get("bytes"), rule.get("transparent")
        if (set(rule) - {"size", "bytes", "transparent", "format"}
                or not isinstance(size, list) or len(size) != 2
                or any(type(n) is not int or not 1 <= n <= 4096 for n in size)
                or type(limit) is not int or limit < 1
                or type(transparent) is not bool):
            raise ValueError(f"微信 {role} 需要有效的 size、bytes 和 transparent")
        kind = rule.get("format")
        if role == "main":
            if kind is not None or size[0] != size[1]:
                raise ValueError("微信 main 使用方形画布，格式由 allowed_kinds 定义")
        elif role == "thumbnail":
            if kind not in (None, "png"):
                raise ValueError("微信 thumbnail 使用 PNG")
        elif kind not in ("png", "jpg") or (transparent and kind == "jpg"):
            raise ValueError(f"微信 {role} 格式必须为 PNG 或不透明 JPG")
    return profile


def require_text(value, label, limit=None):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"请填写微信{label}")
    value = value.strip()
    if limit is not None and len(value) > limit:
        raise ValueError(f"微信{label}超过配置的 {limit} 字")
    return value


def prepare(image, rule, *, fill=False, pixel_art=False):
    size = tuple(rule["size"])
    method = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    if fill:
        if image.getchannel("A").getextrema()[0] != 255:
            raise ValueError("不透明投稿配图须提供带完整背景的原画")
        return ImageOps.fit(image, size, method)
    art = ImageOps.contain(image, size, method)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0) if rule["transparent"] else (255, 255, 255, 255))
    canvas.alpha_composite(art, ((size[0] - art.width) // 2, (size[1] - art.height) // 2))
    return canvas


def outline(frame, px):
    if not px:
        return frame
    alpha = frame.getchannel("A")
    layer = Image.new("RGBA", frame.size, "white")
    layer.putalpha(alpha.filter(ImageFilter.MaxFilter(2 * px + 1)))
    return Image.alpha_composite(layer, frame)


def save_still(image, path, rule):
    if path.suffix == ".jpg":
        candidates = ((image.convert("RGB"), {"quality": q, "optimize": True}) for q in (94, 88, 80, 72, 60))
        fmt = "JPEG"
    else:
        reduced = (
            (image.quantize(colors=n, method=Image.Quantize.FASTOCTREE).convert("RGBA"), {"optimize": True})
            for n in (192, 128, 64)
        )
        candidates = chain(((image, {"optimize": True}),), reduced)
        fmt = "PNG"
    for candidate, options in candidates:
        buffer = BytesIO()
        candidate.save(buffer, format=fmt, **options)
        if buffer.tell() <= rule["bytes"]:
            path.write_bytes(buffer.getvalue())
            return
    raise ValueError(f"{path.name} 超过 {rule['bytes']} 字节，请优化源图或核对微信配置")


def inspect(path, rule, *, animated=False):
    fmt = {".jpg": "JPEG", ".png": "PNG", ".gif": "GIF"}[path.suffix]
    with Image.open(path) as image:
        if image.format != fmt or list(image.size) != rule["size"] or path.stat().st_size > rule["bytes"]:
            raise ValueError(f"{path.name} 的实际格式、尺寸或体积不符合配置")
        frames = getattr(image, "n_frames", 1)
        if animated and (frames < 2 or image.info.get("loop") != 0):
            raise ValueError(f"{path.name} 需要包含多帧和永久循环设置")
        durations = []
        for frame in ImageSequence.Iterator(image):
            alpha = frame.convert("RGBA").getchannel("A")
            low, high = alpha.getextrema()
            if high == 0 or low != (0 if rule["transparent"] else 255):
                raise ValueError(f"{path.name} 的透明背景不符合配置")
            if animated:
                durations.append(frame.info.get("duration", 0))
        if animated and any(ms <= 0 for ms in durations):
            raise ValueError(f"{path.name} 存在无效帧时长")
    return {"format": fmt, "size": rule["size"], "bytes": path.stat().st_size, "frames": frames,
            "duration_ms": sum(durations)}


def export_wechat(root: Path, pack: dict, output: Path):
    config = pack.get("wechat")
    if not isinstance(config, dict):
        raise ValueError("请按 references/wechat.md 填写 pack.wechat")
    profile = profile_for(config)
    recorded = "verified_on" in profile
    items = pack["items"]
    kinds = {item["kind"] for item in items}
    if (len(items) not in profile["counts"] or not kinds.issubset(profile["allowed_kinds"])
            or (len(kinds) > 1 and not profile["allow_mixed"])):
        raise ValueError("当前表情数量、文件格式或混合类型不符合微信配置")
    title = require_text(config.get("title"), "专辑名称", profile["title_chars"])
    description = require_text(config.get("description"), "专辑介绍", profile.get("description_chars"))
    thumbnails = config.get("thumbnails", {})
    if not isinstance(thumbnails, dict) or set(thumbnails) - {item["id"] for item in items}:
        raise ValueError("wechat.thumbnails 必须按有效表情 ID 提供关键帧索引或自备透明图路径")
    destination = output / "wechat"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError("微信导出目录须为项目内的普通文件夹")
    with TemporaryDirectory(prefix=".wechat-", dir=output) as temporary:
        stage = Path(temporary) / "wechat"
        (stage / "main").mkdir(parents=True)
        (stage / "thumbnails").mkdir()
        manifest = {}
        meanings = []
        for index, item in enumerate(items, start=1):
            item_id, kind = item["id"], item["kind"]
            if re.fullmatch(r"[A-Za-z0-9_-]+", item_id) is None:
                raise ValueError("微信表情 ID 含有无效字符")
            filename = f"{index:02d}"
            meanings.append(f"{filename}：{require_text(item.get('meaning') or item.get('caption'), f'{item_id} 含义词', profile['meaning_chars'])}")
            source = input_path(output, f"{item_id}.{kind}")
            main = stage / "main" / f"{filename}.{kind}"
            with Image.open(source) as image:
                if image.format != kind.upper():
                    raise ValueError(f"{source.name} 内容与文件扩展名不符")
                if kind == "gif" and image.info.get("loop") != 0:
                    raise ValueError(f"{item_id} 需在通用项目中设置永久循环再导出")
                frames = [
                    prepare(frame.convert("RGBA"), profile["main"], pixel_art=item.get("pixel_art", False))
                    for frame in ImageSequence.Iterator(image)
                ]
                durations = [frame.info.get("duration", 0) for frame in ImageSequence.Iterator(image)]
            main_frames = [outline(frame, profile["outline_px"]) for frame in frames]
            if kind == "gif":
                for colors in (255, 127, 63, 31):
                    save_gif(main_frames, durations, "repeat", main, colors=colors)
                    if main.stat().st_size <= profile["main"]["bytes"]:
                        break
            else:
                save_still(main_frames[0], main, profile["main"])
            thumb = stage / "thumbnails" / f"{filename}.png"
            selected = thumbnails.get(item_id, 0)
            if isinstance(selected, str):
                with Image.open(input_path(root, selected)) as image:
                    thumb_art = ImageOps.exif_transpose(image).convert("RGBA")
            elif type(selected) is int and 0 <= selected < len(frames):
                thumb_art = frames[selected]
            else:
                raise ValueError(f"{item_id} 的缩略图帧索引无效")
            save_still(prepare(thumb_art, profile["thumbnail"], pixel_art=item.get("pixel_art", False)),
                       thumb, profile["thumbnail"])
            manifest[main.relative_to(stage).as_posix()] = inspect(main, profile["main"], animated=kind == "gif")
            if kind == "gif" and manifest[main.relative_to(stage).as_posix()]["duration_ms"] != sum(durations):
                raise ValueError(f"{item_id} 的 GIF 导出没有保留原始总时长")
            manifest[thumb.relative_to(stage).as_posix()] = inspect(thumb, profile["thumbnail"])
        for role in ("banner", "cover", "icon", *(role for role in EXTRAS if role in profile)):
            entry = require_text(config.get(role), f"{role} 素材路径")
            rule = profile[role]
            path = stage / f"{role}.{rule['format']}"
            with Image.open(input_path(root, entry)) as source:
                art = ImageOps.exif_transpose(source).convert("RGBA")
            save_still(prepare(art, rule, fill=not rule["transparent"]), path, rule)
            manifest[path.name] = inspect(path, rule)

        status = ("已记录表单来源，本地技术检查通过。请对照表单确认沿用的默认值。"
                  if recorded else "草稿，通过本地制作配置，待核对官方表单")
        listing = f"# 微信专辑信息\n\n{status}\n\n## 专辑名称\n\n{title}\n\n## 专辑介绍\n\n{description}\n\n## 表情含义词\n\n" + "\n".join(meanings) + "\n"
        if config.get("reward_copy"):
            listing += "\n## 赞赏文案\n\n" + require_text(config["reward_copy"], "赞赏文案") + "\n"
        (stage / "listing.md").write_text(listing, encoding="utf-8")
        report = {"status": "local-pass-recorded-profile" if recorded else "local-pass-draft",
                  "profile": profile, "profile_overrides": config.get("profile", {}), "files": manifest}
        (stage / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with ZipFile(stage / "wechat.zip", "w", compression=ZIP_DEFLATED) as archive:
            for name in (*manifest, "listing.md", "validation.json"):
                archive.write(stage / name, name)
        # Preserve the previous package if the staged replacement fails.
        backup = Path(temporary) / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            stage.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
    return report
