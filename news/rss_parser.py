import requests
import xml.etree.ElementTree as ET
import os
import time
import re
import json
import sys
import logging
import io
import codecs
from datetime import datetime
from html import unescape

# 设置日志记录
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"rss_parser_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# RSS源地址
RSS_URLS = {
    'tnews365': 'https://rss.afei7.com/telegram/channel/tnews365',
    'ZaihuaNews': 'https://rss.afei7.com/telegram/channel/ZaihuaNews'
}

# 缓存文件路径
CACHE_DIR = 'cache'
os.makedirs(CACHE_DIR, exist_ok=True)

# 输出文件夹
OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_text_from_html(html_content):
    """从HTML中提取纯文本，去除HTML标签"""
    if not html_content:
        return "", []
    
    # 处理换行标签
    html_content = html_content.replace('<br>', '\n')
    
    # 提取img标签内容
    img_pattern = r'<img\s+src="([^"]+)"[^>]*>'
    img_matches = re.findall(img_pattern, html_content)
    img_urls = []
    for url in img_matches:
        img_urls.append(url)
    
    # 处理blockquote标签内的内容（通常是引用），暂时不需要移除
    blockquote_pattern = r'<div class="rsshub-quote"><blockquote>(.*?)</blockquote></div>'
    html_content = re.sub(blockquote_pattern, '', html_content)
    
    # 移除所有HTML标签
    text = re.sub(r'<[^>]+>', '', html_content)
    text = unescape(text)  # 解码HTML实体
    
    # 移除多余空白
    text = re.sub(r'\n\s*\n', '\n', text)
    # 删除行首多余空格
    text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)
    text = text.strip()
    
    return text, img_urls

def format_tnews365_item(item):
    """格式化竹新社新闻条目"""
    try:
        title = item.find('title').text if item.find('title') is not None else ""
        description = item.find('description').text if item.find('description') is not None else ""
        
        # 移除标题中的emoji和标记
        title = re.sub(r'↩️\s*', '', title)
        title = re.sub(r'🖼\s*', '', title)
        title = re.sub(r'🎬\s*', '', title)
        title = re.sub(r'竹新社:\s*', '', title)
        
        # 提取描述中的文本和图片URL
        text, img_urls = extract_text_from_html(description)
        
        # 处理文本，使段落间使用【换行】分隔
        paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # 提取来源信息
        sources = []
        # 直接从原始HTML中提取a标签
        link_pattern = r'<a href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
        link_matches = re.findall(link_pattern, description)
        
        for url, name in link_matches:
            if not name.startswith('竹新社'):  # 过滤掉不是来源的链接
                sources.append(f"{name} {url}")
        
        # 构建格式化文本 - 使用【换行】作为分隔符，不加额外的换行符
        formatted_text = "【换行】".join(paragraphs)
        
        # 添加图片信息
        img_block = ""
        if img_urls:
            for url in img_urls:
                img_block += f"【图片@【@{url} 】】\n"
        
        # 添加来源信息
        source_text = ""
        if sources:
            source_text = "\n（ 新闻来源：" + "\\r".join(sources) + " ）"
        
        # 图片显示在文章最顶部
        if img_block:
            result = img_block + formatted_text + source_text
        else:
            result = formatted_text + source_text
        
        return result
    except Exception as e:
        logging.error(f"Error formatting tnews365 item: {e}")
        return ""

def format_zaihua_item(item):
    """格式化在花频道新闻条目"""
    try:
        title = item.find('title').text if item.find('title') is not None else ""
        description = item.find('description').text if item.find('description') is not None else ""
        
        # 移除标题中的特殊标记和emoji
        title = re.sub(r'🖼\s*', '', title)
        title = re.sub(r'🎬\s*', '', title)
        
        # 提取描述中的文本和图片URL
        text, img_urls = extract_text_from_html(description)
        
        # 清理文本，移除不必要的内容
        # 移除"投稿 ☘️频道 聊天"以及其他类似格式的文本
        text = re.sub(r'📮投稿\s*☘️频道\s*🌸聊天', '', text)
        text = re.sub(r'投稿\s*☘️频道\s*聊天', '', text)
        text = re.sub(r'PS：频道只负责推荐优秀项目.*?后续安全问题请自行承担。', '', text, flags=re.DOTALL)
        
        # 去除所有emoji
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        
        # 处理文本，使段落间使用【换行】分隔
        paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', text)
        # 过滤掉只包含"投稿"、"频道"、"聊天"等词的段落
        paragraphs = [p.strip() for p in paragraphs if p.strip() and not re.match(r'^(投稿|频道|聊天|\s*)+$', p.strip())]
        
        # 提取来源信息
        sources = []
        link_pattern = r'<a href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
        link_matches = re.findall(link_pattern, description)
        
        for url, name in link_matches:
            # 过滤掉投稿、频道、聊天等非来源链接
            if not (name.startswith('投稿') or name.startswith('频道') or name.startswith('聊天')):
                sources.append(f"{name} {url}")
        
        # 构建格式化文本 - 使用【换行】作为分隔符，不加额外的换行符
        formatted_text = "【换行】".join(paragraphs)
        
        # 添加图片信息
        img_block = ""
        if img_urls:
            for url in img_urls:
                img_block += f"【图片@【@{url} 】】\n"
        
        # 添加来源信息
        source_text = ""
        if sources:
            source_text = "\n（ 新闻来源：" + "\\r".join(sources) + " ）"
        
        # 图片显示在文章最顶部
        if img_block:
            result = img_block + formatted_text + source_text
        else:
            result = formatted_text + source_text
        
        # 最后再次检查和清理结果文本中可能遗留的"投稿 ☘️频道 聊天"文本
        result = re.sub(r'投稿\s*☘️*频道\s*聊天\s*', '', result)
        
        return result
    except Exception as e:
        logging.error(f"Error formatting ZaihuaNews item: {e}")
        return ""

