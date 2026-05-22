const express = require('express');
const router = express.Router();
const NewsModel = require('../models/NewsModel');
const path = require('path');

// 获取最新新闻API
router.get('/news', async (req, res) => {
  try {
    const newsData = NewsModel.getLatestNews();
    
    // 设置响应头
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Cache-Control', 'no-cache');
    
    // 构建响应体
    const responseData = {
      request_id: generateRequestId(),
      success: true,
      message: "success",
      code: 200,
      data: newsData,
      time: Math.floor(Date.now() / 1000),
      usage: 0
    };
    
    res.status(200).json(responseData);
  } catch (error) {
    console.error('获取新闻API出错:', error);
    res.status(500).json({
      request_id: generateRequestId(),
      success: false,
      message: "获取新闻失败",
      code: 500,
      time: Math.floor(Date.now() / 1000),
      usage: 0
    });
  }
});

// 获取音频文件
router.get('/audio/:filename', (req, res) => {
  const { filename } = req.params;
  const audioPath = path.join(__dirname, '../public/audio', filename);
  res.sendFile(audioPath);
});

// 获取图片文件
router.get('/image/:filename', (req, res) => {
  const { filename } = req.params;
  const imagePath = path.join(__dirname, '../public/images', filename);
  res.sendFile(imagePath);
});

// 生成请求ID
function generateRequestId() {
  return Math.floor(Math.random() * 1000000000000000000).toString();
}

module.exports = router; 