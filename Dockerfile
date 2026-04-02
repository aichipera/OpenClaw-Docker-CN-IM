# OpenClaw Docker 镜像
FROM node:22-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV BUN_INSTALL="/usr/local" \
    PATH="/usr/local/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# 1. 安装系统依赖、配置环境并安装全局工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    bat \
    build-essential \
    ca-certificates \
    ccze \
    chromium \
    cron \
    curl \
    diffutils \
    dnsutils \
    dstat \
    fd-find \
    ffmpeg \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    git \
    gosu \
    htop \
    httpie \
    imagemagick \
    iotop \
    jq \
    less \
    locales \
    lsof \
    miller \
    mtr \
    multitail \
    ncdu \
    net-tools \
    netcat-openbsd \
    openssh-client \
    pipx \
    poppler-utils \
    procps \
    redis-tools \
    ripgrep \
    rsync \
    shellcheck \
    socat \
    sqlite3 \
    supervisor \
    tini \
    tree \
    unzip \
    vim \
    wget \
    zip && \
    # 配置 locale
    sed -i 's/^# *en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen && \
    printf 'LANG=en_US.UTF-8\nLANGUAGE=en_US:en\nLC_ALL=en_US.UTF-8\n' > /etc/default/locale && \
    # 配置 git 使用 HTTPS 替代 SSH
    git config --system url."https://github.com/".insteadOf ssh://git@github.com/ && \
    # 设置 npm 镜像并安装全局包
    npm config set registry https://registry.npmmirror.com && \
    npm install -g openclaw@2026.4.1 opencode-ai@latest clawhub playwright playwright-extra puppeteer-extra-plugin-stealth @steipete/bird @qwen-code/qwen-code@latest && \
    # 安装 bun、uv 和 qmd，并使用 uv 安装 Python 3.12
    curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && \
    uv python install 3.12 && \
    # 将 uv 管理的 python 移动到全局目录，确保 node 用户也可访问
    PYTHON_PATH=$(uv python find 3.12) && \
    PYTHON_ROOT=$(dirname $(dirname "$PYTHON_PATH")) && \
    mv "$PYTHON_ROOT" /usr/local/python312 && \
    ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python3 && \
    ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python && \
    # 移除 EXTERNALLY-MANAGED 限制并安装 websockify
    find /usr/local/python312 -name EXTERNALLY-MANAGED -delete && \
    /usr/local/bin/python3 -m pip install --no-cache-dir --break-system-packages websockify && \
    npm install -g @tobilu/qmd@1.1.6 && \
    # 安装 Playwright 浏览器依赖
    npx playwright install chromium --with-deps && \
    # 清理缓存
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.npm /root/.cache

# 2. 插件安装（作为 node 用户以避免后期权限修复带来的镜像膨胀）
RUN mkdir -p /home/node/.openclaw/workspace /home/node/.openclaw/extensions && \
    chown -R node:node /home/node

USER node
ENV HOME=/home/node
ENV PATH="/home/node/.local/bin:$PATH"
WORKDIR /home/node

# 安装 pipx 工具
RUN pipx install 'markitdown[all]' && \
    pipx install ddgs[api]

# 安装 linuxbrew（Homebrew 的 Linux 版本）
RUN mkdir -p /home/node/.linuxbrew/Homebrew && \
    git clone --depth 1 https://github.com/Homebrew/brew /home/node/.linuxbrew/Homebrew && \
    mkdir -p /home/node/.linuxbrew/bin && \
    ln -s /home/node/.linuxbrew/Homebrew/bin/brew /home/node/.linuxbrew/bin/brew && \
    chown -R node:node /home/node/.linuxbrew && \
    chmod -R g+rwX /home/node/.linuxbrew

# 安装插件
RUN cd /home/node/.openclaw/extensions && \
  git clone --depth 1 -b v4.17.25 https://github.com/Daiyimo/openclaw-napcat.git napcat && \
  cd napcat && \
  npm install --production && \
  timeout 300 openclaw plugins install -l . || true && \
  cd /home/node/.openclaw/extensions && \
  timeout 300 openclaw plugins install @soimy/dingtalk || true && \
  timeout 300 openclaw plugins install @tencent-connect/openclaw-qqbot@latest || true && \
  timeout 300 openclaw plugins install @sunnoy/wecom || true && \
  mkdir -p /home/node/.openclaw /home/node/.openclaw-seed && \
  find /home/node/.openclaw/extensions -name ".git" -type d -exec rm -rf {} + && \
  mv /home/node/.openclaw/extensions /home/node/.openclaw-seed/ && \
  printf '%s\n' '2026.4.1' > /home/node/.openclaw-seed/extensions/.seed-version && \
  rm -rf /tmp/* /home/node/.npm /home/node/.cache
  
# 3. 最终配置
USER root

# 复制初始化脚本并确保换行符为 LF
COPY ./init.sh /usr/local/bin/init.sh
RUN sed -i 's/\r$//' /usr/local/bin/init.sh && \
    chmod +x /usr/local/bin/init.sh

# 设置环境变量
ENV HOME=/home/node \
    TERM=xterm-256color \
    NODE_PATH=/usr/local/lib/node_modules \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    NODE_ENV=production \
    PATH="/home/node/.linuxbrew/bin:/home/node/.linuxbrew/sbin:/usr/local/lib/node_modules/.bin:${PATH}" \
    HOMEBREW_NO_AUTO_UPDATE=1 \
    HOMEBREW_NO_INSTALL_CLEANUP=1

# 暴露端口
EXPOSE 18789 18790

# 设置工作目录为 home
WORKDIR /home/node

# 使用初始化脚本作为入口点
ENTRYPOINT ["/bin/bash", "/usr/local/bin/init.sh"]
