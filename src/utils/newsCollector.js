const axios = require('axios');
const fs = require('fs');
const path = require('path');
const NewsModel = require('../models/NewsModel');

// 新闻数据来源列表
const NEWS_SOURCES = [
  { name: '人民网', url: 'http://www.people.com.cn/' },
  { name: '新华网', url: 'http://www.xinhuanet.com/' },
  { name: '中国新闻网', url: 'https://www.chinanews.com.cn/' },
  { name: '环球网', url: 'https://www.huanqiu.com/' },
  { name: 'BBC中文网', url: 'https://www.bbc.com/zhongwen/simp' },
  { name: '路透社', url: 'https://cn.reuters.com/' }
];

// 初始化或更新新闻
async function initializeNews() {
  try {
    console.log('开始更新新闻数据...');
    
    // 获取当前日期
    const currentDate = NewsModel.getCurrentDate();
    
    // 模拟从Google获取新闻
    const newsItems = await collectNewsFromSources();
    
    // 为示例保存现有示例图片
    const imageFileName = `${currentDate.replace(/-/g, '')}_news.png`;
    const headImageFileName = `${currentDate.replace(/-/g, '')}_head.png`;
    const audioFileName = `${currentDate.replace(/-/g, '')}_news.mp3`;
    
    // 复制示例图片到公共目录
    copyExampleFiles(imageFileName, headImageFileName, audioFileName);
    
    // 随机选择一首背景音乐
    const backgroundMusic = NewsModel.getRandomBackgroundMusic() || '';
    
    // 更新新闻数据
    const newsData = {
      date: currentDate,
      news: newsItems,
      weiyu: generateRandomWeiyu(),
      image: `/api/image/${imageFileName}`,
      audio: `/api/audio/${audioFileName}`,
      head_image: `/api/image/${headImageFileName}`,
      background_music: backgroundMusic
    };
    
    // 保存新闻数据
    const result = NewsModel.updateNews(newsData);
    if (result) {
      console.log('新闻数据更新成功!');
    } else {
      console.error('新闻数据更新失败!');
    }
  } catch (error) {
    console.error('初始化新闻数据出错:', error);
  }
}

// 模拟从新闻源收集新闻
async function collectNewsFromSources() {
  // 这里是模拟数据，实际实现时应该使用网络爬虫或新闻API
  const newsList = [
    "1、两部门：4月份，西南、华中、华东等部分地区洪涝和风雹灾害风险较高，华北、东北、西北等局地森林火灾风险高；",
    "2、央行：我国已建成全球数据规模领先、服务覆盖面最广的公共征信系统；",
    "3、两办发文：完善价格治理机制，防止经营者以低于成本的价格开展恶性竞争；",
    "4、七部门：生产安全事故每人死亡伤残责任全国最低保障限额提至40万元，临时聘用人员等纳入从业人员范畴；",
    "5、医保局专门提醒：药物服用完毕后，建议撕毁空药盒上的追溯码，不让有心的不法人员继续盗用空药盒和追溯码；",
    "6、食品安全再出两项新规：加强集中用餐单位食品安全监管，学校食堂最严，4月15日起正式实施；",
    "7、《北京市自动驾驶汽车条例》正式实施：L3级自动驾驶私家车可合法上路；北京41处水库湖泊进入禁渔期：半年内禁止一切捕捞；",
    "8、《2025中国城市长租市场发展蓝皮书》发布：四大一线城市约50%人口在租房，35岁以上租客占比达到35%以上创新高；",
    "9、山东宣布：为来鲁求职的应届毕业生提供7-15天免费住宿；四川宣布：引进演唱会最高奖500万，在川开设亚洲首店最高奖300万；",
    "10、多家银行薪酬下降：招行人均年薪降至约58万，中信银行微升至近60万；新股民继续快速增长：3月A股新开户数307万户，较1月增长96%；",
    "11、日媒：日本大隅半岛东部海域2日发生6.0级地震，暂无人员伤亡报告；日本东京一处施工现场发现大量人骨，日本民间要求彻查；",
    "12、美媒：美国卫生部大裁员正式启动，幅度接近四分之一，大量科学家流失、研究项目被砍；美国法官阻止特朗普当局解雇多州试用期联邦雇员；",
    "13、美媒：美参议员连续25小时演讲批特朗普，打破参议院68年纪录；美国将审查学生签证申请人社交媒体，严控多所常春藤大学经费；",
    "14、外媒：特朗普"铝关税"重创美国玩家，机箱、显卡累计税率高达45%；以色列宣布取消所有自美国进口商品关税；",
    "15、外媒：4名美军士兵在立陶宛演习期间失踪，美国军方确认4名失踪士兵遗体全部在沼泽中被发现；"
  ];
  
  return newsList;
}

// 从示例复制文件到公共目录
function copyExampleFiles(imageFileName, headImageFileName, audioFileName) {
  const workspaceDir = path.resolve(__dirname, '../../');
  
  // 确保目标目录存在
  const imagesDir = path.join(__dirname, '../public/images');
  const audioDir = path.join(__dirname, '../public/audio');
  
  if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
  }
  
  if (!fs.existsSync(audioDir)) {
    fs.mkdirSync(audioDir, { recursive: true });
  }
  
  // 复制示例图片
  if (fs.existsSync(path.join(workspaceDir, '202504031743617702.png'))) {
    fs.copyFileSync(
      path.join(workspaceDir, '202504031743617702.png'),
      path.join(imagesDir, imageFileName)
    );
  }
  
  // 复制头部图片
  if (fs.existsSync(path.join(workspaceDir, '202504031743617702_head.png'))) {
    fs.copyFileSync(
      path.join(workspaceDir, '202504031743617702_head.png'),
      path.join(imagesDir, headImageFileName)
    );
  }
  
  // 复制音频文件
  if (fs.existsSync(path.join(workspaceDir, '2025-04-03_254215217979568.mp3'))) {
    fs.copyFileSync(
      path.join(workspaceDir, '2025-04-03_254215217979568.mp3'),
      path.join(audioDir, audioFileName)
    );
  }
}

// 生成随机微语
function generateRandomWeiyu() {
  const weiyuList = [
    "【微语】不知道会遇见什么，只知道阳光这么好吧，别辜负了今天。",
    "【微语】愿你眼中总有光芒，活成你想要的模样。",
    "【微语】不负春光，不负自己，静待花开。",
    "【微语】生活不会一直顺遂，但请保持一颗向阳的心。",
    "【微语】用力过好每一天，未来的路才会越走越宽。"
  ];
  
  const randomIndex = Math.floor(Math.random() * weiyuList.length);
  return weiyuList[randomIndex];
}

module.exports = {
  initializeNews
}; 