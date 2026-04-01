# OpenClaw Docker 镜像
FROM node:22-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV BUN_INSTALL="/usr/local" \
    PATH="/usr/local/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# 1. 合并系统依赖安装与全局工具安装，并清理缓存
# 1. 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash bat ca-certificates ccze chromium cron curl diffutils dnsutils dstat fd-find ffmpeg \
    fonts-liberation fonts-noto-cjk fonts-noto-color-emoji build-essential imagemagick less \
    netcat-openbsd net-tools poppler-utils procps openssh-client git gosu htop httpie iotop jq \
    lsof miller mtr multitail ncdu pipx python3 redis-tools ripgrep rsync shellcheck socat sqlite3 \
    supervisor tini tree unzip vim websockify wget zip && \
    rm -rf /var/lib/apt/lists/*

# 2. 安装 npm 全局包
RUN npm config set registry https://registry.npmmirror.com && \
    npm install -g openclaw@2026.3.31 opencode-ai@latest playwright playwright-extra puppeteer-extra-plugin-stealth @steipete/bird @qwen-code/qwen-code@latest

# 3. 安装 bun 和 qmd
RUN curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash && \
    /usr/local/bin/bun install -g @tobilu/qmd && \
    rm -rf /tmp/*

# 4. 安装 Playwright Chromium 浏览器
RUN npx playwright install chromium --with-deps

# 5. 清理缓存
RUN rm -rf /root/.npm /root/.cache

# 2. 插件安装（作为 node 用户以避免后期权限修复带来的镜像膨胀）
RUN mkdir -p /home/node/.openclaw/workspace /home/node/.openclaw/extensions && \
    chown -R node:node /home/node

USER node
ENV HOME=/home/node
ENV PATH="/home/node/.local/bin:$PATH"
WORKDIR /home/node

RUN pipx install 'markitdown[all]' && \
    pipx install ddgs[api] && \
    cd /home/node/.openclaw/extensions && \
  git clone --depth 1 https://github.com/soimy/openclaw-channel-dingtalk.git dingtalk && \
  cd dingtalk && \
  npm install --omit=dev --legacy-peer-deps && \
  timeout 300 openclaw plugins install -l . || true && \
  cd /home/node/.openclaw/extensions && \
  git clone --depth 1 https://github.com/Daiyimo/openclaw-napcat.git napcat && \
  cd napcat && \
  npm install --production && \
  timeout 300 openclaw plugins install -l . || true && \
  cd /home/node/.openclaw && \
  git clone --depth 1 https://github.com/justlovemaki/qqbot.git && \
  cd qqbot && \
  timeout 300 openclaw plugins install . || true && \
  timeout 300 openclaw plugins install @sunnoy/wecom@latest || true && \
  find /home/node/.openclaw/extensions -name ".git" -type d -exec rm -rf {} + && \
  rm -rf /home/node/.openclaw/qqbot/.git && \
  rm -rf /tmp/* /home/node/.npm /home/node/.cache
  
# 3. 最终配置
USER root

# 复制初始化脚本
COPY ./init.sh /usr/local/bin/init.sh
RUN chmod +x /usr/local/bin/init.sh

# 设置环境变量
ENV HOME=/home/node \
    TERM=xterm-256color \
    NODE_PATH=/usr/local/lib/node_modules

# 暴露端口
EXPOSE 18789 18790

# 设置工作目录为 home
WORKDIR /home/node

# 使用初始化脚本作为入口点
ENTRYPOINT ["/bin/bash", "/usr/local/bin/init.sh"]
