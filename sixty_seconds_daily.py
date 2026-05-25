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

def fetch_data_from_api():
    """从API获取数据"""
    api_url = "https://zaobao.wpush.cn/api/zaobao/today"
    logger.info(f"尝试从API获取数据: {api_url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == "success" and data.get("code") == 200 and "data" in data:
            logger.info("成功从API获取数据")
            return data["data"]
        else:
            logger.warning(f"API返回数据格式异常: {data}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"从API获取数据失败: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"API返回数据JSON解析失败: {e}")
        return None
    except Exception as e:
        logger.warning(f"从API获取数据时发生未知错误: {e}")
        return None

def generate_rss_from_api_data(api_data):
    """从API数据生成RSS文件"""
    try:
        fg = FeedGenerator()
        fg.title('60秒知天下')
        fg.link(href='https://zaobao.wpush.cn', rel='alternate')
        fg.description('60秒知天下RSS')
        fg.language('zh-CN')
        
        # 解析日期
        date_str = api_data.get("date", "")
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                year, month, day = date_obj.year, date_obj.month, date_obj.day
            except:
                now = datetime.now()
                year, month, day = now.year, now.month, now.day
        else:
            now = datetime.now()
            year, month, day = now.year, now.month, now.day
        
        # 获取星期
        date_obj = datetime(year, month, day)
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]
        
        # 获取农历信息
        lunar_date = api_data.get("lunar_date", "")
        if not lunar_date:
            # 如果API没有提供农历信息，尝试从农历API获取
            try:
                nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                nongli_response = requests.get(nongli_url, headers=headers, timeout=5)
                if nongli_response.status_code == 200:
                    nongli_data = json.loads(nongli_response.text)
                    if nongli_data.get("status") == 1 and "data" in nongli_data:
                        data = nongli_data["data"]
                        lunar_date = data.get("lunar_date", "")
                        ganzhi = data.get("ganzhi", "")
                        zodiac = data.get("zodiac", "")
                        if zodiac and zodiac.endswith('年'):
                            zodiac = zodiac.rstrip('年')
                        if ganzhi and zodiac:
                            lunar_info = f"{ganzhi}({zodiac}年) {lunar_date}"
                        else:
                            lunar_info = lunar_date if lunar_date else ""
                    else:
                        lunar_info = ""
                else:
                    lunar_info = ""
            except Exception as e:
                logger.warning(f"获取农历信息失败: {e}")
                lunar_info = ""
        else:
            # API提供了农历日期，尝试获取干支和生肖信息
            try:
                nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                nongli_response = requests.get(nongli_url, headers=headers, timeout=5)
                if nongli_response.status_code == 200:
                    nongli_data = json.loads(nongli_response.text)
                    if nongli_data.get("status") == 1 and "data" in nongli_data:
                        data = nongli_data["data"]
                        ganzhi = data.get("ganzhi", "")
                        zodiac = data.get("zodiac", "")
                        if zodiac and zodiac.endswith('年'):
                            zodiac = zodiac.rstrip('年')
                        if ganzhi and zodiac:
                            lunar_info = f"{ganzhi}({zodiac}年) {lunar_date}"
                        else:
                            lunar_info = lunar_date
                    else:
                        lunar_info = lunar_date
                else:
                    lunar_info = lunar_date
            except Exception as e:
                logger.warning(f"获取干支信息失败，使用API提供的农历日期: {e}")
                lunar_info = lunar_date
        
        # 构建标题
        title = api_data.get("title", f"{year}年{month}月{day}日，{weekday}，在这里每天读懂世界")
        
        # 构建内容
        news_list = api_data.get("news", [])
        weiyu = api_data.get("weiyu", "")
        
        content_lines = []
        # 添加日期行
        if lunar_info:
            # 如果lunar_info已经包含干支信息（格式：干支(生肖年) 农历日期），则直接使用
            if "(" in lunar_info and "年)" in lunar_info:
                date_line = f"{year}年{month}月{day}日，{weekday}，{lunar_info}"
            else:
                date_line = f"{year}年{month}月{day}日，{weekday}，农历{lunar_info}"
        else:
            date_line = f"{year}年{month}月{day}日，{weekday}"
        content_lines.append(date_line)
        content_lines.append("")
        
        # 添加新闻条目
        for news_item in news_list:
            content_lines.append(news_item)
        
        # 添加微语
        if weiyu:
            content_lines.append("")
            content_lines.append(weiyu)
        
        content = "\n".join(content_lines)
        
        # 创建RSS条目
        fe = fg.add_entry()
        fe.title(title)
        fe.link(href="https://zaobao.wpush.cn")
        fe.description(content)
        
        # 设置发布日期
        pub_date = datetime(year, month, day, tzinfo=pytz.timezone('Asia/Shanghai'))
        fe.pubDate(pub_date)
        
        # 保存RSS文件
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
    lunar_info = ""
    lunar_date = api_data.get("lunar_date", "")
    ganzhi = api_data.get("ganzhi", "")
    zodiac = api_data.get("zodiac", "")

    if not ganzhi or not zodiac:
        # 调用农历API获取完整干支生肖信息
        try:
            nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            nongli_response = requests.get(nongli_url, headers=headers, timeout=5)
            if nongli_response.status_code == 200:
                nongli_data = json.loads(nongli_response.text)
                if nongli_data.get("status") == 1 and "data" in nongli_data:
                    nd = nongli_data["data"]
                    ganzhi = nd.get("ganzhi", ganzhi)
                    zodiac = nd.get("zodiac", zodiac)
                    if not lunar_date:
                        lunar_date = nd.get("lunar_date", "")
        except Exception as e:
            logger.warning(f"获取干支生肖信息失败: {e}")

    if ganzhi and zodiac:
        if zodiac.endswith('年'):
            zodiac = zodiac.rstrip('年')
        lunar_info = f"{ganzhi}({zodiac}年) {lunar_date}" if lunar_date else f"{ganzhi}({zodiac}年)"
    elif lunar_date:
        lunar_info = lunar_date

    # 生成标题
    title = api_data.get("title", f"{year}年{month}月{day}日，{weekday_cn}，在这里每天读懂世界")
    gregorian_date = f"{year}年{month}月{day}日"

    # 构建内容文本（用于解析新闻条目和微语）
    content = api_data.get("content", "")
    if not content:
        news_list = api_data.get("news", [])
        if news_list:
            # API返回的news条目已自带序号（如"1、xxxx"），直接使用
            content_lines = [title, ""]
            for news_item in news_list:
                content_lines.append(news_item)
            content_lines.append("")
            weiyu = api_data.get("weiyu", "")
            if weiyu:
                content_lines.append(f"【微语】{weiyu}")
            content = "\n".join(content_lines)

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
    sync_time = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)} 05:00"

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


