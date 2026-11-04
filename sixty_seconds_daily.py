#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
每天60秒读懂世界 - 主程序
功能：
1. 爬取知乎每日60秒新闻
2. 生成RSS文件
3. 生成TTS语音文件
4. 生成网页截图

使用方法：
python sixty_seconds_daily.py [--no-scrape] [--no-tts] [--no-image]

参数说明：
--no-scrape: 跳过爬取知乎并生成RSS的步骤
--no-tts: 跳过生成TTS语音文件的步骤
--no-image: 跳过生成网页截图的步骤

作者: AI助手
"""

import os
import sys
import subprocess
import time
import argparse
import logging
import shutil
import socket
import requests
import json
import re
from datetime import datetime
from pathlib import Path
from feedgen.feed import FeedGenerator
import pytz

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 路径设置
# 使用脚本所在目录作为基础目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(BASE_DIR, "scraper.py")  # 爬虫脚本路径
RSS_TO_TTS_PATH = os.path.join(BASE_DIR, "rss_to_tts.py")  # RSS转TTS脚本路径
OUTPUT_DIR = BASE_DIR  # 输出目录与BASE_DIR相同
HTML_PATH = os.path.join(BASE_DIR, "60s.html")  # HTML文件路径
DATA_DATE_FILE = os.path.join(BASE_DIR, "data-date.txt")  # 记录已生成数据的日期，供 CI 判断

CN_TZ = pytz.timezone('Asia/Shanghai')

# 新闻数据源：优先使用 vikiboss/60s 官方 API，失败时依次回退
# 上游项目: https://github.com/vikiboss/60s
API_SOURCES = [
    ("60s 官方 API", "https://60s.viki.moe/v2/60s"),
    ("60s 备用 API", "https://60s-api.viki.moe/v2/60s"),
    ("60s 镜像", "https://60s.afei7.com/v2/60s"),
]
SOURCE_HOME = "https://github.com/vikiboss/60s"

def check_local_server(host='localhost', port=1929):
    """检查本地服务器是否运行"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def run_command(cmd, cwd=None, shell=True):
    """执行命令并返回输出"""
    logger.info(f"执行命令: {cmd}")
    try:
        # 使用subprocess.run替代Popen，更简单的接口
        process = subprocess.run(
            cmd, 
            shell=shell, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            cwd=cwd,
            encoding='utf-8',
            errors='replace',  # 使用replace模式处理无法解码的字符
            universal_newlines=True,
            check=False  # 不自动抛出异常
        )
        
        # 检查返回码
        if process.returncode != 0:
            logger.error(f"命令执行失败，退出码: {process.returncode}")
            if process.stderr:
                logger.error(f"错误输出: {process.stderr}")
            return False, process.stderr if process.stderr else ""
        
        logger.info("命令执行成功")
        return True, process.stdout if process.stdout else ""
    except Exception as e:
        logger.error(f"执行命令时出错: {e}")
        return False, str(e)

def today_cst():
    """返回北京时间今天的日期字符串"""
    return datetime.now(CN_TZ).strftime('%Y-%m-%d')


def split_lunar(value):
    """把 '丙午年九月廿六' 拆成 ('丙午年', '九月廿六')"""
    m = re.match(r'^([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])年(.*)$', (value or '').strip())
    if m:
        return f"{m.group(1)}年", m.group(2).strip()
    return '', (value or '').strip()


ZODIAC_BY_BRANCH = {
    '子': '鼠', '丑': '牛', '寅': '虎', '卯': '兔', '辰': '龙', '巳': '蛇',
    '午': '马', '未': '羊', '申': '猴', '酉': '鸡', '戌': '狗', '亥': '猪',
}


