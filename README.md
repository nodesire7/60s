# 每天60秒读懂世界

> 每天60秒读懂世界 — AI精选全球最新15条热点新闻，自动生成TTS语音播报与精美分享卡片

[![Daily Build](https://github.com/nodesire7/60s/actions/workflows/daily-build.yml/badge.svg)](https://github.com/nodesire7/60s/actions/workflows/daily-build.yml)
[![GitHub Pages](https://img.shields.io/badge/Pages-Online-brightgreen)](https://nodesire7.github.io/60s/)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

**[🌐 在线页面](https://nodesire7.github.io/60s/)** | **[🎧 今日音频](https://nodesire7.github.io/60s/60s.mp3)** | **[📊 构建历史](https://github.com/nodesire7/60s/actions)**

## 功能特性

- **AI精选新闻** — 每日自动抓取最新15条全球热点，含微语金句
- **TTS语音播报** — edge-tts合成中文语音，可直接播放收听
- **精美分享卡片** — WebP截图生成，650px宽度适配手机分享
- **按周配色** — 12种主题颜色每周轮换，视觉不单调
- **GitHub Pages** — 自动部署静态页面，支持音频播放
- **定时构建** — 06:40–12:40 每 20 分钟自动检查，上游发布后 20 分钟内更新

## 页面截图

| 日期卡片 | 新闻列表 | 音频播放 |
|:---:|:---:|:---:|
| 按周配色 + 农历显示 | 15条精炼新闻 | 一键播放60s.mp3 |

## 技术栈

| 模块 | 技术 |
|------|------|
| 新闻抓取 | Python + Requests + BeautifulSoup |
| RSS生成 | feedgen |
| TTS语音 | edge-tts (VITS API备用) |
| 截图生成 | Selenium + Chrome Headless + Pillow |
| 前端页面 | HTML5 + CSS3 + Vanilla JS |
| 自动部署 | GitHub Actions + GitHub Pages |
| 广告 | Google AdSense Auto Ads |

## 项目结构

```
├── sixty_seconds_daily.py   # 主编排：API → RSS → TTS → WebP
├── rss_to_tts.py            # RSS XML → 语音合成
├── scrapers*.py             # 多种爬虫实现
├── generate_webp.py         # 独立截图工具
├── 60s.html / index.html    # 页面模板
├── .github/workflows/       # CI/CD 定时构建
├── zhihu_daily_news.xml     # 每日RSS数据
├── data-date.txt            # 已生成数据的日期（CI 判断是否跳过）
└── 60s.mp3 / 60s.webp       # 每日输出产物
```

## 本地使用

```bash
pip install -r requirements.txt

# 完整流程
python sixty_seconds_daily.py

# 仅生成TTS
python rss_to_tts.py --output 60s

# 仅生成截图（需要浏览器）
python generate_webp.py
```

## 数据源

新闻来自开源项目 **[vikiboss/60s](https://github.com/vikiboss/60s)** 的公开 API：

| 顺序 | 接口 |
|------|------|
| 1（主） | `https://60s.viki.moe/v2/60s` |
| 2（备） | `https://60s-api.viki.moe/v2/60s` |
| 3（备） | `https://60s.afei7.com/v2/60s` |

所有接口都拿不到**当天**数据时，流程会返回 `3`（上游尚未发布）或 `1`（数据源故障），
不会再像以前那样拿仓库里的旧 XML 继续生成，从而避免"页面停更但 CI 显示成功"。

## 定时构建

GitHub Actions 会在北京时间 **06:40–12:40 每 20 分钟**检查一次：

| 场景 | 行为 |
|------|------|
| 今天的数据已生成 | 直接跳过（约 10 秒） |
| 上游已发布 | 抓取 → RSS → TTS → WebP → 提交部署 |
| 上游尚未发布 | 退出码 3，跳过，等下一次调度 |
| 超过 12:00 仍无数据 | 构建失败并报警（红叉） |
| 数据源全部不可用 | 构建失败并报警（红叉） |

> 数据日期记录在 `data-date.txt`，CI 与本地都以它为准，不再靠 `pubDate` 猜测。

## 许可

文本由AI生成，仅供参考。代码开源。
