# Travel Roadbooks

把真实旅行中使用过的静态路书，重构为由 JSON 驱动、可校验、可重复构建的移动端路书合集。

[在线站点](https://howieu.github.io/travel/) · [Roadbook Skill](skills/personal-travel-roadbook/SKILL.md) · [JSON Schema](skills/personal-travel-roadbook/references/roadbook-schema.md)

## 为什么重构

旧版本直接维护 11 个 HTML 页面。它证明了时间线、地图入口和路线合集在真实旅行中的价值，但每次新增或修改路线都需要复制页面、手工保持样式一致，并重复检查公开内容。

当前版本将路线内容与展示层分开：

```mermaid
flowchart LR
    A["攻略、截图与个人约束"] --> B["Agent 迁移与编排"]
    B --> C["roadbooks/*.json"]
    C --> D["字段校验与隐私清理"]
    D --> E["静态站点构建"]
    E --> F["GitHub Pages"]
```

- JSON 是唯一内容源，路线可以直接编辑、审查和版本管理。
- Agent 负责非结构化资料理解和路线编排。
- Python 构建器负责必填校验、敏感字段清理、HTML 转义、地图链接和静态页面生成。
- GitHub Actions 在每次推送后运行测试、构建 12 条路线并部署。
- 原有 URL 会生成跳转页，例如 `uk/london.html` 仍可访问。

## 数据规模

- 12 条路线
- 33 个行程日
- 145 个停靠点
- 11 个旧 URL 兼容入口

其中 11 条来自旧站迁移（7 条主路线和 4 条子路线），另有 1 条香港国庆当日路线。公开仓库不保存姓名、订单号、证件、联系方式、支付信息或二维码。

## 本地运行

需要 Python 3.10+。构建器只使用标准库；测试需要 `pytest`。

```bash
python -m pip install pytest
python -m pytest -q

python skills/personal-travel-roadbook/scripts/build_site.py \
  --config site.config.json \
  --input roadbooks \
  --out dist

python -m http.server 8000 --directory dist
```

打开 <http://localhost:8000>。

## 项目结构

```text
.
├── roadbooks/                         # 12 条路线的 JSON 单一数据源
├── skills/personal-travel-roadbook/
│   ├── SKILL.md                       # Agent 工作流
│   ├── scripts/build_site.py          # 确定性静态构建器
│   ├── assets/roadbook.css            # 移动端样式
│   ├── references/                    # 输入、Schema、排程与来源规范
│   └── tests/                         # 构建与隐私回归测试
├── scripts/migrate_legacy_html.py     # 旧 HTML 到 JSON 的一次性迁移工具
├── site.config.json
└── .github/workflows/pages.yml
```

## 内容更新

在 `roadbooks/` 中编辑或新增 JSON，然后重新构建。最低必填字段为：

- `trip.title`
- `trip.destination`
- `days[].date`
- `days[].stops[].name`

每条路线可在 `trip.legacyPaths` 中声明旧 `.html` 地址，构建器会生成安全的兼容跳转。

## 设计边界

- 当前不调用实时交通、营业时间、天气或票价 API，出发前仍需复核。
- 敏感信息清理主要基于字段名称；敏感值若混入自由文本仍可能遗漏。
- 迁移自旧页面的路线只保留原有内容，不补写未经用户确认的事实。
- 仓库当前没有开源许可证，不应默认将代码用于再分发或商业使用。
