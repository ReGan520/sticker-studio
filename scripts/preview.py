from html import escape

from PIL import Image, ImageDraw, ImageOps

from validate import expected_files


def make_preview(output, pack):
    files = [(name, item) for sticker in pack["items"] for name, item in expected_files(sticker)
             if (output / name).is_file()]
    title = escape(pack["title"])
    cards = []
    for name, item in files:
        label = escape(item.get("meaning") or item.get("caption") or name)
        name = escape(name)
        cards.append(f'<figure><div><img src="{name}" alt="{label}"><img class="small" src="{name}" alt=""></div>'
                     f'<figcaption>{label}<br><small>{name}</small></figcaption></figure>')
    (output / "preview.html").write_text(f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font:16px system-ui;margin:0;background:#f7f3ee;color:#28232c}}
main{{max-width:1100px;margin:auto;padding:24px}}section{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}}
figure{{margin:0;border:1px solid #aaa7;border-radius:14px;overflow:hidden}}figure div{{display:flex;align-items:end;justify-content:center;gap:10px;padding:12px;background:#fff}}
img{{width:96px;height:96px;object-fit:contain}}img.small{{width:48px;height:48px}}figcaption{{padding:10px;overflow-wrap:anywhere}}
body.dark{{background:#22212a;color:#fff}}body.dark figure div{{background:#121117}}button{{padding:8px 12px;margin-bottom:14px}}
</style><main><h1>{title}</h1><button onclick="document.body.classList.toggle('dark')">切换浅色／深色</button>
<button onclick="document.querySelectorAll('img').forEach(i=>{{const s=i.getAttribute('src').split('?')[0]; i.src=s+'?play='+Date.now()}})">重播</button>
<section>{''.join(cards)}</section></main></html>""", encoding="utf-8")
    if not files:
        return
    columns = min(6, len(files))
    sheet = Image.new("RGB", (columns * 138, ((len(files) + columns - 1) // columns) * 151), "#f7f3ee")
    draw = ImageDraw.Draw(sheet)
    for index, (name, _) in enumerate(files):
        x, y = (index % columns) * 138, (index // columns) * 151
        with Image.open(output / name) as source:
            art = ImageOps.contain(source.convert("RGBA"), (114, 114))
        sheet.paste(art, (x + (138 - art.width) // 2, y + (126 - art.height) // 2), art)
        draw.text((x + 7, y + 126), name[:20], fill="#28232c")
    sheet.save(output / "contact-sheet.png")
