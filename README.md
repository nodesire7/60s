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
- **定时构建** — 凌晨5点生成，8点复查，保证每日更新

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

## 定时构建

GitHub Actions 每日自动执行：

| 时间 | 操作 |
|------|------|
| 凌晨 5:00 (Beijing) | 完整构建：API获取 → RSS → TTS → WebP |
| 早上 8:00 (Beijing) | 复查：若未更新则重试 |

## 许可

文本由AI生成，仅供参考。代码开源。
