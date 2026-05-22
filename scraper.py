import requests
from bs4 import BeautifulSoup
import datetime
import re
import time
import json
import os
import logging
import sys
import platform
import subprocess
import shutil
import tempfile
# fcntl在Windows上不可用，需要条件导入
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
import atexit
from pathlib import Path
from feedgen.feed import FeedGenerator
from urllib.parse import urljoin, quote
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

# 全局变量
LOCK_FILE = None
LOCK_FD = None

def acquire_lock():
    """获取进程锁，防止多个实例同时运行"""
    global LOCK_FILE, LOCK_FD

    try:
        # 创建锁文件路径
        lock_dir = Path(tempfile.gettempdir()) / "scraper_locks"
        lock_dir.mkdir(exist_ok=True)
        LOCK_FILE = lock_dir / "scraper.lock"

        # 在Windows上使用不同的锁机制
        if platform.system() == "Windows":
            try:
                # 尝试创建独占文件
                LOCK_FD = open(LOCK_FILE, 'w')
                LOCK_FD.write(str(os.getpid()))
                LOCK_FD.flush()
                logging.info(f"获取进程锁成功: {LOCK_FILE}")
                return True
            except IOError:
                logging.error("另一个scraper实例正在运行")
                return False
        else:
            # Unix系统使用fcntl
            if not HAS_FCNTL:
                logging.warning("fcntl模块不可用，使用文件锁替代")
                try:
                    LOCK_FD = open(LOCK_FILE, 'x')  # 独占创建
                    LOCK_FD.write(str(os.getpid()))
                    LOCK_FD.flush()
                    logging.info(f"获取进程锁成功: {LOCK_FILE}")
                    return True
                except FileExistsError:
                    logging.error("另一个scraper实例正在运行")
                    return False
            else:
                LOCK_FD = open(LOCK_FILE, 'w')
                try:
                    fcntl.flock(LOCK_FD.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    LOCK_FD.write(str(os.getpid()))
                    LOCK_FD.flush()
                    logging.info(f"获取进程锁成功: {LOCK_FILE}")
                    return True
                except IOError:
                    logging.error("另一个scraper实例正在运行")
                    LOCK_FD.close()
                    return False

    except Exception as e:
        logging.error(f"获取进程锁时出错: {str(e)}")
        return False

def release_lock():
    """释放进程锁"""
    global LOCK_FILE, LOCK_FD

    try:
        if LOCK_FD:
            if platform.system() != "Windows" and HAS_FCNTL:
                fcntl.flock(LOCK_FD.fileno(), fcntl.LOCK_UN)
            LOCK_FD.close()
            LOCK_FD = None

        if LOCK_FILE and LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logging.info("进程锁已释放")

    except Exception as e:
        logging.error(f"释放进程锁时出错: {str(e)}")

# 注册退出时释放锁
atexit.register(release_lock)

def cleanup_chrome_processes():
    """清理Chrome相关进程"""
    try:
        if platform.system() == "Windows":
            # Windows系统
            subprocess.run(['taskkill', '/f', '/im', 'chrome.exe'],
                         capture_output=True, check=False)
            subprocess.run(['taskkill', '/f', '/im', 'chromedriver.exe'],
                         capture_output=True, check=False)
        else:
            # Unix系统
            subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, check=False)
            subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, check=False)
        time.sleep(2)
    except Exception as e:
        logging.warning(f"清理进程时出错: {str(e)}")

def get_chrome_driver_path():
    """获取正确的ChromeDriver路径"""
    try:
        # 首先尝试使用webdriver_manager
        driver_path = ChromeDriverManager().install()

        # 检查文件是否存在且可执行
        if os.path.exists(driver_path):
            # 在Windows上，确保是.exe文件
            if platform.system() == "Windows" and not driver_path.endswith('.exe'):
                exe_path = driver_path + '.exe'
                if os.path.exists(exe_path):
                    driver_path = exe_path
                else:
                    # 查找同目录下的chromedriver.exe
                    driver_dir = os.path.dirname(driver_path)
                    for file in os.listdir(driver_dir):
                        if file.startswith('chromedriver') and file.endswith('.exe'):
                            driver_path = os.path.join(driver_dir, file)
                            break

            # 验证文件是否可执行
            if os.access(driver_path, os.X_OK) or platform.system() == "Windows":
                logging.info(f"使用ChromeDriver: {driver_path}")
                return driver_path

        # 如果webdriver_manager失败，尝试系统PATH中的chromedriver
        chrome_driver_name = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
        system_driver = shutil.which(chrome_driver_name)
        if system_driver:
            logging.info(f"使用系统ChromeDriver: {system_driver}")
            return system_driver

        raise Exception("无法找到有效的ChromeDriver")

    except Exception as e:
        logging.error(f"获取ChromeDriver路径失败: {str(e)}")
        raise

