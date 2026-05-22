import requests
from bs4 import BeautifulSoup
import datetime
import re
import time
import json
import os
from feedgen.feed import FeedGenerator
from urllib.parse import urljoin
import pytz  # 添加时区支持

# 添加Selenium相关导入
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def scrape_zhihu_daily_news():
    url = "https://www.zhihu.com/search?q=60%E7%A7%92%E7%9F%A5%E5%A4%A9%E4%B8%8B&type=content&vertical=article&time_interval=a_day"
    
    # 设置Edge选项
    edge_options = Options()
    
    # 使用本地Edge配置文件
    edge_options.add_argument("--profile-directory=Default")
    edge_options.add_argument("user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Edge\\User Data")
    
    # 禁用自动化标志
    edge_options.add_argument("--disable-blink-features=AutomationControlled")
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    edge_options.add_experimental_option("useAutomationExtension", False)
    
    # 设置浏览器窗口大小
    edge_options.add_argument("--window-size=1920,1080")
    
    # 初始化WebDriver
    print("正在初始化Edge浏览器...")
    driver = webdriver.Edge(options=edge_options)
    
    try:
        # 直接访问搜索页面
        print("正在访问知乎搜索页面...")
        driver.get(url)
        
        # 等待搜索结果加载
        print("等待搜索结果加载...")
        time.sleep(5)
        
        # 打印页面标题，确认页面加载正确
        print(f"页面标题: {driver.title}")
        
        # 保存页面源码以便调试
        with open("zhihu_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("页面源码已保存到 zhihu_page.html")
        
        # 尝试使用多种可能的选择器
        selectors = [
            "div.SearchResult-Card", 
            "div.Card.SearchResult-Card",
            "div.List-item",
            ".Card.SearchResult-Card"
        ]
        
        search_results = None
        for selector in selectors:
            try:
                print(f"尝试使用选择器: {selector}")
                # 使用较长的等待时间
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                search_results = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"使用选择器 {selector} 找到 {len(search_results)} 个结果")
                if search_results:
                    break
            except TimeoutException:
                print(f"选择器 {selector} 超时")
                continue
        
        if not search_results:
            print("未找到任何搜索结果，直接分析页面内容")
            # 如果所有选择器都失败，尝试直接解析整个页面
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # 手动查找包含"60秒知天下"的元素
            all_links = soup.select('a')
            print(f"页面上共有 {len(all_links)} 个链接")
            
            # 准备多种日期格式（Windows兼容）
            now = datetime.datetime.now()
            date_formats = [
                now.strftime("%m月%d日"),       # 04月07日
                f"{now.month}月{now.day}日",    # 4月7日
                now.strftime("%Y年%m月%d日"),   # 2025年04月07日
                f"{now.year}年{now.month}月{now.day}日",  # 2025年4月7日
                now.strftime("%Y-%m-%d"),       # 2025-04-07
                f"{now.month}.{now.day}",       # 4.7
                now.strftime("%m.%d"),          # 04.07
                now.strftime("%Y.%m.%d")        # 2025.04.07
            ]
            print(f"当前日期格式: {date_formats}")
            
            # 寻找包含"60秒知天下"和当前日期的链接
            target_links = []
            for link in all_links:
                link_text = link.get_text()
                if "60秒知天下" in link_text:
                    date_found = False
                    for date_format in date_formats:
                        if date_format in link_text:
                            date_found = True
                            break
                    if date_found:
                        print(f"找到符合条件的链接: {link_text}")
                        href = link.get('href', '')
                        if href:
                            if href.startswith('//'):
                                href = 'https:' + href
                            elif not href.startswith('http'):
                                href = urljoin('https://www.zhihu.com', href)
                            target_links.append({
                                'title': link_text,
                                'link': href
                            })
            
            if target_links:
                latest_news = target_links[0]  # 取第一个结果
                
                # 获取文章内容
                print(f"获取最新文章内容: {latest_news['link']}")
                content = get_article_content_with_selenium(driver, latest_news['link'])
                if content:
                    latest_news['content'] = content
                    latest_news['time'] = '刚刚'  # 默认时间
                    
                    # 生成RSS文件
                    generate_rss(latest_news)
                    
                    return latest_news
                
            return None
        
        # 准备多种日期格式（Windows兼容）
        now = datetime.datetime.now()
        date_formats = [
            now.strftime("%m月%d日"),       # 04月07日
            f"{now.month}月{now.day}日",    # 4月7日
            now.strftime("%Y年%m月%d日"),   # 2025年04月07日
            f"{now.year}年{now.month}月{now.day}日",  # 2025年4月7日
            now.strftime("%Y-%m-%d"),       # 2025-04-07
            f"{now.month}.{now.day}",       # 4.7
            now.strftime("%m.%d"),          # 04.07
            now.strftime("%Y.%m.%d")        # 2025.04.07
        ]
        print(f"当前日期格式: {date_formats}")
        
        # 先寻找包含"60秒知天下早报"的标题（第一个标题）
        for result in search_results:
            result_html = result.get_attribute('outerHTML')
            result_soup = BeautifulSoup(result_html, 'html.parser')
            
            # 尝试多种可能的标题选择器
            title_selectors = [
                'h2.ContentItem-title span div div',
                'div.RichText h3',
                'span.Highlight',
                'a[target="_blank"]'
            ]
            
            title_element = None
            title_text = ""
            
            for selector in title_selectors:
                title_element = result_soup.select_one(selector)
                if title_element:
                    title_text = title_element.get_text()
                    print(f"找到标题: {title_text}")
                    break
            
            if not title_text:
                continue
                
            # 检查是否是我们想要的标题（包含"60秒知天下"和"早报"）
            if "60秒知天下" in title_text and "早报" in title_text:
                print(f"找到符合条件的标题: {title_text}")
                
                # 获取链接
                link_selectors = [
                    'h2.ContentItem-title span div div a',
                    'a[target="_blank"]',
                    'a'
                ]
                
                link = ""
                for selector in link_selectors:
                    link_elements = result_soup.select(selector)
                    for element in link_elements:
                        link = element.get('href', '')
                        if link:
                            break
                    if link:
                        break
                
                if not link:
                    continue
                
                if link.startswith("//"):
                    link = "https:" + link
                elif not link.startswith('http'):
                    link = urljoin('https://www.zhihu.com', link)
                
                print(f"找到链接: {link}")
                
                # 获取文章内容
                print(f"获取文章内容: {link}")
                content = get_article_content_with_selenium(driver, link)
                
                if content:
                    # 获取发布时间
                    time_selectors = [
                        'div.ContentItem-time span.SearchItem-time',
                        'span.SearchItem-time',
                        'span.ContentItem-time'
                    ]
                    
                    time_text = "刚刚"  # 默认值
                    for selector in time_selectors:
                        time_element = result_soup.select_one(selector)
                        if time_element:
                            time_text = time_element.get_text()
                            print(f"发布时间: {time_text}")
                            break
                    
                    latest_news = {
                        'title': title_text,
                        'link': link,
                        'time': time_text,
                        'content': content
                    }
                    
                    # 生成RSS文件
                    generate_rss(latest_news)
                    
                    return latest_news
        
        # 如果没有找到"60秒知天下早报"，再尝试找包含当前日期的任何"60秒知天下"
        latest_news = None
        latest_time_value = float('inf')  # 用于比较时间，初始值设为无穷大
        
        for result in search_results:
            result_html = result.get_attribute('outerHTML')
            result_soup = BeautifulSoup(result_html, 'html.parser')
            
            # 尝试多种可能的标题选择器
            title_selectors = [
                'h2.ContentItem-title span div div',
                'div.RichText h3',
                'span.Highlight',
                'a[target="_blank"]'
            ]
            
            title_element = None
            title_text = ""
            
            for selector in title_selectors:
                title_element = result_soup.select_one(selector)
                if title_element:
                    title_text = title_element.get_text()
                    break
            
            if not title_text:
                continue
                
            # 检查标题是否包含"60秒知天下"和当前日期
            if "60秒知天下" in title_text:
                date_found = False
                for date_format in date_formats:
                    if date_format in title_text:
                        date_found = True
                        break
                
                if date_found:
                    print(f"找到符合日期条件的标题: {title_text}")
                    
                    # 获取发布时间（尝试多种可能的选择器）
                    time_selectors = [
                        'div.ContentItem-time span.SearchItem-time',
                        'span.SearchItem-time',
                        'span.ContentItem-time'
                    ]
                    
                    time_element = None
                    time_text = "刚刚"  # 默认值
                    
                    for selector in time_selectors:
                        time_element = result_soup.select_one(selector)
                        if time_element:
                            time_text = time_element.get_text()
                            print(f"发布时间: {time_text}")
                            break
                    
                    # 计算时间值（用于比较新旧）
                    time_value = calculate_time_value(time_text)
                    
                    # 获取链接（尝试多种可能的选择器）
                    link_selectors = [
                        'h2.ContentItem-title span div div a',
                        'a[target="_blank"]',
                        'a'
                    ]
                    
                    link_element = None
                    link = ""
                    
                    for selector in link_selectors:
                        link_elements = result_soup.select(selector)
                        for element in link_elements:
                            link = element.get('href', '')
                            if link and ("zhuanlan.zhihu.com" in link or "zhihu.com" in link):
                                break
                        if link:
                            break
                    
                    if not link:
                        continue
                    
                    if link.startswith("//"):
                        link = "https:" + link
                    elif not link.startswith('http'):
                        link = urljoin('https://www.zhihu.com', link)
                        
                    print(f"找到链接: {link}")
                    
                    # 如果这是目前为止最新的新闻，则更新
                    if time_value < latest_time_value:
                        latest_time_value = time_value
                        latest_news = {
                            'title': title_text,
                            'link': link,
                            'time': time_text
                        }
        
        if latest_news:
            # 获取文章内容
            print(f"获取最新文章内容: {latest_news['link']}")
            content = get_article_content_with_selenium(driver, latest_news['link'])
            if content:
                latest_news['content'] = content
                
                # 生成RSS文件
                generate_rss(latest_news)
                
                return latest_news
        
        # 如果上面的方法都没找到结果，尝试直接找第一个包含"60秒知天下"的结果
        if not latest_news:
            print("尝试备用方法：直接寻找包含'60秒知天下'的第一个结果")
            for result in search_results:
                result_html = result.get_attribute('outerHTML')
                result_soup = BeautifulSoup(result_html, 'html.parser')
                
                # 尝试多种可能的标题选择器
                title_selectors = [
                    'h2.ContentItem-title span div div',
                    'div.RichText h3',
                    'span.Highlight',
                    'a[target="_blank"]'
                ]
                
                title_element = None
                title_text = ""
                
                for selector in title_selectors:
                    title_element = result_soup.select_one(selector)
                    if title_element:
                        title_text = title_element.get_text()
                        break
                
                if "60秒知天下" in title_text:
                    print(f"找到包含'60秒知天下'的标题: {title_text}")
                    
                    # 获取链接
                    link_selectors = [
                        'h2.ContentItem-title span div div a',
                        'a[target="_blank"]',
                        'a'
                    ]
                    
                    link = ""
                    for selector in link_selectors:
                        link_elements = result_soup.select(selector)
                        for element in link_elements:
                            link = element.get('href', '')
                            if link:
                                break
                        if link:
                            break
                    
                    if not link:
                        continue
                    
                    if link.startswith("//"):
                        link = "https:" + link
                    elif not link.startswith('http'):
                        link = urljoin('https://www.zhihu.com', link)
                    
                    print(f"找到链接: {link}")
                    
                    # 获取文章内容
                    print(f"获取文章内容: {link}")
                    content = get_article_content_with_selenium(driver, link)
                    
                    if content:
                        latest_news = {
                            'title': title_text,
                            'link': link,
                            'time': '刚刚',  # 默认时间
                            'content': content
                        }
                        
                        # 生成RSS文件
                        generate_rss(latest_news)
                        
                        return latest_news
                    
        return None
    
    finally:
        # 关闭浏览器
        print("关闭浏览器...")
        driver.quit()

