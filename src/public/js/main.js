document.addEventListener('DOMContentLoaded', () => {
  // 获取DOM元素
  const newsContainer = document.getElementById('news-container');
  const newsTemplate = document.getElementById('news-template');
  
  // 加载新闻数据
  fetchNews()
    .then(renderNews)
    .catch(handleError);
  
  // 获取新闻数据
  async function fetchNews() {
    try {
      const response = await fetch('/api/news');
      
      if (!response.ok) {
        throw new Error(`API请求失败: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('获取新闻数据失败:', error);
      throw error;
    }
  }
  
  // 渲染新闻
  function renderNews(data) {
    if (!data || !data.success || !data.data) {
      throw new Error('获取到的数据格式不正确');
    }
    
    const newsData = data.data;
    
    // 清空加载动画
    newsContainer.innerHTML = '';
    
    // 复制模板
    const newsCard = document.importNode(newsTemplate.content, true);
    
    // 填充日期
    const dateElement = newsCard.querySelector('.date');
    dateElement.textContent = formatDate(newsData.date);
    
    // 填充图片
    if (newsData.head_image) {
      const headerImage = newsCard.querySelector('.header-image');
      headerImage.src = newsData.head_image;
      headerImage.alt = `${newsData.date} 头图`;
    }
    
    if (newsData.image) {
      const newsImage = newsCard.querySelector('.news-image');
      newsImage.src = newsData.image;
      newsImage.alt = `${newsData.date} 新闻图`;
    }
    
    // 填充新闻列表
    const newsList = newsCard.querySelector('.news-list');
    if (newsData.news && newsData.news.length > 0) {
      newsData.news.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        newsList.appendChild(li);
      });
    } else {
      const li = document.createElement('li');
      li.textContent = '今日暂无新闻';
      newsList.appendChild(li);
    }
    
    // 填充微语
    if (newsData.weiyu) {
      const weiyuElement = newsCard.querySelector('.weiyu');
      weiyuElement.textContent = newsData.weiyu;
    }
    
    // 设置音频
    if (newsData.audio) {
      const audioElement = newsCard.querySelector('#news-audio');
      audioElement.src = newsData.audio;
      
      // 音频控制
      setupAudioControls(newsCard, newsData);
    }
    
    // 添加到容器
    newsContainer.appendChild(newsCard);
  }
  
  // 设置音频控制
  function setupAudioControls(newsCard, newsData) {
    const audioElement = newsCard.querySelector('#news-audio');
    const bgMusicElement = newsCard.querySelector('#bg-music');
    const playButton = newsCard.querySelector('#play-btn');
    const volumeControl = newsCard.querySelector('#volume');
    
    // 加载背景音乐
    if (newsData.background_music) {
      bgMusicElement.src = newsData.background_music;
      bgMusicElement.volume = 0.3; // 背景音乐音量低一些
    }
    
    // 设置音量
    volumeControl.addEventListener('input', () => {
      const volume = parseFloat(volumeControl.value);
      audioElement.volume = volume;
      bgMusicElement.volume = volume * 0.3; // 背景音乐音量是主音量的30%
    });
    
    // 播放/暂停按钮
    playButton.addEventListener('click', () => {
      if (audioElement.paused) {
        // 开始播放
        playButton.textContent = '暂停';
        audioElement.play();
        
        // 如果有背景音乐，也播放
        if (newsData.background_music) {
          bgMusicElement.play();
        }
      } else {
        // 暂停播放
        playButton.textContent = '播放新闻';
        audioElement.pause();
        bgMusicElement.pause();
      }
    });
    
    // 新闻播放结束后
    audioElement.addEventListener('ended', () => {
      playButton.textContent = '播放新闻';
      bgMusicElement.pause();
    });
  }
  
  // 格式化日期
  function formatDate(dateString) {
    try {
      const date = new Date(dateString);
      const year = date.getFullYear();
      const month = date.getMonth() + 1;
      const day = date.getDate();
      
      const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
      const weekDay = weekDays[date.getDay()];
      
      return `${year}年${month}月${day}日 ${weekDay}`;
    } catch (error) {
      console.error('日期格式化错误:', error);
      return dateString;
    }
  }
  
  // 处理错误
  function handleError(error) {
    console.error('渲染新闻失败:', error);
    newsContainer.innerHTML = `
      <div class="error-container">
        <h2>加载失败</h2>
        <p>获取新闻数据时出错，请稍后再试。</p>
        <p class="error-message">${error.message}</p>
        <button class="reload-btn" onclick="location.reload()">重新加载</button>
      </div>
    `;
  }
}); 