def init_driver():
    """初始化 Chrome 驱动"""
    try:
        # 清理可能存在的残留进程
        cleanup_chrome_processes()

        chrome_options = Options()

        # 基础配置
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')

        # 防检测配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # 使用临时用户目录
        timestamp = int(time.time())
        if platform.system() == "Windows":
            temp_dir = os.environ.get('TEMP', 'C:\\temp')
            custom_data_dir = f"{temp_dir}\\chrome_profile_{timestamp}"
        else:
            custom_data_dir = f"/tmp/chrome_profile_{timestamp}"

        chrome_options.add_argument(f"--user-data-dir={custom_data_dir}")

        # 获取ChromeDriver路径
        driver_path = get_chrome_driver_path()
        service = Service(driver_path)

        # 创建驱动实例
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # 设置页面加载超时
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)

        # 验证版本
        try:
            browser_version = driver.capabilities.get('browserVersion', 'Unknown')
            chrome_driver_version = driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'Unknown')
            if chrome_driver_version != 'Unknown':
                chrome_driver_version = chrome_driver_version.split(' ')[0]

            logging.info(f"Chrome版本: {browser_version}")
            logging.info(f"ChromeDriver版本: {chrome_driver_version}")
        except Exception as e:
            logging.warning(f"获取版本信息失败: {str(e)}")

        return driver

    except Exception as e:
        logging.error(f"浏览器初始化失败: {str(e)}")
        # 尝试清理临时目录
        try:
            if 'custom_data_dir' in locals() and os.path.exists(custom_data_dir):
                shutil.rmtree(custom_data_dir, ignore_errors=True)
        except:
            pass
        raise

def scrape_zhihu_daily_news():
    """主抓取函数"""
    driver = None
    try:
        driver = init_driver()
        now = datetime.datetime.now()
        date_str = f"{now.month}月{now.day}日"
        encoded_date = quote(date_str)
        full_date_str = f"{now.year}年{now.month}月{now.day}日"
        encoded_full_date = quote(full_date_str)
        
        search_keywords = [
            f"60秒知天下+{encoded_date}",
            f"3分钟读懂世界+{encoded_date}",
            f"{encoded_full_date}+3分钟读懂世界"
        ]
        
        for keyword in search_keywords:
            url = f"https://weixin.sogou.com/weixin?type=2&s_from=input&query={keyword}"
            logging.info(f"尝试搜索: {url}")
            
            driver.get(url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
            
            # 保存页面供调试
            with open("sogou_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            try:
                search_results = get_search_results(driver)
                if search_results:
                    result = process_search_results(driver, search_results, now)
                    if result:
                        return result
            except Exception as e:
                logging.error(f"处理搜索结果时出错: {str(e)}")
                continue
        
        # 尝试API备用方案
        return fetch_api_data()
        
    except Exception as e:
        logging.error(f"主流程异常: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("浏览器已关闭")

def get_search_results(driver):
    """获取搜索结果"""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.news-list li"))
        )
        return driver.find_elements(By.CSS_SELECTOR, "ul.news-list li")
    except TimeoutException:
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[1]/div[3]/ul/li"))
            )
            return driver.find_elements(By.XPATH, "/html/body/div[2]/div[1]/div[3]/ul/li")
        except TimeoutException:
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            return soup.select("ul.news-list li")

def process_search_results(driver, search_results, now):
    """处理搜索结果"""
    candidates = []
    for idx, result in enumerate(search_results):
        try:
            if isinstance(result, webdriver.remote.webelement.WebElement):
                h3_element = result.find_element(By.CSS_SELECTOR, "h3")
                title_text = h3_element.text.strip()
                time_element = result.find_element(By.XPATH, ".//div[@class='s-p']/span[@class='s2']")
                time_text = time_element.text.strip()
                link = h3_element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
            else:
                h3 = result.select_one("h3")
                if not h3:
                    continue
                title_text = h3.get_text().strip()
                time_element = result.select_one("div.s-p span.s2")
                time_text = time_element.get_text().strip() if time_element else "未知时间"
                link = h3.select_one("a")["href"] if h3.select_one("a") else None
            
            if not link:
                continue
                
            # 检查标题是否符合要求
            date_pattern = f"{now.month}月{now.day}日"
            full_date_pattern = f"{now.year}年{now.month}月{now.day}日"
            
            is_valid_title = False
            if date_pattern in title_text and ("60秒知天下" in title_text or "3分钟读懂世界" in title_text):
                is_valid_title = True
            elif full_date_pattern in title_text and "3分钟读懂世界" in title_text:
                is_valid_title = True
                
            if is_valid_title:
                time_value = extract_time_value(time_text)
                candidates.append({
                    "index": idx,
                    "title": title_text,
                    "link": link,
                    "time_text": time_text,
                    "time_value": time_value
                })
        except Exception as e:
            logging.error(f"处理搜索结果 {idx} 时出错: {str(e)}")
            continue
    
    if candidates:
        candidates.sort(key=lambda x: -x["time_value"])
        selected = candidates[0]
        logging.info(f"选择结果: {selected['title']} - {selected['time_text']}")
        
        driver.get(selected['link'])
        time.sleep(5)
        
        article_content = get_article_content(driver)
        if article_content:
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', selected['title'])
            if date_match:
                year, month, day = map(int, date_match.groups())
            else:
                date_match = re.search(r'(\d{1,2})月(\d{1,2})日', selected['title'])
                if date_match:
                    month, day = map(int, date_match.groups())
                    year = datetime.datetime.now().year
                else:
                    year = datetime.datetime.now().year
                    month = now.month
                    day = now.day
            
            try:
                nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
                nongli_response = requests.get(nongli_url)
                if nongli_response.status_code == 200:
                    nongli_data = nongli_response.json()
                    if nongli_data.get("status") == 1:
                        lunar_date = nongli_data["data"]["lunar_date"]
                        ganzhi = nongli_data["data"]["ganzhi"]
                        
                        date_obj = datetime.datetime(year, month, day)
                        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]
                        
                        date_line = f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}\n"
                        content_lines = article_content.split('\n')
                        if not any(line.startswith(str(year)) for line in content_lines):
                            content_lines.insert(0, date_line)
                        article_content = "\n".join(content_lines)
            except Exception as e:
                logging.error(f"获取农历日期时出错: {str(e)}")
            
            result = {
                'title': selected['title'],
                'link': selected['link'],
                'time': selected['time_text'],
                'content': article_content
            }
            
            generate_rss(result)
            return result
    
    return None