def normalize_api_data(raw):
    """把不同数据源返回的数据统一成内部结构；数据不完整时返回 None"""
    if not isinstance(raw, dict):
        return None

    date_str = str(raw.get('date') or '').strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return None

    news = []
    for item in raw.get('news') or []:
        text = re.sub(r'^\s*\d+[、.．]\s*', '', str(item)).strip()
        if text:
            news.append(text)
    if not news:
        return None

    data = dict(raw)
    data['date'] = date_str
    data['news'] = news
    # 老接口用 weiyu，vikiboss/60s 接口用 tip
    data['weiyu'] = str(raw.get('weiyu') or raw.get('tip') or '').strip()

    ganzhi, lunar_md = split_lunar(str(raw.get('lunar_date') or ''))
    if not ganzhi:
        ganzhi = str(raw.get('ganzhi') or '').strip()
    zodiac = str(raw.get('zodiac') or '').strip().rstrip('年')
    if not zodiac and len(ganzhi) >= 2:
        zodiac = ZODIAC_BY_BRANCH.get(ganzhi[1], '')
    data['ganzhi'] = ganzhi
    data['zodiac'] = zodiac
    data['lunar_date'] = lunar_md if ganzhi else str(raw.get('lunar_date') or '')

    if not data.get('day_of_week'):
        d = datetime.strptime(date_str, '%Y-%m-%d')
        data['day_of_week'] = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][d.weekday()]
    return data


