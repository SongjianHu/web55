# 渲染字体（保真关键）

把论文实际使用的字体文件**放到本目录**，构建镜像时会装进
`/usr/share/fonts/custom/` 并 `fc-cache`。否则 Ubuntu 上 LibreOffice 找不到这些
字体会自动替换，导致 PDF/预览的字号、行距、断行与 Word 不一致。

## 需要哪些字体（须与 `app/defaults.py` 默认一致）

当前默认排版用到：

| 用途 | 中文字体 | 文件（Windows 来源） |
|---|---|---|
| 正文 / 摘要 / 参考文献 / 图表题 | **宋体** SimSun | `simsun.ttc` |
| 各级标题 / 图表题（智能样式） | **黑体** SimHei | `simhei.ttf` |
| 西文（全局） | **Times New Roman** | `times.ttf timesbd.ttf timesi.ttf timesbi.ttf` |
| 建议附带（部分模板用） | 楷体 KaiTi / 仿宋 FangSong | `simkai.ttf` / `simfang.ttf` |

来源：Windows 开发机 `C:\Windows\Fonts\`。复制到本目录即可（自用/小范围部署）。
注意这些是微软版权字体，勿公开分发本目录。

## 不放字体也能跑（降级）

镜像已装 `fonts-noto-cjk`：Noto Serif CJK 近似宋体、Noto Sans CJK 近似黑体，
排版基本可读但**与 Word 非逐像素一致**。要高保真就放真字体。

## 校验

容器内：`fc-list | grep -iE "simsun|simhei|times"` 应能列出对应字体。