def fetch_api_data():
    """从API获取数据"""
    try:
        api_url = "https://60s.afei7.com/v2/60s"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200 and "data" in data:
                api_data = data["data"]
                
                content_parts = []
                
                if "date" in api_data:
                    date_str = api_data["date"]
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    year = date_obj.year
                    month = date_obj.month
                    day = date_obj.day
                    
                    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]
                    
                    try:
                        nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
                        nongli_response = requests.get(nongli_url)
                        if nongli_response.status_code == 200:
                            nongli_data = nongli_response.json()
                            if nongli_data.get("status") == 1:
                                lunar_date = nongli_data["data"]["lunar_date"]
                                ganzhi = nongli_data["data"]["ganzhi"]
                                content_parts.append(f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}")
                    except Exception as e:
                        logging.error(f"获取农历日期时出错: {str(e)}")
                        content_parts.append(f"{year}年{month}月{day}日，{weekday}")
                
                if "news" in api_data and isinstance(api_data["news"], list):
                    for idx, news_item in enumerate(api_data["news"], 1):
                        content_parts.append(f"{idx}、{news_item}")
                
                if "tip" in api_data:
                    content_parts.append(f"【微语】{api_data['tip']}")
                
                result = {
                    'title': f"60秒知天下 {api_data.get('date', '')}",
                    'link': api_data.get('link', api_url),
                    'time': api_data.get('created', datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")),
                    'content': "\n".join(content_parts)
                }
                
                generate_rss(result)
                return result
    except Exception as e:
        logging.error(f"获取API数据时出错: {str(e)}")
    
    return None

def extract_time_value(time_text):
    """计算时间值用于比较新旧"""
    if "分钟前" in time_text:
        minutes = int(re.search(r'(\d+)', time_text).group(1))
        return minutes
    elif "小时前" in time_text:
        hours = int(re.search(r'(\d+)', time_text).group(1))
        return hours * 60
    elif "天前" in time_text:
        days = int(re.search(r'(\d+)', time_text).group(1))
        return days * 24 * 60
    elif re.match(r'\d{4}-\d{2}-\d{2}', time_text):
        date = datetime.datetime.strptime(time_text, "%Y-%m-%d")
        now = datetime.datetime.now()
        delta = now - date
        return delta.days * 24 * 60
    return 0

def get_article_content(driver):
    """获取文章内容"""
    try:
        time.sleep(3)
        with open("article_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        content_selectors = [
            "div.rich_media_content",
            "div.rich_media_wrp",
            "div#js_content",
            "section",
            "/html/body/div[2]/div[2]/div[2]/div/div[1]/div[2]/section"
        ]
        
        content_html = ""
        for selector in content_selectors:
            try:
                if selector.startswith("/"):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements:
                    for element in elements:
                        element_html = element.get_attribute("outerHTML")
                        if "60秒知天下" in element_html or "3分钟读懂世界" in element_html:
                            content_html = element_html
                            break
                    
                    if content_html:
                        break
            except Exception as e:
                continue
        
        if not content_html:
            content_html = driver.page_source
        
        soup = BeautifulSoup(content_html, 'html.parser')
        news_items = []
        weiyu_text = ""
        
        p_tags = soup.select('p')
        for p in p_tags:
            text = p.get_text().strip()
            if not text:
                continue
                
            if "【每日金句】" in text or "【微语】" in text:
                text = text.replace("【每日金句】", "【微语】")
                weiyu_text = text
                continue
                
            if re.match(r'^\d+、', text):
                news_items.append(text)
        
        output_parts = []
        if news_items:
            output_parts.extend(news_items)
            
        if weiyu_text:
            output_parts.append(weiyu_text)
        
        if not output_parts:
            text = soup.get_text()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            weiyu_found = False
            for line in lines:
                if re.search(r'\d{4}年', line):
                    continue
                
                if re.match(r'^\d+、', line):
                    output_parts.append(line)
                    continue
                
                if not weiyu_found and ("【每日金句】" in line or "【微语】" in line):
                    line = line.replace("【每日金句】", "【微语】")
                    weiyu_text = line
                    weiyu_found = True
                    continue
            
            if weiyu_text:
                if weiyu_text in output_parts:
                    output_parts.remove(weiyu_text)
                output_parts.append(weiyu_text)
        
        return "\n".join(output_parts)
    
    except Exception as e:
        logging.error(f"获取文章内容时出错: {str(e)}")
        return None

def generate_rss(news_item):
    """生成RSS格式文件"""
    fg = FeedGenerator()
    fg.title('60秒知天下')
    fg.link(href='https://weixin.sogou.com', rel='alternate')
    fg.description('60秒知天下RSS')
    fg.language('zh-CN')
    
    year = datetime.datetime.now().year
    month = datetime.datetime.now().month
    day = datetime.datetime.now().day
    
    date_match_full = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', news_item['title'])
    if date_match_full:
        year, month, day = map(int, date_match_full.groups())
    else:
        date_match = re.search(r'(\d{1,2})月(\d{1,2})日', news_item['title'])
        if date_match:
            month, day = map(int, date_match.groups())
    
    content_lines = news_item['content'].split('\n')
    has_lunar_info = False
    
    if content_lines and re.search(r'农历', content_lines[0]):
        has_lunar_info = True
    
    if not has_lunar_info:
        try:
            nongli_url = f"https://www.iamwawa.cn/nongli/api?type=solar&year={year}&month={month}&day={day}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            nongli_response = requests.get(nongli_url, headers=headers)
            
            if nongli_response.status_code == 200:
                nongli_data = json.loads(nongli_response.text)
                if nongli_data.get("status") == 1 and "data" in nongli_data:
                    data = nongli_data["data"]
                    lunar_date = data.get("lunar_date", "")
                    ganzhi = data.get("ganzhi", "")
                    zodiac = data.get("zodiac", "")
                    
                    if zodiac and zodiac.endswith('年'):
                        zodiac = zodiac.rstrip('年')
                    
                    date_obj = datetime.datetime(year, month, day)
                    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date_obj.weekday()]
                    
                    date_line = f"{year}年{month}月{day}日，{weekday}，农历{lunar_date}，{ganzhi}({zodiac}年)"
                    
                    if not content_lines[0].startswith(f"{year}年"):
                        content_lines.insert(0, date_line)
                        news_item['content'] = '\n'.join(content_lines)
        except Exception as e:
            logging.error(f"获取农历信息时出错: {str(e)}")
    
    fe = fg.add_entry()
    fe.title(news_item['title'])
    fe.link(href=news_item['link'])
    fe.description(news_item['content'])
    
    now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
    fe.pubDate(now)
    
    filename = 'zhihu_daily_news.xml'
    fg.rss_file(filename, pretty=True)
    logging.info(f"RSS文件已生成: {filename}")

def main():
    """主函数"""
    # 检查进程锁
    if not acquire_lock():
        print("另一个scraper实例正在运行，程序退出")
        sys.exit(1)

    try:
        logging.info("开始执行scraper程序")
        news = scrape_zhihu_daily_news()
        if news:
            print(f"已获取最新60秒知天下: {news['title']}")
            print(f"链接: {news['link']}")
            print(f"发布时间: {news['time']}")
            print(f"内容预览:")
            print(news['content'][:200] + "..." if len(news['content']) > 200 else news['content'])
            logging.info("程序执行成功")
        else:
            print("未找到符合条件的60秒知天下")
            logging.warning("未找到符合条件的内容")
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
        print("程序被用户中断")
    except Exception as e:
        logging.error(f"程序执行异常: {str(e)}")
        print(f"程序执行异常: {str(e)}")
    finally:
        # 清理资源
        release_lock()
        cleanup_chrome_processes()
        logging.info("程序执行完毕")

if __name__ == "__main__":
    main()
