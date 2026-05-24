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