def calculate_time_value(time_text):
    """
    计算时间值，用于比较新旧
    较小的值表示更新的内容
    """
    if "分钟前" in time_text:
        minutes = int(time_text.split()[0])
        return minutes
    elif "小时前" in time_text:
        hours = int(time_text.split()[0])
        return hours * 60
    elif "昨天" in time_text:
        return 24 * 60
    elif re.match(r'\d{4}-\d{2}-\d{2}', time_text):
        # 日期格式，转换为距今的分钟数
        date = datetime.datetime.strptime(time_text, "%Y-%m-%d")
        now = datetime.datetime.now()
        delta = now - date
        return delta.days * 24 * 60
    return float('inf')  # 无法解析的时间返回无穷大

def get_article_content_with_selenium(driver, url):
    """使用Selenium获取文章内容"""
    try:
        # 访问文章页面
        print(f"访问文章页面: {url}")
        driver.get(url)
        
        # 等待页面加载
        print("等待文章内容加载...")
        time.sleep(5)
        
        # 尝试多种可能的内容选择器
        content_selectors = [
            "div.RichText.ztext.Post-RichText",
            "div.RichText",
            "article.Post-Main",
            "div.Post-RichTextContainer"
        ]
        
        content_element = None
        for selector in content_selectors:
            try:
                print(f"尝试使用内容选择器: {selector}")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                content_element = driver.find_element(By.CSS_SELECTOR, selector)
                if content_element:
                    print(f"找到内容元素，使用选择器: {selector}")
                    break
            except (TimeoutException, NoSuchElementException):
                print(f"选择器 {selector} 未找到内容")
                continue
        
        if not content_element:
            print("未找到内容元素，保存页面用于调试")
            with open("article_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("文章页面源码已保存到 article_page.html")
            return None
        
        # 滚动页面以加载完整内容
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        
        # 获取页面HTML
        html = content_element.get_attribute('outerHTML')
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取段落文本
        paragraphs = []
        for p in soup.select('p'):
            text = p.get_text()
            if text.strip():
                paragraphs.append(text.strip())
        
        if not paragraphs:
            # 如果没有找到段落，获取整个内容的文本
            text = soup.get_text()
            if text.strip():
                paragraphs = [line.strip() for line in text.split('\n') if line.strip()]
                
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"获取文章内容时出错: {e}")
        return None

