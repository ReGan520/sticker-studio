import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from animation import animation_frames, save_gif
from preview import make_preview
from render import caption_layer, load_art, place_art
from validate import expected_files, inspect, read_pack


def render_item(root, pack, item, target):
    size = pack.get("size", 320)
    text = caption_layer(root, pack, item, size)
    if item["kind"] == "png":
        art = load_art(root, item["source"])
        art = art.crop(art.getbbox())
        Image.alpha_composite(place_art(art, size, item), text).save(target, optimize=True)
    else:
        frames, durations = animation_frames(root, item, size)
        frames = [Image.alpha_composite(frame, text) for frame in frames]
        save_gif(frames, durations, item.get("loop", "repeat"), target)


def verify(output, pack):
    reports = [inspect(output / name, item, pack.get("size", 320))
               for sticker in pack["items"] for name, item in expected_files(sticker)]
    report = {"passed": not any(item["errors"] for item in reports), "files": reports}
    (output / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="表情包合成及导出")
    parser.add_argument("command", choices=["build", "check", "wechat"])
    parser.add_argument("project", type=Path)
    parser.add_argument("--id", help="build 时仅重建一个表情")
    args = parser.parse_args()
    if args.id and args.command != "build":
        parser.error("--id 只用于 build")
    try:
        root = args.project.resolve()
        pack = read_pack(root)
        items = [item for item in pack["items"] if args.id is None or item["id"] == args.id]
        if not items:
            raise ValueError(f"找不到编号 {args.id}")
        names = [name for sticker in pack["items"] for name, _ in expected_files(sticker)]
        if len(set(names)) != len(names):
            raise ValueError("无字副本与另一个表情的文件名冲突")
        output = root / "export"
        if output.is_symlink():
            raise ValueError("export 必须是项目内的真实目录")
        output.mkdir(exist_ok=True)
        if args.command == "build":
            with TemporaryDirectory(dir=root) as temp:
                pending = []
                for sticker in items:
                    for name, item in expected_files(sticker):
                        target = Path(temp) / name
                        render_item(root, pack, item, target)
                        problems = inspect(target, item, pack.get("size", 320))["errors"]
                        if problems:
                            raise ValueError(f"{name}：{'；'.join(problems)}")
                        pending.append(target)
                for target in pending:
                    target.replace(output / target.name)
            make_preview(output, pack)
            report = verify(output, pack)
            if args.id:
                report = {"built": args.id, "pack_passed": report["passed"]}
        elif args.command == "wechat":
            from wechat import export_wechat
            report = export_wechat(root, pack, output)
        else:
            report = verify(output, pack)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("passed", True) else 1
    except (OSError, ValueError) as error:
        print(f"制作失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
