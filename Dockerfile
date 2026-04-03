# OpenClaw Docker 镜像 - 多阶段构建优化版
# Stage 1: Builder - 安装系统依赖和构建工具
FROM debian:bookworm-slim AS builder

# 安装构建依赖和 CA 证书
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    unzip \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 bun
RUN curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash

# 安装 uv 和 Python 3.12
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && \
    uv python install 3.12 && \
    PYTHON_PATH=$(uv python find 3.12) && \
    PYTHON_ROOT=$(dirname $(dirname "$PYTHON_PATH")) && \
    mv "$PYTHON_ROOT" /usr/local/python312 && \
    ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python3 && \
    ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python && \
    find /usr/local/python312 -name EXTERNALLY-MANAGED -delete

# Stage 2: Base - 基础系统环境
FROM node:22-slim AS base

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    BUN_INSTALL=/usr/local \
    PATH=/usr/local/bin:$PATH

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    bat \
    ca-certificates \
    chromium \
    curl \
    ffmpeg \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    git \
    gosu \
    jq \
    less \
    locales \
    netcat-openbsd \
    openssh-client \
    pandoc \
    pipx \
    sqlite3 \
    tini \
    unzip \
    vim \
    wget \
    && sed -i 's/^# *en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen && \
    printf 'LANG=en_US.UTF-8\nLANGUAGE=en_US:en\nLC_ALL=en_US.UTF-8\n' > /etc/default/locale && \
    git config --system url."https://github.com/".insteadOf ssh://git@github.com/ && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# 从 builder 阶段复制 bun 和 Python
COPY --from=builder /usr/local/bin/bun /usr/local/bin/bun
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/python312 /usr/local/python312
RUN ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python3 && \
    ln -sf /usr/local/python312/bin/python3 /usr/local/bin/python && \
    find /usr/local/python312 -name EXTERNALLY-MANAGED -delete && \
    /usr/local/bin/python3 -m pip install --no-cache-dir --break-system-packages websockify

# Stage 3: npm packages
FROM base AS npm-deps

# 设置 npm 镜像
RUN npm config set registry https://registry.npmmirror.com

# 安装全局 npm 包
RUN npm install -g openclaw@2026.4.2 opencode-ai@latest clawhub playwright playwright-extra puppeteer-extra-plugin-stealth @steipete/bird @qwen-code/qwen-code@latest @tobilu/qmd@1.1.6

# 安装 Playwright 浏览器
RUN npx playwright install chromium --with-deps

# Stage 4: user setup
FROM npm-deps AS user-setup

# 创建用户目录
RUN mkdir -p /home/node/.openclaw/workspace /home/node/.openclaw/extensions && \
    id node &>/dev/null || useradd -m -u 1000 -s /bin/bash node && \
    chown -R node:node /home/node

USER node
ENV HOME=/home/node
ENV PATH="/home/node/.local/bin:$PATH"
WORKDIR /home/node

RUN pipx install 'markitdown[all]' && \
    pipx install 'ddgs[api]'

# 安装 Linuxbrew
RUN mkdir -p /home/node/.linuxbrew/Homebrew && \
    git clone --depth 1 https://github.com/Homebrew/brew /home/node/.linuxbrew/Homebrew && \
    mkdir -p /home/node/.linuxbrew/bin && \
    ln -s /home/node/.linuxbrew/Homebrew/bin/brew /home/node/.linuxbrew/bin/brew && \
    chown -R node:node /home/node/.linuxbrew && \
    chmod -R g+rwX /home/node/.linuxbrew

# 安装插件
RUN mkdir -p /home/node/.openclaw/extensions && \
    chown -R node:node /home/node/.openclaw && \
    cd /home/node/.openclaw/extensions && \
    git clone --depth 1 -b v4.17.25 https://github.com/Daiyimo/openclaw-napcat.git napcat && \
    cd napcat && \
    npm install --production && \
    timeout 300 openclaw plugins install -l . --dangerously-force-unsafe-install || true && \
    cd /home/node/.openclaw/extensions && \
    timeout 300 openclaw plugins install @soimy/dingtalk --dangerously-force-unsafe-install || true && \
    timeout 300 openclaw plugins install @tencent-connect/openclaw-qqbot@latest --dangerously-force-unsafe-install || true && \
    timeout 300 openclaw plugins install @sunnoy/wecom --dangerously-force-unsafe-install || true && \
    mkdir -p /home/node/.openclaw-seed && \
    find /home/node/.openclaw/extensions -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true && \
    mv /home/node/.openclaw/extensions /home/node/.openclaw-seed/ && \
    printf '%s\n' '2026.4.1' > /home/node/.openclaw-seed/extensions/.seed-version && \
    rm -rf /tmp/* /home/node/.npm /home/node/.cache

# Stage 5: Final - 运行时配置
FROM user-setup AS final

USER root

# 复制初始化脚本
COPY ./scripts/init.sh /usr/local/bin/init.sh
COPY ./scripts/init-utils.sh /usr/local/bin/init-utils.sh
COPY ./scripts/init-permissions.sh /usr/local/bin/init-permissions.sh
COPY ./scripts/init-plugins.sh /usr/local/bin/init-plugins.sh
COPY ./scripts/init-config.sh /usr/local/bin/init-config.sh
COPY ./scripts/init-agent-reach.sh /usr/local/bin/init-agent-reach.sh
COPY ./scripts/openclaw-config /usr/local/bin/openclaw-config

RUN sed -i 's/\r$//' /usr/local/bin/init*.sh && \
    chmod +x /usr/local/bin/init*.sh

# 设置环境变量
ENV HOME=/home/node \
    TERM=xterm-256color \
    NODE_PATH=/usr/local/lib/node_modules \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    NODE_ENV=production \
    PATH="/home/node/.linuxbrew/bin:/home/node/.linuxbrew/sbin:/usr/local/lib/node_modules/.bin:/usr/local/bin:${PATH}" \
    HOMEBREW_NO_AUTO_UPDATE=1 \
    HOMEBREW_NO_INSTALL_CLEANUP=1

# 暴露端口
EXPOSE 18789 18790

# 设置工作目录
WORKDIR /home/node

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD bash -c 'echo > /dev/tcp/localhost/18789' || exit 1

# 入口点
ENTRYPOINT ["/bin/bash", "/usr/local/bin/init.sh"]
