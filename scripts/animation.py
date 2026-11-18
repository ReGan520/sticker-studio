from PIL import Image

from render import load_art, place_art


def sample_poses(layers, timeline, repeat):
    defaults = {"x": 0, "y": 0, "scale": 1, "angle": 0, "opacity": 1}
    for index, duration in enumerate(timeline):
        current = [poses[index] for _, poses in layers]
        next_index = index + 1
        if next_index == len(timeline):
            if not repeat:
                yield current, duration
                continue
            next_index = 0

        if not any("tween" in pose for pose in current):
            yield current, duration
            continue

        # GIF timing is in centiseconds. Distribute rounding across the segment.
        ticks = duration // 10
        count = max(1, (ticks + 1) // 3)
        for step in range(count):
            start = step * ticks // count
            end = (step + 1) * ticks // count
            sampled = []
            for (_, poses), pose in zip(layers, current):
                mode = pose.get("tween")
                if mode is None:
                    sampled.append(pose)
                    continue
                progress = start / ticks
                if mode == "ease-in-out":
                    progress = progress * progress * (3 - 2 * progress)
                following = poses[next_index]
                sampled.append({
                    key: pose.get(key, default) + (following.get(key, default) - pose.get(key, default)) * progress
                    for key, default in defaults.items()
                })
            yield sampled, (end - start) * 10


def animation_frames(root, item, size):
    if "frames" in item:
        images = [load_art(root, frame["source"]) for frame in item["frames"]]
        if len({image.size for image in images}) != 1:
            raise ValueError("逐帧源图必须共用注册画布尺寸")
        return [place_art(image, size, item) for image in images], [frame["ms"] for frame in item["frames"]]

    images = [load_art(root, layer["source"]) for layer in item["layers"]]
    if len({image.size for image in images}) != 1:
        raise ValueError("动效图层必须共用注册画布尺寸")
    layers = [(place_art(image, size, item), layer["poses"]) for image, layer in zip(images, item["layers"])]
    timelines = [[pose["ms"] for pose in poses] for _, poses in layers]
    if any(timeline != timelines[0] for timeline in timelines):
        raise ValueError("动效层必须共用同一帧数及帧时长")
    frames = []
    durations = []
    repeat = item.get("loop", "repeat") == "repeat"
    for sampled, duration in sample_poses(layers, timelines[0], repeat):
        frame = Image.new("RGBA", (size, size))
        for (art, _), pose in zip(layers, sampled):
            opacity = pose.get("opacity", 1)
            if opacity == 0:
                continue
            scale = pose.get("scale", 1)
            angle = pose.get("angle", 0)
            art_width = max(1, round(art.width * scale))
            resample = Image.Resampling.NEAREST if item.get("pixel_art") else Image.Resampling.BICUBIC
            transformed = art.resize((art_width, art_width), resample).rotate(angle, resample=resample, expand=True)
            position = ((size - transformed.width) // 2 + round(pose.get("x", 0)),
                        (size - transformed.height) // 2 + round(pose.get("y", 0)))
            if opacity < 1:
                transformed.putalpha(transformed.getchannel("A").point(lambda value: round(value * opacity)))
            bounds = transformed.getbbox()
            if bounds is None:
                continue
            if (position[0] + bounds[0] < 1 or position[1] + bounds[1] < 1
                    or position[0] + bounds[2] >= size or position[1] + bounds[3] >= size):
                raise ValueError("动效超出画布安全区，请降低位移或缩放")
            frame.alpha_composite(transformed, position)
        if len(frames) == 240:
            raise ValueError("补间后超过 240 帧，请缩短补间段、把停顿设为独立姿势或拆分动图")
        frames.append(frame)
        durations.append(duration)
    return frames, durations


def save_gif(frames, durations, loop, output, *, colors=255):
    # Derive one shared palette to avoid color pulsing between frames.
    atlas = Image.new("RGB", (96 * min(8, len(frames)), 96 * ((len(frames) + 7) // 8)))
    for index, frame in enumerate(frames):
        sample = frame.resize((96, 96), Image.Resampling.BOX)
        atlas.paste(sample.convert("RGB"), (96 * (index % 8), 96 * (index // 8)), sample.getchannel("A"))
    base = atlas.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = (base.getpalette()[:765] + [0, 0, 0])
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette)
    converted = []
    for frame in frames:
        indexed = frame.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE)
        alpha = frame.getchannel("A")
        transparent = alpha.point(lambda value: 255 if value < 128 else 0)
        # The palette mapper may choose the reserved slot for opaque black.
        if 255 in indexed.getdata():
            black = min(range(colors), key=lambda idx: sum(c * c for c in palette[idx * 3:idx * 3 + 3]))
            indexed = indexed.point(list(range(255)) + [black])
        indexed.paste(255, mask=transparent)
        indexed.info["transparency"] = 255
        converted.append(indexed)
    options = {"loop": 0} if loop == "repeat" else {}
    converted[0].save(output, format="GIF", save_all=True, append_images=converted[1:],
                      duration=durations, disposal=2, transparency=255, background=255, optimize=False, **options)
