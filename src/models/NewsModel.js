const fs = require('fs');
const path = require('path');

class NewsModel {
  constructor() {
    this.dataPath = path.join(__dirname, '../data');
    this.newsFilePath = path.join(this.dataPath, 'news.json');
    this.musicDirectory = path.join(__dirname, '../public/audio/music');
    
    // 确保数据目录存在
    if (!fs.existsSync(this.dataPath)) {
      fs.mkdirSync(this.dataPath, { recursive: true });
    }
    
    // 确保音乐目录存在
    if (!fs.existsSync(this.musicDirectory)) {
      fs.mkdirSync(this.musicDirectory, { recursive: true });
    }
    
    // 初始化空的新闻数据
    if (!fs.existsSync(this.newsFilePath)) {
      this.saveNews({
        date: this.getCurrentDate(),
        news: [],
        weiyu: "",
        image: "",
        audio: "",
        head_image: "",
        background_music: ""
      });
    }
  }
  
  // 获取最新新闻
  getLatestNews() {
    try {
      const newsData = JSON.parse(fs.readFileSync(this.newsFilePath, 'utf8'));
      return newsData;
    } catch (error) {
      console.error('读取新闻数据失败:', error);
      return {
        date: this.getCurrentDate(),
        news: [],
        weiyu: "暂无新闻数据",
        image: "",
        audio: "",
        head_image: "",
        background_music: ""
      };
    }
  }
  
  // 保存新闻数据
  saveNews(newsData) {
    try {
      fs.writeFileSync(this.newsFilePath, JSON.stringify(newsData, null, 2), 'utf8');
      return true;
    } catch (error) {
      console.error('保存新闻数据失败:', error);
      return false;
    }
  }
  
  // 更新新闻
  updateNews(newsData) {
    return this.saveNews({
      ...newsData,
      date: newsData.date || this.getCurrentDate()
    });
  }
  
  // 获取当前日期（YYYY-MM-DD格式）
  getCurrentDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  
  // 获取随机背景音乐
  getRandomBackgroundMusic() {
    try {
      const musicFiles = fs.readdirSync(this.musicDirectory);
      if (musicFiles.length === 0) {
        return null;
      }
      const randomIndex = Math.floor(Math.random() * musicFiles.length);
      return `/api/audio/music/${musicFiles[randomIndex]}`;
    } catch (error) {
      console.error('获取随机背景音乐失败:', error);
      return null;
    }
  }
}

// 单例模式
module.exports = new NewsModel(); 