# 微信表情开放平台专辑

用户要求「投稿」「上架」「表情开放平台专辑」时使用。聊天自用可以直接交付通用 PNG 或 GIF。投稿包是本地提交素材，需要创作者到平台操作。

[微信表情开放平台](https://sticker.weixin.qq.com/)

## 先核对规格和素材

读取用户选择的投稿类别和当前上传表单。真人、卡通、截屏等类别可能有不同条件。核对数量、静态或动态是否分开、格式、像素、字节上限、透明底、描边、文案字数和选填配图。能查看官方页面时记录日期与来源，再将差异写入 `pack.wechat.profile`。登录后才能看到的规则可用用户提供的表单截图或规则文本。核对权利来源、肖像授权和创作者资料要求时依据当前规则。

当前无法直读官方表单时，以草稿配置制作并明确标注「待核对官方表单」。脚本里的 8/12/16/20/24 张、100,000 字节等是**可修改的制作目标**。填写 `verified_on` 和 `source` 会记录表单来源。校验报告保留实际生效的配置和明确覆盖项，未覆盖项仍沿用草稿默认值。最终审核由平台完成。

主图用通用项目的无缝循环 GIF 或静态 PNG。内容依据选题逐张制作。用 `meaning` 提供应填入平台的含义词，省略时脚本使用 `caption`。含义词和画面上的文字可以不同。缩略图默认取无描边主图的首帧，可指定动作的代表帧或专门制作一张简化透明小图。专辑横幅应独立构图，按表单要求安排背景、角色位置和文字；封面与面板图标选容易识别的主轮廓，小图检查眼睛、道具和文字是否挤在一起。

## 填写项目

下面是草稿配置例子。配图路径相对于表情包项目，缩略图帧索引从 0 开始，使用实际通用 GIF 的编码帧序号。

```json
{
  "wechat": {
    "title": "气鼓鼓云朵",
    "description": "一朵脾气来得快、走得也快的小乌云。",
    "banner": "source/wechat/banner.png",
    "cover": "source/wechat/cover.png",
    "icon": "source/wechat/icon.png",
    "thumbnails": {
      "cloud-angry": 2,
      "cloud-ok": "source/wechat/thumb-ok.png"
    }
  }
}
```

`profile` 中可覆盖的字段：

| 字段 | 草稿配置或说明 |
|---|---|
| `counts`, `allowed_kinds`, `allow_mixed` | `[8,12,16,20,24]`、`["png","gif"]`、`false` |
| `outline_px`, `title_chars`, `meaning_chars` | 2、8、4；关闭白描边时填 0 |
| `description_chars` | 可按实际表单填写介绍字数限制 |
| `main`, `thumbnail` | 分别为 240 × 240、120 × 120；100,000、50,000 字节；透明。主图为方形，可覆盖 `size`、`bytes`、`transparent` |
| `banner` | 750 × 400、80,000 字节、不透明 JPG；用比例匹配的无透明全幅原画，可改用 PNG |
| `cover` | 240 × 240、80,000 字节、透明 PNG |
| `icon` | 50 × 50、30,000 字节、透明 PNG |
| `reward_guide`, `reward_thanks` | 表单要求时可增加，例如 `{"size":[750,560],"bytes":100000,"transparent":false,"format":"jpg"}`，同时在 `wechat` 同名字段提供项目内素材路径。尺寸和格式示例需要按表单填写 |
| `verified_on`, `source` | 核对后填写日期 `YYYY-MM-DD` 和官方规则或表单来源，两项一起记录 |

配图规则使用 `size`、`bytes`、`transparent`、`format`。可按用户需求在 `wechat.reward_copy` 提供赞赏文案。体积超标时尝试较低色数或 JPEG 质量，本地技术检查后还要目视检查压缩效果。压缩后仍超限则回到素材和动效调整，避免擅自牺牲可读性或丢帧。

## 运行导出

先运行 `python3 sticker-studio/scripts/sticker.py build <项目目录>` 生成通用图，再运行
`python3 sticker-studio/scripts/sticker.py wechat <项目目录>` 制作投稿包。通用图有更新时重新执行这两步。专辑编辑时以发布页面需要的字段为准，压缩包便于交接和归档。

## 验收交付

导出目录 `export/wechat/` 含按顺序编号的 `main/` 和 `thumbnails/`、横幅、封面、面板图标、`listing.md`、`validation.json`、`wechat.zip`。先看编号是否对应、缩略图能否表达对应情绪，再用浅底和深底打开导出的实际 GIF，检查描边、降色、残影和循环。记录哪些规则来自真实表单，哪些来自草稿配置，然后把素材和可复制文案交给用户。