def scrape_zhihu_and_generate_rss():
    """爬取知乎并生成RSS文件（优先使用API数据）"""
    # 首先尝试从API获取数据
    api_data = fetch_data_from_api()
    
    if api_data:
        logger.info("成功从API获取数据，正在生成RSS文件...")
        if generate_rss_from_api_data(api_data):
            xml_path = os.path.join(BASE_DIR, "zhihu_daily_news.xml")
            if os.path.exists(xml_path):
                logger.info(f"RSS文件已成功生成: {xml_path}")
                # 同时生成静态HTML（数据直接嵌入，无需JS fetch）
                logger.info("正在生成静态HTML页面...")
                if generate_static_html(api_data):
                    logger.info("静态HTML页面已成功生成")
                else:
                    logger.warning("静态HTML生成失败，但不影响主流程")
                return True
            else:
                logger.error(f"RSS文件生成失败，未找到文件: {xml_path}")
                return False
        else:
            logger.error("从API数据生成RSS文件失败")
            return False
    
    # 如果API获取失败，则使用原来的知乎爬取方式
    logger.info("API获取数据失败，尝试从知乎爬取数据...")
    success, output = run_command(f"python {SCRAPER_PATH} -r", cwd=BASE_DIR)
    if not success:
        logger.error("爬取知乎失败")
        return False
    
    # 检查XML文件是否已生成 - 直接在BASE_DIR中检查，因为scraper.py会直接在其运行目录生成XML
    xml_path = os.path.join(BASE_DIR, "zhihu_daily_news.xml")
    if not os.path.exists(xml_path):
        logger.error(f"未找到生成的XML文件: {xml_path}")
        return False
    
    # 由于OUTPUT_DIR与BASE_DIR相同，文件已经在正确位置，不需要复制
    logger.info(f"RSS文件已成功生成: {xml_path}")
    return True

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
    
    # 1. 爬取知乎并生成RSS
    if not args.no_scrape:
        if not scrape_zhihu_and_generate_rss():
            logger.error("爬取知乎并生成RSS的步骤失败")
            return 1
    else:
        logger.info("已跳过爬取知乎并生成RSS的步骤")
    
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
