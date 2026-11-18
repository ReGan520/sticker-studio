---
name: sticker-studio
description: 根据真人照片、宠物照片、角色参考图或原创构思生成静态和 GIF 聊天表情，支持根据所给图片推荐表情创意、风格试稿、原创 IP 定稿、同角色续作、单张返工及微信表情开放平台投稿素材导出。用于做单张表情、整套表情包或准备微信投稿。
---

# 表情包制作室

交付聊天里一眼能读懂的表情。把通过验收的角色参考、无字原画、动效时间轴和成品一起保存，以便续作、换字和局部返工。生成工具负责画图，本地脚本负责排字、动画合成、预览和技术校验。

## 按任务选择流程

- **有图片，缺少具体创作方向**。用户只发了图、只说「做个表情包」，或只指定了风格、构图、GIF 等形式时，先看图，按[看图推荐](references/expression-planning.md#看图推荐)给 3–5 条可选择的方案。保留用户已给定的约束，默认推荐其中一条，等用户回复编号或调整要求后再出图。用户已明确委托自行决定时，可直接采用最贴合图片的一条出样。
- **单张试做或明确的小批量**。用户已经给出台词、情绪、动作或清晰的聊天主题时，读取已有要求，补齐常规细节并直接出样。
- **整套表情或新 IP**。先设计角色和选题。先给一张代表性静态样张。套装含 GIF 时，再给一条代表性动图，以实际聊天尺寸展示。角色、选题和动效合并为一次确认，收到确认后批量制作。新 IP 的初选方案和角色表现力试稿见角色指南。
- **已有角色续作或单张维修**。优先加载用户给出的角色版本和项目。换字重排现有源图。节拍问题先调时长或关键位移。画面本身出错时按表情 ID 换源图。保持其他表情 ID 和源文件，检查新增或改动项在整套预览中的表现。
- **微信投稿**。仅在用户要求投稿包时走[微信导出](references/wechat.md)。先确认具体投稿类型及其当前规则，再准备主图、缩略图和页面配套图文。交付本地投稿素材和复制用文案，由用户在平台操作提交。

若用真人或已有 IP 做公开投稿，确认素材来源及肖像或角色使用授权。用户要求制作原创 IP 时，按自己的角色设定建立外观，不借用未授权的可识别现成形象。

## 生成选项

风格、夸张度、构图独立选择，详见[风格与画面选项](references/styles.md)。用户已指定的选项直接采用，未指定夸张度或构图时按「自动」处理。套装默认值写入 `pack.generation`，单张例外写入 `items[].generation`，逐字段覆盖套装默认。风格未指定时优先沿用角色档案，再按任务选择。示例为 `{"style":"3D 卡通","exaggeration":"strong","composition":"half-body"}`。这些选项指导出图和续作，已有源图要改变风格、姿势或镜头时重新生成受影响的原画或帧。像素风同时设置 `pixel_art: true`，使合成使用最近邻缩放。

## 执行与交付

1. 从[角色设计](references/character-design.md)和[风格](references/styles.md)选取当前任务所需规则。已有定稿时直接复用。用[选题](references/expression-planning.md)把用户实际聊天场景写成表情清单。
2. 按[图像生成](references/image-generation.md)逐张生成无字原画，保存实际可复用的参考图。动画按[GIF 制作](references/gif-production.md)选择分层或关键姿势。每条 GIF 都要根据原图和聊天含义设计可见的表情或肢体姿势变化，默认补画独立的关键姿势及中间帧。整图摇晃、位移、缩放和特效只作辅助，除非用户明确要这类效果。按 GIF 指南写清主情绪的可见证据，先验最能表达情绪的一帧，再分批补画独立过渡帧。交付前用实际 GIF 检查情绪和动作衔接。根据 [pack schema](schemas/pack.schema.json)和 [角色 schema](schemas/character.schema.json)记录项目。
3. 安装 [脚本依赖](scripts/requirements.txt)后，从 Skill 目录运行以下命令。项目路径含空格时加引号。

   ```sh
   python3 -m pip install -r scripts/requirements.txt  # 在所用的 Python 环境中首次安装
   python3 scripts/sticker.py build "PROJECT"
   python3 scripts/sticker.py build "PROJECT" --id sticker-01
   python3 scripts/sticker.py check "PROJECT"
   python3 scripts/sticker.py wechat "PROJECT"
   ```

4. 打开实际导出文件及预览，执行[视觉验收](references/visual-review.md)。脚本能检查文件结构和图像属性。角色是否像、文字对不对、情绪好不好读和 GIF 是否连贯由成品目检判定。定位到失败表情，修改对应源图或配置，再重建和验收。
5. 交付用户要求的 PNG、GIF 和预览，以及用于后续续作的角色档案和源文件。投稿任务再交付微信素材目录、填写文案和校验结果。说明任何仍未通过的检查、缺失素材或未确认的平台规则。

## 最小静态项目

把原画保存为项目下的 `source/received.png`，将以下内容存为同一项目的 `pack.json`。运行 `build` 后打开 `export/preview.html`。项目素材路径相对于项目根目录，通用导出默认 320×320 px，可用 `size` 设置。

```json
{
  "version": 1,
  "title": "下班小剧场",
  "items": [
    {
      "id": "received",
      "kind": "png",
      "source": "source/received.png",
      "caption": "收到",
      "meaning": "确认收到",
      "no_text_copy": true
    }
  ]
}
```
