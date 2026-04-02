#!/bin/bash

install_agent_reach() {
    if [ "${AGENT_REACH_ENABLED:-false}" != "true" ]; then
        return
    fi

    log_section "安装 Agent Reach"

    local github_url="https://github.com/Panniantong/agent-reach/archive/main.zip"
    local pip_mirror=""
    local pip_index_env=""

    if [ "${AGENT_REACH_USE_CN_MIRROR:-false}" = "true" ]; then
        github_url="https://gh.llkk.cc/https://github.com/Panniantong/agent-reach/archive/main.zip"
        pip_mirror="-i https://pypi.tuna.tsinghua.edu.cn/simple"
        pip_index_env="export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    fi

    if gosu node test -f /home/node/.agent-reach-venv/bin/agent-reach; then
        local check_output
        check_output="$(gosu node bash -c "
            export PATH=\$PATH:/home/node/.local/bin
            $pip_index_env
            source ~/.agent-reach-venv/bin/activate
            /home/node/.agent-reach-venv/bin/agent-reach check-update 2>&1 || true
        ")"
        echo "$check_output"

        if echo "$check_output" | grep -q '已是最新版本'; then
            echo "Agent Reach 已是最新版本，跳过安装步骤"
            return
        fi

        echo "Agent Reach 检测到可更新版本，开始自动更新..."
        gosu node bash -c "
            export PATH=\$PATH:/home/node/.local/bin
            $pip_index_env
            source ~/.agent-reach-venv/bin/activate
            pip install --upgrade pip $pip_mirror
            pip install --upgrade $github_url $pip_mirror
        "
    else
        gosu node bash -c "
            export PATH=\$PATH:/home/node/.local/bin
            $pip_index_env
            python3 -m venv ~/.agent-reach-venv
            source ~/.agent-reach-venv/bin/activate
            pip install --upgrade pip $pip_mirror
            pip install $github_url $pip_mirror
            agent-reach install --env=auto 
        "
    fi

    gosu node bash -c "
        export PATH=\$PATH:/home/node/.local/bin
        $pip_index_env
        source ~/.agent-reach-venv/bin/activate

        # 配置代理（如果提供）
        if [ -n \"\$AGENT_REACH_PROXY\" ]; then
            agent-reach configure proxy \"\$AGENT_REACH_PROXY\"
        fi

        # 配置 Twitter Cookies
        if [ -n \"\$AGENT_REACH_TWITTER_COOKIES\" ]; then
            agent-reach configure twitter-cookies \"\$AGENT_REACH_TWITTER_COOKIES\"
        fi

        # 配置 Groq Key
        if [ -n \"\$AGENT_REACH_GROQ_KEY\" ]; then
            agent-reach configure groq-key \"\$AGENT_REACH_GROQ_KEY\"
        fi
        
        # 配置小红书 Cookies
        if [ -n \"\$AGENT_REACH_XHS_COOKIES\" ]; then
            agent-reach configure xhs-cookies \"\$AGENT_REACH_XHS_COOKIES\"
        fi
    "
    
    # 建立软链接到 /usr/local/bin 以便全局访问（如果需要）
    # 但我们已经在 setup_runtime_env 中处理了 PATH

    # 检查工作空间父目录下的 skills 目录中是否存在 agent-reach，若存在则同步到工作空间（仅删除目标 SKILL.md 并覆盖）
    local workspace_parent
    workspace_parent="$(dirname "$OPENCLAW_WORKSPACE")"
    if [ -d "$workspace_parent/skills/agent-reach" ]; then
        local src="$workspace_parent/skills/agent-reach"
        local dst="$OPENCLAW_WORKSPACE/skills/agent-reach"
        echo "检测到 $src，正在将其同步到工作空间: $dst"
        mkdir -p "$dst"
        rm -f "$dst/SKILL.md"
        cp -af "$src/." "$dst/" || true
        rm -rf "$src"
        if is_root; then
            chown -R node:node "$dst" || true
        fi
    fi
}