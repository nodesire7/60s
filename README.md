# 知乎每日新闻RSS生成器

这个项目用于爬取知乎上的每日新闻，并生成RSS格式的XML文件。

## 功能

- 爬取知乎搜索页面中的"每日新闻"
- 筛选包含当前日期的新闻
- 选择最新发布的新闻
- 提取新闻内容
- 生成RSS格式的XML文件

## 安装

1. 克隆此仓库
2. 安装所需依赖：
   ```
   pip install -r requirements.txt
   ```
3. 确保已安装Microsoft Edge浏览器

## 使用方法

直接运行脚本：

```
python scraper.py
```

脚本将使用您的Edge浏览器和默认配置文件，这意味着它会使用您已登录的知乎账号和cookie来访问内容。

如果遇到问题，可以尝试：
1. 确保Edge浏览器路径正确，默认为`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
2. 确保用户数据目录路径正确，默认为`C:\Users\Administrator\AppData\Local\Microsoft\Edge\User Data`
3. 查看生成的`zhihu_page.html`或`article_page.html`文件，分析页面结构

运行成功后，将在当前目录生成`zhihu_daily_news.xml`文件，可以将其导入到RSS阅读器中。

## 技术说明

本项目使用以下主要库：
- requests: 发送HTTP请求
- BeautifulSoup4: 解析HTML内容
- Selenium: 自动化浏览器操作，处理动态加载内容
- feedgen: 生成RSS格式文件

## 注意事项

- 脚本使用您已登录的Edge浏览器配置文件，因此您需要已经在Edge中登录知乎。
- 脚本依赖于知乎页面的结构，如果知乎页面结构变更，可能需要更新选择器。
- 使用已登录的浏览器配置文件可以绕过知乎的大部分反爬机制。
- 如需修改浏览器配置文件路径，请编辑脚本中的`user-data-dir`参数。 