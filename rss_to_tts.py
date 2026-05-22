#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RSS转语音脚本
用法: 
python rss_to_tts.py [--rss RSS文件路径] [--output 输出文件名]

例如:
1. 使用默认设置:
   python rss_to_tts.py
   
2. 指定RSS文件路径:
   python rss_to_tts.py --rss C:\\Users\\Administrator\\Desktop\\index_60s\\RSS\\zhihu_daily_news.xml
   
3. 指定输出文件名:
   python rss_to_tts.py --output 60s_news
   
4. 同时指定RSS文件路径和输出文件名:
   python rss_to_tts.py --rss C:\\Users\\Administrator\\Desktop\\index_60s\\RSS\\zhihu_daily_news.xml --output 60s_news

说明:
- 脚本会从RSS文件中提取最新的新闻内容
- 生成文本文件
- 优先调用VITS API生成MP3文件
- 如果VITS API失败，回退到edge-tts生成MP3文件
- 将生成的MP3文件移动到RSS目录
"""

import os
import sys
import xml.etree.ElementTree as ET
import subprocess
import shutil
import re
from datetime import datetime
import argparse
import importlib.util

def extract_content_from_rss(rss_file_path):
    """从RSS XML文件中提取需要的内容"""
    try:
        tree = ET.parse(rss_file_path)
        root = tree.getroot()
        
        # 获取第一个item(最新的新闻)
        item = root.find('.//item')
        if item is None:
            raise Exception("未找到新闻条目")
        
        title = item.find('title').text if item.find('title') is not None else ""
        description = item.find('description').text if item.find('description') is not None else ""
        
        # 将内容分割成行
        lines = [line.strip() for line in description.split('\n') if line.strip()]
        
        # 提取日期行 (第一行通常是日期)
        date_text = lines[0] if lines else ""
        
        # 解析日期文本 (例如: "2025年4月7日，星期一，农历三月初十")
        date_parts = date_text.split('，')
        date = date_parts[0] if len(date_parts) > 0 else ""
        weekday = date_parts[1] if len(date_parts) > 1 else ""
        lunar_date = date_parts[2].replace('农历', '') if len(date_parts) > 2 else ""
        
        # 提取微语 - 增强识别方式
        hitokoto = ""
        
        # 方法1: 从格式化的行中查找微语标记
        for line in lines:
            if '【#今日早报微语】' in line or '【#今日微语】' in line:
                hitokoto = re.sub(r'【#今日早报微语】：|【#今日微语】：|【#今日早报微语】|【#今日微语】', '', line).strip()
                break
        
        # 方法2: 如果没找到，查找以【微语】开头的行
        if not hitokoto:
            for line in lines:
                if line.startswith('【微语】') or '【微语】' in line:
                    hitokoto = re.sub(r'.*【微语】[：:]*\s*', '', line).strip()
                    break
        
        # 方法3: 最后一种情况，查找所有行，找到包含"微语"的行
        if not hitokoto:
            # 先检查最后一行，通常微语会放在最后
            last_line = lines[-1] if lines else ""
            if last_line and ('微语' in last_line):
                hitokoto = re.sub(r'.*微语[】）\)\]]*[：:：]?\s*', '', last_line).strip()
            else:
                # 如果最后一行没有，则检查所有行
                for line in lines:
                    if '微语' in line and not any(skip in line for skip in ['微语：见上', '微语:见上']):
                        hitokoto = re.sub(r'.*微语[】）\)\]]*[：:：]?\s*', '', line).strip()
                        break
        
        # 移除可能存在的HTML标签和多余符号
        if hitokoto:
            hitokoto = re.sub(r'<[^>]*>', '', hitokoto)  # 移除HTML标签
            hitokoto = re.sub(r'^[""「『]|[""」』]$', '', hitokoto)  # 移除首尾引号
            hitokoto = hitokoto.strip()
        
        # 提取新闻内容
        news_items = []
        for i, line in enumerate(lines):
            # 跳过日期行和微语行
            if (i == 0) or ('微语' in line) or ('【#今日早报微语】' in line) or ('【#今日微语】' in line):
                continue
                
            # 提取新闻文本，去掉序号
            news_text = re.sub(r'^\d+[、.．]\s*', '', line).strip()
            if news_text:
                news_items.append(news_text)
        
        return {
            'date': date,
            'weekday': weekday,
            'lunar_date': lunar_date,
            'hitokoto': hitokoto,
            'news_items': news_items
        }
        
    except Exception as e:
        print(f"解析RSS文件时出错: {e}")
        return None

def create_text_file(content, output_path):
    """创建普通文本文件供TTS使用"""
    try:
        # 格式化新闻条目
        news_text = ""
        for i, news in enumerate(content['news_items']):
            news_text += f"第{i+1}条，{news}。\n"
        
        # 构建完整的朗读文本
        tts_text = (
            f"亲爱的听众朋友们，这里是阿飞为你带来的每天60秒读懂世界，"
            f"今天是{content['date']}，{content['weekday']}，"
            f"{content['lunar_date']}。\n"
            f"今日的新闻有：\n{news_text}\n"
            f"今天的新闻就到这里，"
            f"最后送给大家一句话：{content['hitokoto']}。\n"
            f"感谢您的收听，我们下次再见。"
        )

        # 写入文本文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(tts_text)
        
        return True
    except Exception as e:
        print(f"创建文本文件时出错: {e}")
        return False

def run_tts_vits_api(text_file_path, output_file_path):
    """使用VITS API进行TTS转换"""
    try:
        # 检查requests库是否已安装
        if importlib.util.find_spec("requests") is None:
            print("正在安装requests库...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
            print("requests库安装完成")
        
        import requests
        import urllib.parse
        
        # 从文本文件读取内容
        with open(text_file_path, "r", encoding="utf-8") as f:
            text_content = f.read()
        
        # 对文本进行URL编码
        encoded_text = urllib.parse.quote(text_content)
        
        # VITS API URL
        api_url = f"https://artrajz-vits-simple-api.hf.space/voice/vits?text={encoded_text}&id=190&lang=zh&noisew=0.9"
        
        print("正在优先使用VITS API进行TTS转换...")
        
        # 发送请求获取音频数据
        response = requests.get(api_url, timeout=60)
        
        if response.status_code == 200:
            # 检查并创建输出目录
            output_dir = os.path.dirname(output_file_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 保存音频文件
            with open(output_file_path, 'wb') as f:
                f.write(response.content)
            
            print(f"VITS API TTS转换成功，已保存到：{output_file_path}")
            return True
        else:
            print(f"VITS API请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"VITS API TTS转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tts_alternative(text_file_path, output_file_path):
    """使用替代方法（edge-tts）运行TTS转换"""
    try:
        import asyncio
        
        # 检查edge-tts是否已安装
        if importlib.util.find_spec("edge_tts") is None:
            print("正在安装edge-tts库...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts"])
            print("edge-tts库安装完成")
        
        import edge_tts
        
        # 检查并创建输出目录
        output_dir = os.path.dirname(output_file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 创建异步函数进行TTS转换
        async def run_tts():
            # 从文本文件读取内容
            with open(text_file_path, "r", encoding="utf-8") as f:
                text_content = f.read()
                
            voice = "zh-CN-YunyangNeural"
            
            try:
                # 直接保存到目标位置
                await edge_tts.Communicate(text_content, voice, rate="-5%", volume="+0%").save(output_file_path)
                print(f"TTS文件已创建: {output_file_path}")
                return True
            except Exception as e:
                print(f"保存音频文件时出错: {e}")
                raise

        # 运行异步函数
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        if hasattr(asyncio, "run"):
            result = asyncio.run(run_tts())
        else:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(run_tts())
        
        print(f"edge-tts转换成功，已保存到：{output_file_path}")
        return result
    except Exception as e:
        print(f"edge-tts转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='从RSS生成TTS语音文件')

    # 使用脚本所在目录作为基础目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_rss_path = os.path.join(script_dir, 'zhihu_daily_news.xml')

    parser.add_argument('--rss', help='RSS文件路径', default=default_rss_path)
    parser.add_argument('--output', help='输出音频文件名（不含扩展名）', default='60s')
    args = parser.parse_args()

    # 定义路径 - 使用脚本所在目录
    tts_dir = os.path.join(script_dir, "tts")
    rss_dir = script_dir

    # 确保TTS目录存在
    if not os.path.exists(tts_dir):
        os.makedirs(tts_dir)
        print(f"已创建TTS目录: {tts_dir}")

    text_path = os.path.join(tts_dir, f"{args.output}.txt")
    
    # 获取完整的RSS文件路径
    rss_file_path = args.rss
    if not os.path.isabs(rss_file_path):
        # 如果提供的是相对路径，转换为绝对路径
        rss_file_path = os.path.join(script_dir, rss_file_path)
    
    print(f"从RSS文件提取内容: {rss_file_path}")
    content = extract_content_from_rss(rss_file_path)
    
    if not content:
        print("内容提取失败，脚本终止。")
        return 1

    print("提取内容成功，创建文本文件...")
    if not create_text_file(content, text_path):
        print("文本文件创建失败，脚本终止。")
        return 1

    print(f"文本文件创建成功: {text_path}")
    
    # 定义临时MP3文件路径（在TTS目录）
    tts_mp3_path = os.path.join(tts_dir, f"{args.output}.mp3")
    # 定义最终MP3文件路径（在RSS目录）
    rss_mp3_path = os.path.join(rss_dir, f"{args.output}.mp3")
    
    # --- 核心逻辑调整：优先调用VITS API ---
    tts_success = False
    
    # 尝试使用VITS API
    print("尝试优先使用VITS API生成音频...")
    if run_tts_vits_api(text_path, tts_mp3_path):
        tts_success = True
    else:
        # VITS API失败，回退到edge-tts
        print("VITS API失败，回退到edge-tts...")
        if run_tts_alternative(text_path, tts_mp3_path):
            tts_success = True
    
    # --- 后续文件处理逻辑 ---
    if tts_success:
        print("TTS转换成功，开始处理文件...")
        try:
            # 检查生成的MP3文件是否存在
            if not os.path.exists(tts_mp3_path):
                print("TTS生成的文件不存在，处理失败。")
                return 1

            # 确保RSS目录存在
            if not os.path.exists(rss_dir):
                os.makedirs(rss_dir)
                print(f"已创建RSS目录: {rss_dir}")

            # 复制文件到RSS目录，覆盖同名文件
            shutil.copy2(tts_mp3_path, rss_mp3_path)
            print(f"已成功将音频文件复制到RSS目录并覆盖: {rss_mp3_path}")

            # 可选：清理临时文件
            try:
                os.remove(tts_mp3_path)
                print(f"已清理临时文件: {tts_mp3_path}")
            except Exception as e:
                print(f"清理临时文件失败: {e}")
            
            print("处理完成!")
            return 0
        except Exception as e:
            print(f"文件处理时出错: {e}")
            return 1
    else:
        print("所有TTS方法均失败，脚本终止。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
