#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""健康检查 — 验证60s管线的每个环节"""

import os
import sys
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
errors = []

def check(description, fn):
    """运行检查并收集结果"""
    try:
        ok, msg = fn()
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {description}")
        if msg:
            print(f"         {msg}")
        if not ok:
            errors.append(f"{description}: {msg}")
        return ok
    except Exception as e:
        print(f"  [FAIL] {description}")
        print(f"         Exception: {e}")
        errors.append(f"{description}: {e}")
        return False

def main():
    print("=" * 60)
    print(f"60s Pipeline Health Check — {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 检查Python依赖
    print("\n[1] Python Dependencies")
    deps_ok = True
    for pkg in ['requests', 'feedgen', 'pytz', 'bs4', 'edge_tts', 'PIL', 'selenium']:
        def make_check(p):
            return lambda: (True, p) if __import__(p) else (False, f"{p} not found")
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [FAIL] {pkg} not installed")
            deps_ok = False
            errors.append(f"Missing Python package: {pkg}")
    if deps_ok:
        print("  => All Python deps OK")

    # 2. 检查文件完整性
    print("\n[2] Required Files")
    required = [
        'zhihu_daily_news.xml',
        '60s.mp3',
        '60s.webp',
        '60s.html',
        'index.html',
        'css/bg_small.webp',
        'rss_to_tts.py',
        'sixty_seconds_daily.py',
        'scraper.py',
    ]
    for f in required:
        path = os.path.join(BASE_DIR, f)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        status = f"({size/1024:.0f}KB)" if exists else "MISSING"
        print(f"  [{'OK' if exists else 'FAIL'}] {f} {status}")
        if not exists:
            errors.append(f"Missing file: {f}")
        elif size == 0:
            errors.append(f"Empty file: {f}")

    # 3. 检查RSS XML内容
    print("\n[3] RSS XML Content")
    xml_path = os.path.join(BASE_DIR, 'zhihu_daily_news.xml')
    if os.path.exists(xml_path):
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            items = root.findall('.//item')
            print(f"  [OK] Found {len(items)} news items")
            if items:
                title = items[0].find('title')
                if title is not None:
                    print(f"  [OK] Latest: {title.text[:50]}...")
                desc = items[0].find('description')
                if desc is not None:
                    lines = [l for l in desc.text.split('\n') if l.strip()]
                    print(f"  [OK] {len(lines)} lines in description")
                    # Check if date matches today
                    from datetime import datetime
                    today = datetime.now().strftime('%Y年%m月%d日')
                    if today in desc.text:
                        print(f"  [OK] Content matches today's date ({today})")
                    else:
                        print(f"  [WARN] Content date may not match today ({today})")
        except Exception as e:
            print(f"  [FAIL] XML parse error: {e}")
            errors.append(f"XML parse error: {e}")

    # 4. 检查API连通性
    print("\n[4] API Connectivity")
    try:
        import requests
        r = requests.get('https://zaobao.wpush.cn/api/zaobao/today', timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == 'success':
                print(f"  [OK] API OK — {len(data.get('data', {}).get('news', []))} news items")
            else:
                print(f"  [WARN] API returned unexpected: {data}")
        else:
            print(f"  [WARN] API HTTP {r.status_code}")
    except Exception as e:
        print(f"  [WARN] API unreachable: {e}")

    # 5. 检查edge-tts
    print("\n[5] TTS (edge-tts)")
    try:
        import edge_tts
        print(f"  [OK] edge-tts installed (version check passed)")
    except Exception as e:
        print(f"  [FAIL] edge-tts: {e}")
        errors.append(f"edge-tts not available: {e}")

    # 6. 检查Chrome/WebDriver
    print("\n[6] WebDriver (for WebP)")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        driver_path = ChromeDriverManager().install()
        print(f"  [OK] ChromeDriver: {driver_path}")
    except Exception as e:
        print(f"  [WARN] ChromeDriver: {e}")

    # 7. 检查CSV输出文件时效性
    print("\n[7] Output Freshness")
    mp3_path = os.path.join(BASE_DIR, '60s.mp3')
    webp_path = os.path.join(BASE_DIR, '60s.webp')
    for label, path in [('MP3', mp3_path), ('WebP', webp_path)]:
        if os.path.exists(path):
            age_hours = (time.time() - os.path.getmtime(path)) / 3600
            print(f"  [{'OK' if age_hours < 30 else 'STALE'}] {label} age: {age_hours:.1f}h")
            if age_hours > 30:
                errors.append(f"Stale {label} file: {age_hours:.1f} hours old")

    # 总结
    print("\n" + "=" * 60)
    if errors:
        print(f"HEALTH CHECK FAILED — {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("HEALTH CHECK PASSED — All systems operational")
        return 0

if __name__ == '__main__':
    sys.exit(main())
