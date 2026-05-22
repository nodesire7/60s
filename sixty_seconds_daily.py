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
    """生成网页截图"""
    logger.info("开始生成网页截图...")

    # 检查本地服务器是否运行
    if not check_local_server():
        logger.error("本地服务器 (localhost:1929) 未运行，无法生成网页截图")
        logger.info("请确保本地HTTP服务器正在运行，例如使用: python -m http.server 1929")
        return False

    try:
        # 检查是否已安装必要的库
        import importlib.util
        
        # 检查selenium是否已安装
        if importlib.util.find_spec("selenium") is None:
            logger.info("正在安装selenium...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium"])
            logger.info("selenium安装完成")
        
        # 检查webdriver_manager是否已安装
        if importlib.util.find_spec("webdriver_manager") is None:
            logger.info("正在安装webdriver_manager...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver_manager"])
            logger.info("webdriver_manager安装完成")
        
        # 检查PIL是否已安装
        if importlib.util.find_spec("PIL") is None:
            logger.info("正在安装Pillow...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
            logger.info("Pillow安装完成")
        
        # 导入必要的库
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        from PIL import Image, ImageEnhance
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        import io
        
        # 设置固定宽度
        target_width = 650
        
        # 初始化浏览器
        logger.info("初始化浏览器...")
        driver = None
        driver_initialized = False
        
        # 方法1: 优先尝试使用Chrome浏览器（通常更容易管理驱动）
        try:
            logger.info("尝试使用Chrome浏览器...")
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless=new")  # 使用新的无头模式
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--hide-scrollbars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"--force-device-scale-factor=2.0")
            chrome_options.add_argument(f"--window-size={target_width+16},2000")
            
            # 尝试使用WebDriver Manager
            try:
                logger.info("使用ChromeDriver Manager...")
                driver_manager = ChromeDriverManager()
                driver_path = driver_manager.install()
                logger.info(f"ChromeDriver路径: {driver_path}")
                driver = webdriver.Chrome(
                    service=ChromeService(driver_path),
                    options=chrome_options
                )
                driver_initialized = True
                logger.info("成功使用Chrome浏览器（WebDriver Manager）")
            except Exception as wdm_error:
                logger.warning(f"ChromeDriver Manager失败: {wdm_error}")
                # 尝试直接使用系统PATH中的Chrome
                try:
                    logger.info("尝试使用系统PATH中的Chrome驱动...")
                    driver = webdriver.Chrome(options=chrome_options)
                    driver_initialized = True
                    logger.info("成功使用Chrome浏览器（系统PATH）")
                except Exception as path_error:
                    logger.warning(f"系统PATH Chrome驱动失败: {path_error}")
        except Exception as chrome_error:
            logger.warning(f"Chrome浏览器初始化失败: {chrome_error}")
        
        # 方法2: 如果Chrome失败，尝试使用Edge浏览器
        if not driver_initialized:
            try:
                logger.info("尝试使用Edge浏览器...")
                edge_options = EdgeOptions()
                edge_options.add_argument("--headless=new")
                edge_options.add_argument("--disable-gpu")
                edge_options.add_argument("--hide-scrollbars")
                edge_options.add_argument("--disable-extensions")
                edge_options.add_argument(f"--force-device-scale-factor=2.0")
                edge_options.add_argument(f"--window-size={target_width+16},2000")
                
                # 尝试使用WebDriver Manager
                try:
                    logger.info("使用EdgeDriver Manager...")
                    driver_manager = EdgeChromiumDriverManager()
                    driver_path = driver_manager.install()
                    logger.info(f"EdgeDriver路径: {driver_path}")
                    driver = webdriver.Edge(
                        service=EdgeService(driver_path),
                        options=edge_options
                    )
                    driver_initialized = True
                    logger.info("成功使用Edge浏览器（WebDriver Manager）")
                except Exception as wdm_error:
                    logger.warning(f"EdgeDriver Manager失败: {wdm_error}")
                    # 尝试直接使用系统PATH中的Edge
                    try:
                        logger.info("尝试使用系统PATH中的Edge驱动...")
                        driver = webdriver.Edge(options=edge_options)
                        driver_initialized = True
                        logger.info("成功使用Edge浏览器（系统PATH）")
                    except Exception as path_error:
                        logger.warning(f"系统PATH Edge驱动失败: {path_error}")
            except Exception as edge_error:
                logger.warning(f"Edge浏览器初始化失败: {edge_error}")
        
        if not driver_initialized:
            raise Exception("所有浏览器驱动初始化方法都失败了，请检查网络连接或手动安装浏览器驱动")
        
        try:
            
            # 设置CSS以确保捕获所有内容并增强文字显眼度
            driver.execute_script("""
                // 添加CSS确保所有内容可见且文字更加醒目
                var style = document.createElement('style');
                style.type = 'text/css';
                style.innerHTML = `
                    body { 
                        margin: 0 !important; 
                        padding: 0 !important;
                        background-color: white !important;
                        width: 650px !important;
                        max-width: 650px !important;
                        overflow-x: hidden !important;
                        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif !important;
                        -webkit-font-smoothing: antialiased !important;
                        -moz-osx-font-smoothing: grayscale !important;
                        text-rendering: optimizeLegibility !important;
                        font-size: 120% !important; /* 全局字体放大10% */
                    }
                    html { 
                        width: 650px !important;
                        max-width: 650px !important;
                        overflow-x: hidden !important;
                    }
                    html, body { 
                        height: auto !important; 
                        overflow-y: visible !important;
                    }
                    * {
                        max-width: 650px !important;
                        box-sizing: border-box !important;
                    }
                    /* 标题部分增强 */
                    .title {
                        font-weight: 800 !important;
                        font-size: 1.4em !important; /* 更大的标题 */
                        color: #000000 !important;
                        letter-spacing: 0.05em !important;
                    }
                    /* 日期卡片文字增强 */
                    .date-card {
                        font-weight: 700 !important;
                        font-size: 1.25em !important; /* 更大的日期 */
                    }
                    .date-lunar, .lunar-date {
                        font-weight: 700 !important;
                        letter-spacing: 0.03em !important;
                        font-size: 1.15em !important; /* 更大的农历日期 */
                    }
                    /* 新闻项目文字增强 */
                    .news-item {
                        font-weight: 700 !important;
                        font-size: 1.5em !important; /* 更大的新闻条目 */
                        line-height: 1.6 !important;
                        margin: 15px 0 !important;
                        letter-spacing: 0.03em !important;
                        color: #000000 !important;
                        text-shadow: 0 0 1px rgba(0,0,0,0.1) !important;
                        padding: 5px 0 !important;
                    }
                    /* 数字标记增强 */
                    .news-item .index {
                        font-weight: 900 !important;
                        color: #2196F3 !important;
                        font-size: 1.25em !important; /* 更大的数字标记 */
                        text-shadow: 0 0 2px rgba(33,150,243,0.2) !important;
                    }
                    /* 金句/微语增强 */
                    .hitokoto, .weiyu, .quote {
                        font-style: italic !important;
                        font-weight: 700 !important;
                        color: #333333 !important;
                        font-size: 1.2em !important; /* 更大的微语/金句 */
                        letter-spacing: 0.05em !important;
                        text-align: center !important;
                        padding: 12px !important;
                    }
                    /* 卡片增强 */
                    .card {
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
                        background-color: #ffffff !important;
                        border-radius: 8px !important;
                        padding: 10px !important;
                        margin: 8px 0 !important;
                    }
                    /* 所有段落文字放大 */
                    p {
                        font-size: 1.2em !important;
                    }
                    /* 统一文字颜色 */
                    p, div, span, h1, h2, h3, h4, h5, h6, li {
                        color: #000000 !important;
                    }
                    /* 为所有元素增加更好的间距 */
                    .container, .content {
                        padding: 8px !important;
                    }
                `;
                document.getElementsByTagName('head')[0].appendChild(style);
                
                // 增强数字标签的视觉效果
                document.querySelectorAll('.news-item').forEach(function(item) {
                    // 查找开头的数字并增强其显示
                    let text = item.textContent || item.innerText;
                    let match = text.match(/^(\\d+)[、.]/);
                    if (match) {
                        // 分离数字标记和内容
                        let index = match[1];
                        let content = text.replace(/^\\d+[、.]\\s*/, '');

                        // 清空原内容，替换为带有增强样式的内容
                        item.innerHTML = '<span class="index">' + index + '、</span> ' + content;
                    }
                });
                
                // 全局增大文字
                document.body.style.fontSize = "120%";
            """)
            
            # 访问网络页面
            page_url = "http://localhost:1929/60s.html"
            logger.info(f"访问网页: {page_url}")
            driver.get(page_url)
            
            # 等待页面加载
            logger.info("等待页面加载完成...")
            try:
                wait = WebDriverWait(driver, 10)
                wait.until(lambda d: len(d.find_elements(By.CLASS_NAME, 'news-item')) > 0)
                logger.info("页面已成功加载内容")
            except Exception as e:
                logger.warning(f"智能等待失败，使用固定等待时间: {e}")
                time.sleep(5)
            
            # 强制设置视口和内容宽度为650
            driver.execute_script("""
                // 设置视口宽度
                document.querySelector('meta[name="viewport"]').setAttribute(
                    'content', 
                    'width=650, initial-scale=1.0'
                );
                
                // 重新检查并设置body宽度
                document.body.style.width = '650px';
                document.body.style.maxWidth = '650px';
                document.documentElement.style.width = '650px';
                document.documentElement.style.maxWidth = '650px';
            """)
            
            # 等待调整生效
            time.sleep(1)
            
            # 获取页面实际内容高度，特别检查页脚元素
            true_height = driver.execute_script("""
                // 找到文档中所有元素
                var allElements = document.getElementsByTagName('*');
                var maxBottom = 0;
                var footerBottom = 0;
                
                // 特别寻找页脚元素
                var footerElements = document.querySelectorAll('footer, .footer, #footer, [class*="footer"], [id*="footer"], small, [class*="copyright"], [id*="copyright"]');
                if (footerElements.length > 0) {
                    console.log("找到" + footerElements.length + "个可能的页脚元素");
                    for (var i = 0; i < footerElements.length; i++) {
                        var rect = footerElements[i].getBoundingClientRect();
                        var bottom = rect.top + rect.height;
                        console.log("页脚元素 #" + i + " 底部位置: " + bottom + "px");
                        if (bottom > footerBottom) {
                            footerBottom = bottom;
                        }
                    }
                }
                
                // 遍历所有元素寻找页面底部
                for (var i = 0; i < allElements.length; i++) {
                    var element = allElements[i];
                    var rect = element.getBoundingClientRect();
                    var bottom = rect.top + rect.height;
                    if (bottom > maxBottom) {
                        maxBottom = bottom;
                    }
                }
                
                // 使用页脚位置或最大底部位置
                var finalHeight = Math.max(footerBottom, maxBottom);
                console.log("页脚底部: " + footerBottom + "px, 最大底部: " + maxBottom + "px");
                
                // 添加足够的边距确保所有内容可见
                return Math.ceil(finalHeight) + 50;  // 添加50px边距确保页脚完全可见
            """)
            
            # 调试输出所有元素及其位置
            driver.execute_script("""
                // 输出所有元素的位置信息，帮助调试
                var allElements = document.getElementsByTagName('*');
                for (var i = 0; i < allElements.length; i++) {
                    if (i % 50 === 0) { // 每50个元素输出一次，避免过多日志
                        var element = allElements[i];
                        var rect = element.getBoundingClientRect();
                        if (rect.top > document.documentElement.clientHeight - 300) { // 只关注靠近底部的元素
                            console.log("元素 [" + element.tagName + (element.id ? "#"+element.id : "") +
                                        (element.className ? "."+element.className.replace(/\\s+/g, ".") : "") +
                                        "] 位置: top=" + rect.top + ", height=" + rect.height +
                                        ", bottom=" + (rect.top + rect.height) + "px");
                        }
                    }
                }
            """)
            
            # 重新设置窗口大小
            driver.set_window_size(target_width + 16, true_height + 100)  # 增加更多边距确保完整捕获
            logger.info(f"调整窗口大小为: {target_width + 16} x {true_height + 100}px")
            
            # 等待渲染完成
            time.sleep(1)
            
            # 获取当前实际内容尺寸
            content_size = driver.execute_script("""
                return {
                    width: document.body.offsetWidth,
                    scrollWidth: document.body.scrollWidth,
                    clientWidth: document.body.clientWidth,
                    scrollHeight: document.body.scrollHeight,
                    offsetHeight: document.body.offsetHeight
                };
            """)
            logger.info(f"页面实际内容尺寸: {content_size}")
            
            # 获取完整页面截图
            logger.info("获取完整页面截图...")
            full_page_screenshot = driver.execute_script("""
                // 返回完整页面的高度
                return document.documentElement.scrollHeight;
            """)
            
            logger.info(f"页面完整高度: {full_page_screenshot}px")
            
            # 使用滚动捕获整个页面
            original_screenshot = driver.get_screenshot_as_png()
            screenshot = Image.open(io.BytesIO(original_screenshot))
            logger.info(f"完整截图尺寸: {screenshot.width}x{screenshot.height}")
            
            # 确保宽度正确
            if screenshot.width != target_width:
                logger.info(f"调整截图宽度从 {screenshot.width}px 到 {target_width}px")
                # 保持宽高比
                new_height = int(screenshot.height * (target_width / screenshot.width))
                screenshot = screenshot.resize((target_width, new_height), Image.LANCZOS)
                logger.info(f"调整后截图尺寸: {screenshot.width}x{screenshot.height}")
            
            # 增强图像对比度和锐度
            enhancer = ImageEnhance.Contrast(screenshot)
            screenshot = enhancer.enhance(1.2)  # 增加20%对比度
            
            enhancer = ImageEnhance.Sharpness(screenshot)
            screenshot = enhancer.enhance(1.3)  # 增加30%锐度
            
            # 保存WebP格式图片（提高质量设置）
            webp_path = os.path.join(OUTPUT_DIR, "60s.webp")
            screenshot.save(webp_path, format="WEBP", quality=100, method=6, lossless=False)
            logger.info(f"已成功生成网页截图: {webp_path}")
            
            return True
            
        finally:
            # 确保关闭浏览器
            if driver:
                try:
                    driver.quit()
                    logger.info("浏览器已关闭")
                except Exception as e:
                    logger.warning(f"关闭浏览器时出错: {e}")
    except Exception as e:
        logger.error(f"生成网页截图时出错: {e}")
        return False

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