def get_latest_items(url, channel_name, last_update_time=None):
    """获取RSS的最新内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 处理字符编码问题
        if 'charset' in response.headers.get('content-type', '').lower():
            response.encoding = response.apparent_encoding
        
        root = ET.fromstring(response.content)
        channel = root.find('channel')
        items = channel.findall('item')
        
        new_items = []
        latest_pub_date = last_update_time
        
        for item in items:
            pub_date_str = item.find('pubDate').text
            pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
            
            if last_update_time is None or pub_date > last_update_time:
                new_items.append((item, pub_date))
                if latest_pub_date is None or pub_date > latest_pub_date:
                    latest_pub_date = pub_date
        
        # 按发布时间排序，最新的在前
        new_items.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in new_items], latest_pub_date
    
    except Exception as e:
        logging.error(f"Error fetching {channel_name}: {e}")
        return [], last_update_time

def save_cache(channel_name, update_time):
    """保存缓存信息"""
    cache_file = os.path.join(CACHE_DIR, f"{channel_name}_cache.json")
    cache_data = {
        'last_update': update_time.isoformat() if update_time else None
    }
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f)

def load_cache(channel_name):
    """加载缓存信息"""
    cache_file = os.path.join(CACHE_DIR, f"{channel_name}_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                if cache_data.get('last_update'):
                    return datetime.fromisoformat(cache_data['last_update'])
        except Exception as e:
            logging.error(f"Error loading cache for {channel_name}: {e}")
    return None

def check_and_process_feed(channel_name):
    """检查并处理RSS feed"""
    url = RSS_URLS.get(channel_name)
    if not url:
        logging.error(f"Unknown channel: {channel_name}")
        return None
    
    last_update_time = load_cache(channel_name)
    new_items, latest_update_time = get_latest_items(url, channel_name, last_update_time)
    
    if new_items:
        logging.info(f"Found {len(new_items)} new items in {channel_name}")
        results = []
        
        for item in new_items:
            if channel_name == 'tnews365':
                formatted_text = format_tnews365_item(item)
            elif channel_name == 'ZaihuaNews':
                formatted_text = format_zaihua_item(item)
            else:
                continue
                
            if formatted_text:
                results.append(formatted_text)
        
        # 保存最新的更新时间
        if latest_update_time:
            save_cache(channel_name, latest_update_time)
        
        return results
    else:
        logging.info(f"No new items in {channel_name}")
        return None

def save_results_to_file(results, timestamp=None):
    """将结果保存到文件，并返回文件路径"""
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    file_paths = []
    
    for channel, items in results.items():
        output_file = os.path.join(OUTPUT_DIR, f"{channel}_{timestamp}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"===== {channel} =====\n\n")
            for item in items:
                f.write(item + "\n\n----------\n\n")
        
        file_paths.append(output_file)
        logging.info(f"Saved {len(items)} items to {output_file}")
    
    return file_paths

def output_final_result(results):
    """生成最终结果输出文件，避免控制台编码问题"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"final_output_{timestamp}.txt")
    
    # 手动构建JSON字符串，确保格式完全一致
    json_str = "[\n"
    
    # 遍历所有内容项
    items_processed = 0
    total_items = sum(len(items) for channel, items in results.items())
    
    for channel, items in results.items():
        for item in items:
            items_processed += 1
            
            # 处理文本内容，直接将换行符替换为\\n
            processed_text = item.replace('\n', '\\n')
            
            # 处理其他特殊字符
            processed_text = processed_text.replace('\\', '\\\\')
            processed_text = processed_text.replace('"', '\\"')
            
            # 特殊处理图片格式和链接
            processed_text = processed_text.replace('【图片@【@', '【图片@【@')
            processed_text = processed_text.replace('】】', '】】')
            
            # 不再使用【反射执行@】包装内容
            
            # 添加每个项目
            json_str += " {\n"
            json_str += " \"data\": {\n"
            json_str += " \"content\":\"" + processed_text + "\",\n"
            json_str += " \"nickname\": \"腾讯新闻\",\n"
            json_str += " \"user_id\": \"319350538\"\n"
            json_str += " },\n"
            json_str += " \"type\": \"node\"\n"
            json_str += " }"
            
            # 如果不是最后一项，添加逗号
            if items_processed < total_items:
                json_str += ",\n"
            else:
                json_str += "\n"
    
    # 关闭JSON数组
    json_str += " ]"
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(json_str)
    
    logging.info(f"生成最终输出文件: {output_file}")
    print(f"结果已保存到文件: {output_file}")
    return output_file

def main():
    """主函数"""
    results = {}
    for channel_name in RSS_URLS.keys():
        news_items = check_and_process_feed(channel_name)
        if news_items:
            results[channel_name] = news_items
    
    if results:
        # 保存结果到单独文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_results_to_file(results, timestamp)
        
        # 生成最终输出文件而不是直接打印到控制台
        final_output = output_final_result(results)
    else:
        logging.info("No new content found in any feeds.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        logging.error("Error details:", exc_info=True) 