def get_article_content(url, headers):
    """获取文章内容（使用requests）"""
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 获取文章内容
        content_element = soup.select_one('div.RichText.ztext.Post-RichText')
        if not content_element:
            return None
            
        # 提取段落文本
        paragraphs = []
        for p in content_element.select('p'):
            text = p.get_text()
            if text.strip():
                paragraphs.append(text.strip())
                
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"获取文章内容时出错: {e}")
        return None

def generate_rss(news_item):
    """生成RSS格式文件"""
    fg = FeedGenerator()
    fg.title('知乎60秒知天下')
    fg.link(href='https://www.zhihu.com', rel='alternate')
    fg.description('知乎60秒知天下RSS')
    fg.language('zh-CN')
    
    # 添加条目
    fe = fg.add_entry()
    fe.title(news_item['title'])
    fe.link(href=news_item['link'])
    fe.description(news_item['content'])
    
    # 设置发布时间（添加时区信息）
    now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
    fe.pubDate(now)
    
    # 保存RSS文件
    filename = 'zhihu_daily_news.xml'
    fg.rss_file(filename, pretty=True)
    print(f"RSS文件已生成: {filename}")

if __name__ == "__main__":
    news = scrape_zhihu_daily_news()
    if news:
        print(f"已获取最新60秒知天下: {news['title']}")
        print(f"链接: {news['link']}")
        print(f"发布时间: {news['time']}")
    else:
        print("未找到符合条件的60秒知天下") 
