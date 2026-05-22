#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""独立 WebP 截圖生成脚本 - 启动临时 HTTP 服务器并使用 Selenium 截图"""

import os
import sys
import time
import http.server
import socketserver
import threading
import io
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def start_http_server(port, directory):
    """在后台线程启动 HTTP 服务器"""
    os.chdir(directory)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread

def main():
    port = find_free_port()
    print(f"使用端口: {port}")

    # 启动 HTTP 服务器
    httpd, thread = start_http_server(port, BASE_DIR)
    time.sleep(1)
    print(f"HTTP 服务器已启动: http://localhost:{port}")

    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    from PIL import Image, ImageEnhance

    target_width = 650
    driver = None

    # 尝试 Chrome（使用 webdriver-manager）
    try:
        print("尝试使用 Chrome 浏览器...")
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--force-device-scale-factor=2.0")
        chrome_options.add_argument(f"--window-size={target_width+16},2000")

        driver_path = ChromeDriverManager().install()
        print(f"ChromeDriver 路径: {driver_path}")
        driver = webdriver.Chrome(service=ChromeService(driver_path), options=chrome_options)
        print("Chrome 浏览器启动成功")
    except Exception as e:
        print(f"Chrome 失败: {e}")

    # 尝试 Edge（使用 webdriver-manager）
    if driver is None:
        try:
            print("尝试使用 Edge 浏览器...")
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless=new")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument("--hide-scrollbars")
            edge_options.add_argument("--disable-extensions")
            edge_options.add_argument(f"--force-device-scale-factor=2.0")
            edge_options.add_argument(f"--window-size={target_width+16},2000")

            driver_path = EdgeChromiumDriverManager().install()
            print(f"EdgeDriver 路径: {driver_path}")
            driver = webdriver.Edge(service=EdgeService(driver_path), options=edge_options)
            print("Edge 浏览器启动成功")
        except Exception as e:
            print(f"Edge 失败: {e}")
            httpd.shutdown()
            return 1

    try:
        # 加载页面
        page_url = f"http://localhost:{port}/60s.html"
        print(f"加载页面: {page_url}")
        driver.get(page_url)
        time.sleep(3)

        # 获取实际内容高度
        true_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);")
        print(f"页面高度: {true_height}px")

        # 调整窗口大小
        driver.set_window_size(target_width + 16, true_height + 100)
        time.sleep(1)

        # 截图
        screenshot_png = driver.get_screenshot_as_png()
        screenshot = Image.open(io.BytesIO(screenshot_png))
        print(f"截图尺寸: {screenshot.width}x{screenshot.height}")

        # 调整宽度
        if screenshot.width != target_width:
            new_height = int(screenshot.height * (target_width / screenshot.width))
            screenshot = screenshot.resize((target_width, new_height), Image.LANCZOS)

        # 增强图像
        enhancer = ImageEnhance.Contrast(screenshot)
        screenshot = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Sharpness(screenshot)
        screenshot = enhancer.enhance(1.3)

        # 保存 WebP
        webp_path = os.path.join(BASE_DIR, "60s.webp")
        screenshot.save(webp_path, format="WEBP", quality=100, method=6, lossless=False)
        print(f"WebP 已生成: {webp_path} ({os.path.getsize(webp_path)} bytes)")

        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if driver:
            driver.quit()
        httpd.shutdown()
        print("清理完毕")

if __name__ == "__main__":
    sys.exit(main())
