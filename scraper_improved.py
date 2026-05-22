#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
改进版60秒知天下爬虫
功能：获取完整的新闻列表和内容
"""

import requests
import datetime
import re
import time
import json
import os
import logging
from feedgen.feed import FeedGenerator
import pytz
from bs4 import BeautifulSoup
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_improved.log'),
        logging.StreamHandler()
    ]
)

# 检测操作系统，使用兼容的输出
def safe_print(text):
    """安全的打印函数，兼容Windows编码"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 如果遇到编码错误，尝试使用ASCII兼容的输出
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)

def get_news_from_api():
    """从API获取完整的新闻数据"""
    try:
        # 尝试多个API源
        api_sources = [
            "https://60s.afei7.com/v2/60s",
            "https://api.03c3.cn/zb/api.php",
            "https://api.oick.cn/random/api.php"
        ]
        
        for api_url in api_sources:
            try:
                logging.info(f"尝试API: {api_url}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(api_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    # 处理不同的API格式
                    if api_url == "https://60s.afei7.com/v2/60s":
                        if data.get("code") == 200 and "data" in data:
                            return process_60s_api_data(data["data"])
                    elif api_url == "https://api.03c3.cn/zb/api.php":
                        if data.get("status") == "success":
                            return process_03c3_api_data(data)
                    elif api_url == "https://api.oick.cn/random/api.php":
                        if "data" in data:
                            return process_oick_api_data(data["data"])
                            
            except Exception as e:
                logging.warning(f"API {api_url} 失败: {e}")
                continue
        
        return None
        
    except Exception as e:
        logging.error(f"所有API都失败: {e}")
        return None

def process_60s_api_data(api_data):
    """处理60s.afei7.com的API数据"""
    try:
        content_parts = []
        
        # 处理日期信息
        if "date" in api_data:
            date_str = api_data["date"]
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            year = date_obj.year
            month = date_obj.month
            day = date_obj.day
            
            weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]
            
            # 获取农历信息
            try:
                nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
                nongli_response = requests.get(nongli_url, timeout=10)
                if nongli_response.status_code == 200:
                    nongli_data = nongli_response.json()
                    if nongli_data.get("status") == 1:
                        lunar_date = nongli_data["data"]["lunar_date"]
                        ganzhi = nongli_data["data"]["ganzhi"]
                        content_parts.append(f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}")
                    else:
                        content_parts.append(f"{year}年{month}月{day}日，{weekday}")
                else:
                    content_parts.append(f"{year}年{month}月{day}日，{weekday}")
            except Exception as e:
                logging.warning(f"获取农历信息失败: {e}")
                content_parts.append(f"{year}年{month}月{day}日，{weekday}")
        
        # 处理新闻列表
        if "news" in api_data and isinstance(api_data["news"], list):
            for idx, news_item in enumerate(api_data["news"], 1):
                if isinstance(news_item, str) and news_item.strip():
                    content_parts.append(f"{idx}、{news_item.strip()}")
        
        # 处理微语/金句
        if "tip" in api_data and api_data["tip"]:
            content_parts.append(f"【微语】{api_data['tip']}")
        
        if not content_parts:
            return None
            
        result = {
            'title': f"60秒知天下 {api_data.get('date', '')}",
            'link': api_data.get('link', 'https://60s.afei7.com'),
            'time': api_data.get('created', datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")),
            'content': "\n".join(content_parts)
        }
        
        return result
        
    except Exception as e:
        logging.error(f"处理60s API数据失败: {e}")
        return None

def process_03c3_api_data(api_data):
    """处理03c3.cn的API数据"""
    try:
        content_parts = []
        
        # 获取当前日期
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
        
        # 获取农历信息
        try:
            nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
            nongli_response = requests.get(nongli_url, timeout=10)
            if nongli_response.status_code == 200:
                nongli_data = nongli_response.json()
                if nongli_data.get("status") == 1:
                    lunar_date = nongli_data["data"]["lunar_date"]
                    ganzhi = nongli_data["data"]["ganzhi"]
                    content_parts.append(f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}")
                else:
                    content_parts.append(f"{year}年{month}月{day}日，{weekday}")
            else:
                content_parts.append(f"{year}年{month}月{day}日，{weekday}")
        except Exception as e:
            logging.warning(f"获取农历信息失败: {e}")
            content_parts.append(f"{year}年{month}月{day}日，{weekday}")
        
        # 处理新闻数据
        if "data" in api_data:
            news_data = api_data["data"]
            if isinstance(news_data, list):
                for idx, news_item in enumerate(news_data, 1):
                    if isinstance(news_item, str) and news_item.strip():
                        content_parts.append(f"{idx}、{news_item.strip()}")
            elif isinstance(news_data, dict):
                # 如果是字典格式，尝试提取新闻
                for key, value in news_data.items():
                    if isinstance(value, str) and value.strip() and key != "date":
                        content_parts.append(f"{key}、{value.strip()}")
        
        if not content_parts:
            return None
            
        result = {
            'title': f"60秒知天下 {now.strftime('%Y年%m月%d日')}",
            'link': 'https://03c3.cn',
            'time': now.strftime("%Y/%m/%d %H:%M:%S"),
            'content': "\n".join(content_parts)
        }
        
        return result
        
    except Exception as e:
        logging.error(f"处理03c3 API数据失败: {e}")
        return None

def process_oick_api_data(api_data):
    """处理oick.cn的API数据"""
    try:
        content_parts = []
        
        # 获取当前日期
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
        
        # 获取农历信息
        try:
            nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
            nongli_response = requests.get(nongli_url, timeout=10)
            if nongli_response.status_code == 200:
                nongli_data = nongli_response.json()
                if nongli_data.get("status") == 1:
                    lunar_date = nongli_data["data"]["lunar_date"]
                    ganzhi = nongli_data["data"]["ganzhi"]
                    content_parts.append(f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}")
                else:
                    content_parts.append(f"{year}年{month}月{day}日，{weekday}")
            else:
                content_parts.append(f"{year}年{month}月{day}日，{weekday}")
        except Exception as e:
            logging.warning(f"获取农历信息失败: {e}")
            content_parts.append(f"{year}年{month}月{day}日，{weekday}")
        
        # 处理新闻数据
        if isinstance(api_data, list):
            for idx, news_item in enumerate(api_data, 1):
                if isinstance(news_item, str) and news_item.strip():
                    content_parts.append(f"{idx}、{news_item.strip()}")
        elif isinstance(api_data, dict):
            # 如果是字典格式，尝试提取新闻
            for key, value in api_data.items():
                if isinstance(value, str) and value.strip() and key != "date":
                    content_parts.append(f"{key}、{value.strip()}")
        
        if not content_parts:
            return None
            
        result = {
            'title': f"60秒知天下 {now.strftime('%Y年%m月%d日')}",
            'link': 'https://oick.cn',
            'time': now.strftime("%Y/%m/%d %H:%M:%S"),
            'content': "\n".join(content_parts)
        }
        
        return result
        
    except Exception as e:
        logging.error(f"处理oick API数据失败: {e}")
        return None

def get_news_from_web():
    """从网页获取新闻数据（备用方案）"""
    try:
        # 尝试从搜狗微信搜索获取
        now = datetime.datetime.now()
        date_str = f"{now.month}月{now.day}日"
        
        search_url = f"https://weixin.sogou.com/weixin?type=2&query=60秒知天下+{date_str}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找搜索结果
            search_results = soup.select("ul.news-list li")
            if search_results:
                for result in search_results:
                    title_elem = result.select_one("h3 a")
                    if title_elem and "60秒知天下" in title_elem.get_text():
                        title = title_elem.get_text().strip()
                        link = title_elem.get('href')
                        
                        if link and not link.startswith('http'):
                            link = 'https://weixin.sogou.com' + link
                        
                        # 这里可以进一步获取文章内容，但需要处理反爬
                        content = f"标题：{title}\n链接：{link}\n\n注意：由于反爬机制，无法直接获取完整内容，建议使用API方式。"
                        
                        result_data = {
                            'title': title,
                            'link': link,
                            'time': now.strftime("%Y/%m/%d %H:%M:%S"),
                            'content': content
                        }
                        
                        return result_data
        
        return None
        
    except Exception as e:
        logging.error(f"从网页获取新闻失败: {e}")
        return None

def generate_rss(news_item):
    """生成RSS文件"""
    try:
        fg = FeedGenerator()
        fg.title('60秒知天下')
        fg.link(href='https://weixin.sogou.com', rel='alternate')
        fg.description('60秒知天下RSS - 每日新闻摘要')
        fg.language('zh-CN')
        
        # 添加条目
        fe = fg.add_entry()
        fe.title(news_item['title'])
        fe.link(href=news_item['link'])
        fe.description(news_item['content'])
        
        # 设置发布时间
        now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
        fe.pubDate(now)
        
        # 保存文件
        filename = 'zhihu_daily_news.xml'
        fg.rss_file(filename, pretty=True)
        logging.info(f"RSS文件已生成: {filename}")
        
        return True
        
    except Exception as e:
        logging.error(f"生成RSS文件失败: {e}")
        return False

def main():
    """主函数"""
    logging.info("开始执行改进版爬虫...")
    
    # 首先尝试从API获取
    news_data = get_news_from_api()
    
    if not news_data:
        logging.warning("API获取失败，尝试从网页获取...")
        news_data = get_news_from_web()
    
    if news_data:
        logging.info(f"成功获取新闻: {news_data['title']}")
        
        # 生成RSS
        if generate_rss(news_data):
            logging.info("RSS生成成功")
            safe_print(f"[成功] 成功获取新闻: {news_data['title']}")
            safe_print(f"[内容] 内容预览:")
            content_preview = news_data['content'][:300] + "..." if len(news_data['content']) > 300 else news_data['content']
            safe_print(content_preview)
        else:
            logging.error("RSS生成失败")
            safe_print("[错误] RSS生成失败")
    else:
        logging.error("未能获取任何新闻数据")
        safe_print("[错误] 未能获取任何新闻数据")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