def fetch_data_from_api():
    """从上游 API 获取今日数据。

    返回 (data, state)：
      state = "ok"     拿到了今天的数据
      state = "stale"  接口可用，但数据还停留在旧日期（上游尚未发布）
      state = "error"  所有接口都不可用
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }
    today = today_cst()
    saw_stale = False

    for name, api_url in API_SOURCES:
        logger.info(f"尝试从 {name} 获取数据: {api_url}")
        try:
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning(f"{name} 请求失败: {e}")
            continue

        if not isinstance(payload, dict) or payload.get('code') != 200:
            logger.warning(f"{name} 返回状态异常: {str(payload)[:200]}")
            continue

        data = normalize_api_data(payload.get('data') or {})
        if not data:
            logger.warning(f"{name} 返回的数据不完整，忽略")
            continue

        if data['date'] != today:
            logger.warning(f"{name} 数据仍停留在 {data['date']}（今天 {today}），上游尚未发布")
            saw_stale = True
            continue

        logger.info(f"{name} 获取成功: {data['date']}，{len(data['news'])} 条新闻")
        return data, 'ok'

    return None, ('stale' if saw_stale else 'error')


def resolve_lunar_info(api_data, year, month, day):
    """返回 (ganzhi, zodiac, 农历月日)，API 缺失时回退到农历接口"""
    ganzhi = str(api_data.get('ganzhi') or '').strip()
    zodiac = str(api_data.get('zodiac') or '').strip().rstrip('年')
    lunar_md = str(api_data.get('lunar_date') or '').strip()

    if ganzhi and zodiac and lunar_md:
        return ganzhi, zodiac, lunar_md

    try:
        nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        nongli_response = requests.get(nongli_url, headers=headers, timeout=8)
        if nongli_response.status_code == 200:
            nongli_data = nongli_response.json()
            if nongli_data.get('status') == 1 and 'data' in nongli_data:
                nd = nongli_data['data']
                ganzhi = ganzhi or str(nd.get('ganzhi') or '').strip()
                zodiac = zodiac or str(nd.get('zodiac') or '').strip().rstrip('年')
                lunar_md = lunar_md or str(nd.get('lunar_date') or '').strip()
    except Exception as e:
        logger.warning(f"获取农历信息失败: {e}")

    return ganzhi, zodiac, lunar_md


def build_lunar_text(ganzhi, zodiac, lunar_md):
    """组合成 '丙午年(马年) 九月廿六' 的展示文本"""
    if ganzhi and zodiac:
        text = f"{ganzhi}({zodiac}年)"
        return f"{text} {lunar_md}".strip() if lunar_md else text
    return lunar_md


def build_content(api_data, year, month, day, weekday, lunar_text):
    """生成 RSS 与页面共用的正文：日期行 + 编号新闻 + 微语"""
    date_line = f"{year}年{month}月{day}日，{weekday}"
    if lunar_text:
        date_line += f"，{lunar_text}"
    lines = [date_line, ""]

    for idx, item in enumerate(api_data.get('news') or [], 1):
        lines.append(f"{idx}、{item}")

    weiyu = str(api_data.get('weiyu') or '').strip()
    if weiyu:
        lines.append("")
        lines.append(f"【微语】{weiyu}")
    return "\n".join(lines)


def generate_rss_from_api_data(api_data):
    """从API数据生成RSS文件"""
    try:
        date_obj = datetime.strptime(api_data.get('date', ''), '%Y-%m-%d')
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]

        ganzhi, zodiac, lunar_md = resolve_lunar_info(api_data, year, month, day)
        lunar_text = build_lunar_text(ganzhi, zodiac, lunar_md)
        content = build_content(api_data, year, month, day, weekday, lunar_text)

        fg = FeedGenerator()
        fg.title('60秒知天下')
        fg.link(href=SOURCE_HOME, rel='alternate')
        fg.description('60秒知天下RSS')
        fg.language('zh-CN')

        fe = fg.add_entry()
        fe.title(f"{month}月{day}日，{weekday}，在这里每天读懂世界")
        fe.link(href=SOURCE_HOME)
        fe.description(content)
        fe.pubDate(CN_TZ.localize(datetime(year, month, day)))

        xml_path = os.path.join(BASE_DIR, "zhihu_daily_news.xml")
        fg.rss_file(xml_path, pretty=True)
        logger.info(f"RSS文件已成功生成: {xml_path}")
        return True

    except Exception as e:
        logger.error(f"从API数据生成RSS文件时出错: {e}")
        return False


def generate_static_html(api_data):
    """从API数据生成静态HTML页面，新闻数据直接嵌入，无需JS fetch"""
    logger.info("开始生成静态HTML页面...")

    # 解析日期
    date_str = api_data.get("date", "")
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            year, month, day = date_obj.year, date_obj.month, date_obj.day
        except:
            now = datetime.now()
            year, month, day = now.year, now.month, now.day
            date_obj = now
    else:
        now = datetime.now()
        year, month, day = now.year, now.month, now.day
        date_obj = now

    # Python weekday: 0=Mon → JS getDay: 0=Sun
    js_day = (date_obj.weekday() + 1) % 7
    weekday_en = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"][js_day]
    weekday_cn = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][js_day]

    # 按星期几变换颜色（7色，周一到周日各不相同）
    weekday_colors = {
        0: '#FF5722',  # 周日 Sunday
        1: '#4CAF50',  # 周一 Monday
        2: '#2196F3',  # 周二 Tuesday
        3: '#FF9800',  # 周三 Wednesday
        4: '#9C27B0',  # 周四 Thursday
        5: '#F44336',  # 周五 Friday
        6: '#E91E63',  # 周六 Saturday
    }
    week_color = weekday_colors[js_day]

    # 获取农历信息（含干支生肖年份）
    ganzhi, zodiac, lunar_md = resolve_lunar_info(api_data, year, month, day)
    lunar_info = build_lunar_text(ganzhi, zodiac, lunar_md)

    # 生成标题
    title = api_data.get("title", f"{year}年{month}月{day}日，{weekday_cn}，在这里每天读懂世界")
    gregorian_date = f"{year}年{month}月{day}日"

    # 构建内容文本（用于解析新闻条目和微语）
    content = api_data.get("content", "")
    if not content:
        content = build_content(api_data, year, month, day, weekday_cn, lunar_info)

    # 解析新闻条目
    lines = content.split('\n')
    news_items = []
    hitokoto = ""
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if '【微语】' in line_stripped or '【#今日微语】' in line_stripped or '【#今日早报微语】' in line_stripped:
            hitokoto = line_stripped.replace('【#今日早报微语】：', '').replace('【#今日微语】：', '').replace('【#今日早报微语】', '').replace('【#今日微语】', '').replace('【微语】：', '').replace('【微语】:', '').replace('【微语】', '').strip()
            continue
        if '来源：' in line_stripped or line_stripped.startswith('每天60秒'):
            continue
        import re as _re
        match = _re.match(r'^(\d+)[、.．]\s*', line_stripped)
        if match:
            num = match.group(1)
            text = _re.sub(r'^\d+[、.．]\s*', '', line_stripped)
            if text and len(news_items) < 15:
                news_items.append((num, text))

    # 如果还没有微语，尝试从API字段获取
    if not hitokoto:
        hitokoto = api_data.get("weiyu", "心事浩茫连广宇，于无声处听惊雷。")

    # 生成新闻HTML
    news_html_parts = []
    for num, text in news_items:
        news_html_parts.append(f'''            <div class="news-item">
                <div class="news-number-box"><div class="news-number">{num}</div></div>
                <div class="news-content">{text}</div>
            </div>''')

    news_html = "\n".join(news_html_parts) if news_html_parts else '<div class="loading">暂无新闻数据</div>'

    # 构建时间戳
    from datetime import timezone as _tz, timedelta as _td
    _cst = _tz(_td(hours=8))
    build_time = datetime.now(_cst).strftime('%Y-%m-%d %H:%M')
    # 显示真实构建时间（旧代码写死 05:00，与实际更新时间不符）
    sync_time = build_time

    html = f'''<!DOCTYPE html>
<html lang="zh-CN" style="background-color: #f0f0f0 !important;">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>每天60秒读懂世界</title>
    <meta name="description" content="每天60秒读懂世界，AI精选全球最新、最重要的15条热点新闻">
    <link rel="shortcut icon" href="favicon.svg" type="image/svg+xml">

    <style>
        :root {{
            --background-color: #f0f0f0 !important;
            --card-shadow: 0 3px 10px rgba(0, 0, 0, 0.12) !important;
            --card-bg-color: {week_color};
        }}

        html, body {{
            background-color: #f0f0f0 !important;
            margin: 0 !important;
            padding: 0 !important;
            min-height: auto !important;
        }}

        .webp-capture * {{
            animation: none !important;
            transition: none !important;
        }}

        .webp-capture .audio-player-bar,
        .webp-capture .build-status-bar {{
            display: none !important;
        }}

        .audio-player-bar {{
            display: flex;
            align-items: center;
            justify-content: center;
            background: #ffffff;
            border-radius: 12px;
            padding: 10px 15px;
            box-shadow: var(--card-shadow);
            gap: 12px;
            margin-bottom: 0;
        }}

        .audio-btn {{
            width: 44px; height: 44px;
            border-radius: 50%;
            border: none;
            background-color: var(--card-bg-color);
            color: white;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            box-shadow: 0 3px 8px rgba(0,0,0,0.2);
        }}

        .audio-btn:hover {{ transform: scale(1.08); }}
        .audio-btn:active {{ transform: scale(0.95); }}
        .audio-btn.playing {{ animation: pulse 1.2s infinite; }}

        @keyframes pulse {{
            0%, 100% {{ box-shadow: 0 3px 8px rgba(0,0,0,0.2); }}
            50% {{ box-shadow: 0 0 0 8px rgba(0,0,0,0.08), 0 3px 8px rgba(0,0,0,0.2); }}
        }}

        .audio-progress {{
            flex: 1; height: 4px;
            background: #e0e0e0; border-radius: 2px;
            overflow: hidden; cursor: pointer;
        }}

        .audio-progress-fill {{
            height: 100%;
            background: var(--card-bg-color);
            border-radius: 2px;
            width: 0%;
            transition: width 0.3s ease;
        }}

        .audio-time {{
            font-size: 12px; color: #999;
            flex-shrink: 0; min-width: 65px;
            text-align: center;
        }}

        header h1 {{
            color: var(--card-bg-color) !important;
            font-size: 24px !important;
            margin: 0 !important; padding: 0 !important;
            font-weight: bold !important;
            background-color: transparent !important;
            letter-spacing: 1px !important;
        }}

        header {{
            margin: 0 !important; text-align: center !important;
            background-color: transparent !important;
            border-radius: 0 !important;
            padding: 8px 0 4px !important;
            box-shadow: none !important;
        }}

        .news-container {{
            padding: 15px !important; margin: 0 !important;
            background-color: #ffffff !important;
            border-radius: 12px !important;
            box-shadow: var(--card-shadow) !important;
            border: none !important;
        }}

        .news-item {{
            margin-bottom: 12px !important;
            padding: 8px 0 12px 0 !important;
            border-bottom: 1px solid #f5f5f5 !important;
            background-color: #ffffff !important;
            display: flex !important;
            align-items: flex-start !important;
        }}

        .news-item:last-child {{
            margin-bottom: 0 !important;
            border-bottom: none !important;
            padding-bottom: 0 !important;
        }}

        .news-number-box {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            flex-shrink: 0 !important;
            width: 32px !important;
            height: 41.6px !important;
            margin-right: 12px !important;
        }}

        .news-number {{
            width: 24px !important; height: 24px !important;
            border-radius: 50% !important;
            background-color: var(--card-bg-color) !important;
            color: white !important;
            font-size: 14px !important;
            font-weight: bold !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            line-height: 1 !important;
        }}

        .news-content {{
            flex: 1 !important;
            font-size: 26px !important;
            line-height: 1.6 !important;
            color: #333333 !important;
            text-align: justify !important;
            margin: 0 !important; padding: 0 !important;
        }}

        .hitokoto {{
            background-color: #ffffff !important;
            border-radius: 12px !important;
            padding: 15px 30px !important;
            font-size: 21px !important;
            line-height: 1.6 !important;
            color: #757575 !important;
            text-align: center !important;
            font-style: italic !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
            margin-bottom: 0 !important;
            position: relative !important;
            width: 100% !important;
            display: block !important;
            box-sizing: border-box;
        }}

        .hitokoto::before {{
            content: "\\201C" !important;
            font-size: 40px !important;
            color: #e0e0e0 !important;
            position: absolute !important;
            left: 12px !important; top: -2px !important;
        }}

        .hitokoto::after {{
            content: "\\201D" !important;
            font-size: 40px !important;
            color: #e0e0e0 !important;
            position: absolute !important;
            right: 12px !important; bottom: -20px !important;
        }}

        .today-date {{
            margin: 0 !important; width: 100% !important;
        }}

        .date-card {{
            display: flex;
            background-color: var(--card-bg-color);
            color: white;
            border-radius: 12px !important;
            overflow: hidden;
            min-height: 100px;
            margin-bottom: 0 !important;
            position: relative; z-index: 1;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.25) !important;
            border: none !important;
        }}

        .date-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: url('css/bg_small.webp') !important;
            background-size: cover !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            opacity: 0.3 !important;
            z-index: -1;
            mix-blend-mode: overlay !important;
            border-radius: 12px;
        }}

        .lunar-section {{
            width: 30%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            position: relative; z-index: 2;
            padding: 15px;
        }}

        .lunar-section::after {{
            content: '';
            position: absolute;
            right: 0; top: 30%;
            height: 40%; width: 1px;
            background: rgba(255, 255, 255, 0.5);
            box-shadow: 0 0 3px rgba(255, 255, 255, 0.3);
        }}

        .weekday-en {{
            font-size: 18px; font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 5px; letter-spacing: 1px;
        }}

        .weekday-cn {{ font-size: 26px; font-weight: bold; }}

        .gregorian-section {{
            flex: 1; padding: 15px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            text-align: center;
        }}

        .gregorian-date {{
            font-size: 28px; font-weight: bold;
            margin-bottom: 5px;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }}

        .lunar-date {{
            font-size: 18px !important; opacity: 1;
            color: rgba(255, 255, 255, 1);
            letter-spacing: 1px; margin-top: 2px;
            font-weight: 500;
            text-shadow: 0 1px 1px rgba(0, 0, 0, 0.2);
        }}

        .app-container {{
            padding: 8px !important;
            display: flex !important;
            flex-direction: column !important;
            min-height: auto !important;
            gap: 8px !important;
            max-width: 800px !important;
            margin: 0 auto !important;
            background-color: #f0f0f0 !important;
        }}

        footer {{
            text-align: center !important;
            padding: 8px 0 !important;
            color: #757575 !important;
            font-size: 12px !important;
            margin-top: 0 !important;
            margin-bottom: 5px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-top: none !important;
            background-color: #ffffff !important;
            border-radius: 12px !important;
            box-shadow: var(--card-shadow) !important;
        }}

        footer p {{
            display: flex !important;
            align-items: center !important;
            margin: 0 !important; padding: 0 !important;
        }}

        footer a {{
            color: var(--card-bg-color) !important;
            text-decoration: none !important;
        }}

        .author-avatar {{
            width: 16px !important; height: 16px !important;
            border-radius: 50% !important;
            margin-right: 5px !important;
        }}

        .build-status-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #ffffff;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 11px;
            color: #666;
            font-family: 'Courier New', monospace;
            border: 1px dashed #e0e0e0;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .build-status-dot {{
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #4CAF50;
            flex-shrink: 0;
        }}

        @media (max-width: 600px) {{
            .news-content {{ font-size: 20px !important; }}
            .gregorian-date {{ font-size: 22px !important; }}
            .weekday-cn {{ font-size: 22px !important; }}
            .weekday-en {{ font-size: 16px !important; }}
            .lunar-date {{ font-size: 14px !important; }}
            header h1 {{ font-size: 20px !important; }}
            .hitokoto {{ font-size: 18px !important; padding: 10px 20px !important; }}
        }}
    </style>

    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9956808351564739" crossorigin="anonymous"></script>
    <meta name="adsense-ads.txt" content="google.com, pub-9956808351564739, DIRECT, f08c47fec0942fa0">
</head>
<body>
    <div class="app-container" id="captureContent">
        <header>
            <h1>每天60秒读懂世界</h1>
        </header>

        <div class="build-status-bar" id="buildStatus">
            <span style="display:flex;align-items:center;gap:6px">
                <span class="build-status-dot" id="statusDot"></span>
                <span id="statusText">SYSTEM: 60S_DAILY_NEWS</span>
            </span>
            <span id="lastSync">LAST_SYNC: {sync_time}</span>
        </div>

        <div class="audio-player-bar" id="audioPlayer">
            <button class="audio-btn" id="audioBtn" aria-label="播放/暂停" title="播放/暂停">▶</button>
            <div class="audio-progress" id="audioProgressBar">
                <div class="audio-progress-fill" id="audioProgressFill"></div>
            </div>
            <span class="audio-time" id="audioTime">00:00 / 00:00</span>
        </div>

        <div class="today-date" id="today-date">
            <div class="date-card">
                <div class="lunar-section">
                    <div class="weekday-en">{weekday_en}</div>
                    <div class="weekday-cn">{weekday_cn}</div>
                </div>
                <div class="gregorian-section">
                    <div class="gregorian-date">{gregorian_date}</div>
                    <div class="lunar-date">{lunar_info}</div>
                </div>
            </div>
        </div>

        <div class="hitokoto" id="hitokoto">{hitokoto}</div>

        <div class="news-container" id="newsContainer">
{news_html}
        </div>

        <footer>
            <p>
                <img src="https://avatars.githubusercontent.com/u/63827263?v=4" alt="nodesire7" class="author-avatar">
                <span>&copy; {year} <a href="https://github.com/nodesire7" target="_blank">nodesire7</a> | 文本由AI生成，仅供参考</span>
            </p>
        </footer>
    </div>

    <script>
        (function() {{
            var url = new URL(window.location.href);
            if (url.searchParams.get('webp') === '1') {{
                document.documentElement.classList.add('webp-capture');
            }}

            var audio = new Audio('60s.mp3');
            audio.preload = 'auto';
            var btn = document.getElementById('audioBtn');
            var progressFill = document.getElementById('audioProgressFill');
            var timeDisplay = document.getElementById('audioTime');
            var progressBar = document.getElementById('audioProgressBar');
            var isPlaying = false;

            function formatTime(s) {{
                var m = Math.floor(s / 60);
                var sec = Math.floor(s % 60);
                return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
            }}

            btn.addEventListener('click', function() {{
                if (isPlaying) {{ audio.pause(); }}
                else {{ audio.play().catch(function(e) {{ console.warn('Audio play failed:', e); }}); }}
            }});

            audio.addEventListener('play', function() {{
                isPlaying = true; btn.textContent = '⏸'; btn.classList.add('playing');
            }});

            audio.addEventListener('pause', function() {{
                isPlaying = false; btn.textContent = '▶'; btn.classList.remove('playing');
            }});

            audio.addEventListener('ended', function() {{
                isPlaying = false; btn.textContent = '▶'; btn.classList.remove('playing');
                progressFill.style.width = '0%';
                timeDisplay.textContent = '00:00 / ' + formatTime(audio.duration || 0);
            }});

            audio.addEventListener('loadedmetadata', function() {{
                timeDisplay.textContent = '00:00 / ' + formatTime(audio.duration);
            }});

            audio.addEventListener('timeupdate', function() {{
                if (audio.duration) {{
                    progressFill.style.width = (audio.currentTime / audio.duration * 100) + '%';
                    timeDisplay.textContent = formatTime(audio.currentTime) + ' / ' + formatTime(audio.duration);
                }}
            }});

            progressBar.addEventListener('click', function(e) {{
                if (!audio.duration) return;
                var rect = progressBar.getBoundingClientRect();
                audio.currentTime = (e.clientX - rect.left) / rect.width * audio.duration;
            }});
        }})();
    </script>

    <pre id="ads-txt" style="display:none">google.com, pub-9956808351564739, DIRECT, f08c47fec0942fa0</pre>
</body>
</html>'''

    # 写入文件
    html_path = os.path.join(BASE_DIR, "60s.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"静态HTML已生成: {html_path} ({len(html)} bytes)")

    # 同步到 index.html
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"index.html 已同步: {index_path}")

    return True


def write_data_date(date_str):
    """写入数据日期标记文件，CI 用它判断今天是否已经生成"""
    try:
        with open(DATA_DATE_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{date_str}\n")
        return True
    except Exception as e:
        logger.warning(f"写入数据日期标记失败: {e}")
        return False


def read_xml_data_date(xml_path):
    """从 RSS 中解析新闻日期，解析不出来返回 None"""
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_path).getroot()
        item = root.find('.//item')
        if item is None:
            return None

        for text in (item.findtext('description') or '', item.findtext('title') or ''):
            m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
            if m:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime('%Y-%m-%d')

        m = re.search(r'(\d{1,2})月(\d{1,2})日', item.findtext('title') or '')
        if m:
            return datetime(datetime.now(CN_TZ).year, int(m.group(1)), int(m.group(2))).strftime('%Y-%m-%d')

        m = re.search(r'(\d{1,2}) (\w{3}) (\d{4})', item.findtext('pubDate') or '')
        if m:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", '%d %b %Y').strftime('%Y-%m-%d')
    except Exception as e:
        logger.warning(f"解析 RSS 日期失败: {e}")
    return None


def load_content_from_xml(xml_path):
    """把爬虫生成的 RSS 读回成 api_data 结构，用于生成静态页面"""
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_path).getroot()
        item = root.find('.//item')
        if item is None:
            return None
        return {
            'date': read_xml_data_date(xml_path) or today_cst(),
            'title': item.findtext('title') or '',
            'content': item.findtext('description') or '',
            'news': [],
            'weiyu': '',
        }
    except Exception as e:
        logger.warning(f"读取 RSS 内容失败: {e}")
        return None


def scrape_zhihu_and_generate_rss():
    """抓取今日新闻并生成 RSS/HTML。

    返回 "ok"   今日数据已生成
         "stale" 上游尚未发布今日数据（不是错误，等下一次调度）
         "error" 硬失败（数据源不可用/生成失败）
    """
    api_data, state = fetch_data_from_api()

    if api_data:
        if not generate_rss_from_api_data(api_data):
            return 'error'
        if not generate_static_html(api_data):
            logger.error("静态HTML生成失败")
            return 'error'
        write_data_date(api_data['date'])
        return 'ok'

    logger.info("API 数据不可用，尝试从知乎爬取数据...")
    success, output = run_command(f"python {SCRAPER_PATH} -r", cwd=BASE_DIR)
    if not success:
        logger.error("爬取知乎失败")
        return state

    xml_path = os.path.join(BASE_DIR, "zhihu_daily_news.xml")
    if not os.path.exists(xml_path):
        logger.error(f"未找到生成的XML文件: {xml_path}")
        return 'error'

    # 关键校验：绝不能把仓库里的旧 XML 当成今天的结果继续生成
    xml_date = read_xml_data_date(xml_path)
    if xml_date != today_cst():
        logger.error(f"爬虫结果日期为 {xml_date}，不是今天 {today_cst()}，拒绝复用旧数据")
        return 'stale' if xml_date else 'error'

    xml_data = load_content_from_xml(xml_path)
    if not xml_data:
        logger.error("无法读取爬虫生成的 RSS 内容")
        return 'error'
    if not generate_static_html(xml_data):
        logger.error("静态HTML生成失败")
        return 'error'

    write_data_date(xml_date)
    return 'ok'


def generate_tts():
    """生成TTS语音文件"""
    logger.info("开始生成TTS语音文件...")
    output_name = "60s"  # 固定文件名，不带日期
    
    # 检查XML文件是否存在
    xml_path = os.path.join(BASE_DIR, "zhihu_daily_news.xml")
    if not os.path.exists(xml_path):
        logger.error(f"未找到XML文件: {xml_path}")
        return False
    
    # 运行RSS到TTS的脚本
    cmd = f"python {RSS_TO_TTS_PATH} --output {output_name}"
    success, output = run_command(cmd, cwd=BASE_DIR)
    
    if not success:
        logger.error("生成TTS语音文件失败")
        return False
    
    # 检查MP3文件是否已生成
    mp3_path = os.path.join(OUTPUT_DIR, f"{output_name}.mp3")
    if not os.path.exists(mp3_path):
        logger.error(f"未找到生成的MP3文件: {mp3_path}")
        return False
    
    logger.info(f"已成功生成TTS语音文件: {mp3_path}")
    return True

def generate_webp_image():
    """通过 generate_webp.py 生成网页截图（独立HTTP服务器 + 动态端口）"""
    logger.info("开始生成网页截图...")
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_webp.py")
    except NameError:
        script_path = os.path.join(BASE_DIR, "generate_webp.py")

    logger.info("调用 generate_webp.py（独立HTTP服务器模式）...")
    result = subprocess.run(
        [sys.executable, script_path],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=120
    )
    for line in result.stdout.split('\n'):
        if line.strip():
            logger.info(f"[WebP] {line.strip()}")

    if result.returncode != 0:
        logger.warning(f"generate_webp.py exited with code {result.returncode}, continuing anyway")
    else:
        logger.info("网页截图生成完成")
    return True

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='每天60秒读懂世界 - 主程序')
    parser.add_argument('--no-scrape', action='store_true', help='跳过爬取知乎并生成RSS的步骤')
    parser.add_argument('--no-tts', action='store_true', help='跳过生成TTS语音文件的步骤')
    parser.add_argument('--no-image', action='store_true', help='跳过生成网页截图的步骤')
    args = parser.parse_args()
    
    # 记录开始时间
    start_time = time.time()
    logger.info("开始执行每天60秒读懂世界任务...")
    
    # 输出当前工作目录和脚本位置
    logger.info(f"当前工作目录: {os.getcwd()}")
    logger.info(f"脚本文件位置: {os.path.abspath(__file__)}")
    logger.info(f"基础目录设置: {BASE_DIR}")
    logger.info(f"爬虫脚本路径: {SCRAPER_PATH}")
    logger.info(f"HTML文件路径: {HTML_PATH}")
    
    # 检查基础目录是否存在
    if not os.path.exists(BASE_DIR):
        logger.error(f"基础目录不存在: {BASE_DIR}")
        logger.info("请确保路径设置正确或创建必要的目录")
        return 1
    
    # 检查爬虫脚本是否存在
    if not os.path.exists(SCRAPER_PATH):
        logger.error(f"爬虫脚本不存在: {SCRAPER_PATH}")
        logger.info("请确保scraper.py文件位于正确位置")
        return 1
    
    # 1. 抓取今日新闻并生成 RSS/HTML
    if not args.no_scrape:
        status = scrape_zhihu_and_generate_rss()
        if status == 'stale':
            logger.warning("上游尚未发布今日数据，本次不更新，等待下一次调度")
            return 3
        if status != 'ok':
            logger.error("获取今日新闻失败")
            return 1

        # 兜底校验：产物日期必须是今天，否则绝不提交
        xml_date = read_xml_data_date(os.path.join(BASE_DIR, "zhihu_daily_news.xml"))
        if xml_date != today_cst():
            logger.error(f"构建结果日期为 {xml_date}，不是今天 {today_cst()}，中止")
            return 1
        logger.info(f"数据日期校验通过: {xml_date}")
    else:
        logger.info("已跳过抓取新闻并生成RSS/HTML的步骤")
    
    # 2. 生成TTS语音文件
    if not args.no_tts:
        if not generate_tts():
            logger.error("生成TTS语音文件的步骤失败")
            return 1
    else:
        logger.info("已跳过生成TTS语音文件的步骤")
    
    # 3. 生成网页截图
    if not args.no_image:
        if not generate_webp_image():
            logger.error("生成网页截图的步骤失败")
            return 1
    else:
        logger.info("已跳过生成网页截图的步骤")
    
    # 记录结束时间
    end_time = time.time()
    execution_time = end_time - start_time
    logger.info(f"任务全部完成！总执行时间: {execution_time:.2f}秒")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
