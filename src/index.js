const express = require('express');
const cors = require('cors');
const path = require('path');
const dotenv = require('dotenv');
const cron = require('node-cron');
const newsRoutes = require('./api/newsRoutes');
const { initializeNews } = require('./utils/newsCollector');

// 加载环境变量
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true }));

// 设置视图引擎
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// 路由
app.use('/api', newsRoutes);

// 前端页面
app.get('/', (req, res) => {
  res.render('index');
});

// 初始化新闻数据
initializeNews();

// 每天早上6点更新新闻
cron.schedule('0 6 * * *', async () => {
  console.log('定时任务：更新新闻数据');
  await initializeNews();
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`服务器运行在 http://localhost:${PORT}`);
}); 