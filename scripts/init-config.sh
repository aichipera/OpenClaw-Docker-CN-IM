#!/bin/bash

ensure_workspace_root_link() {
    mkdir -p "$OPENCLAW_HOME"

    if [ "$OPENCLAW_WORKSPACE_ROOT" = "$OPENCLAW_HOME" ]; then
        return
    fi

    local workspace_root_parent
    workspace_root_parent="$(dirname "$OPENCLAW_WORKSPACE_ROOT")"
    mkdir -p "$workspace_root_parent"
    mkdir -p "$OPENCLAW_WORKSPACE_ROOT"

    if [ -L "$OPENCLAW_WORKSPACE_ROOT" ]; then
        local current_target
        current_target="$(readlink "$OPENCLAW_WORKSPACE_ROOT" || true)"
        if [ "$current_target" = "$OPENCLAW_HOME" ]; then
            return
        fi
        rm -f "$OPENCLAW_WORKSPACE_ROOT"
    elif [ -e "$OPENCLAW_WORKSPACE_ROOT" ]; then
        if [ -d "$OPENCLAW_WORKSPACE_ROOT" ] && [ -z "$(ls -A "$OPENCLAW_WORKSPACE_ROOT" 2>/dev/null)" ]; then
            rmdir "$OPENCLAW_WORKSPACE_ROOT"
        else
            echo "❌ OPENCLAW_WORKSPACE_ROOT 已存在且不能替换为指向 $OPENCLAW_HOME 的软链接: $OPENCLAW_WORKSPACE_ROOT"
            echo "   请清理或改用其他路径后重试。"
            exit 1
        fi
    fi

    ln -s "$OPENCLAW_HOME" "$OPENCLAW_WORKSPACE_ROOT"
    echo "已创建工作空间根目录软链接: $OPENCLAW_WORKSPACE_ROOT -> $OPENCLAW_HOME"
}

ensure_directories() {
    ensure_workspace_root_link
    mkdir -p "$OPENCLAW_HOME" "$OPENCLAW_WORKSPACE"
}

ensure_config_persistence() {
    log_section "配置 .config 目录持久化"
    local persistent_config_dir="$OPENCLAW_HOME/.config"
    local container_config_dir="/home/node/.config"

    # 1. 创建持久化目录
    mkdir -p "$persistent_config_dir"

    # 2. 处理现有目录与迁移
    if [ -d "$container_config_dir" ] && [ ! -L "$container_config_dir" ]; then
        # 如果持久化目录为空，将现有配置迁移过去
        if [ -z "$(ls -A "$persistent_config_dir")" ]; then
            echo "检测到容器内已有 .config 目录，正在迁移到持久化目录..."
            cp -a "$container_config_dir/." "$persistent_config_dir/"
        fi
        rm -rf "$container_config_dir"
    fi

    # 3. 创建软链接
    if [ ! -L "$container_config_dir" ]; then
        ln -sfn "$persistent_config_dir" "$container_config_dir"
        echo "已建立软链接: $container_config_dir -> $persistent_config_dir"
    fi

    # 4. 权限修复
    if is_root; then
        chown -R node:node "$persistent_config_dir" || true
        chown -h node:node "$container_config_dir" || true
    fi
}

ensure_base_config() {
    local config_file="$OPENCLAW_HOME/openclaw.json"

    if [ -f "$config_file" ]; then
        return
    fi

    echo "配置文件不存在，创建基础骨架..."
    cat > "$config_file" <<'EOF'
{
  "meta": { "lastTouchedVersion": "2026.2.14" },
  "update": { "checkOnStart": false },
  "browser": {
    "headless": true,
    "noSandbox": true,
    "defaultProfile": "openclaw",
    "executablePath": "/usr/bin/chromium"
  },
  "models": { "mode": "merge", "providers": { "default": { "models": [] } } },
  "agents": {
    "defaults": {
      "compaction": { "mode": "safeguard" },
      "sandbox": { "mode": "off", "workspaceAccess": "none" },
      "elevatedDefault": "full",
      "maxConcurrent": 4,
      "subagents": { "maxConcurrent": 8 }
    }
  },
  "messages": {
    "ackReactionScope": "group-mentions",
    "tts": {
      "auto": "off",
      "mode": "final",
      "provider": "edge",
      "providers": {
        "edge": {
          "voice": "zh-CN-XiaoxiaoNeural",
          "lang": "zh-CN",
          "outputFormat": "ogg-24khz-16bit-mono-opus",
          "pitch": "+0Hz",
          "rate": "+0%",
          "volume": "+0%",
          "timeoutMs": 30000
        }
      }
    }
  },
  "commands": { "native": "auto", "nativeSkills": "auto" },
  "tools": {
    "profile": "full",
    "sessions": {
      "visibility": "all"
    },
    "fs": {
      "workspaceOnly": true
    }
  },
  "channels": {},
  "plugins": { "entries": {}, "installs": {} },
  "memory": {
    "backend": "qmd",
    "citations": "auto",
    "qmd": {
      "includeDefaultMemory": true,
      "sessions": {
        "enabled": true
      },
      "limits": {
        "timeoutMs": 8000,
        "maxResults": 16
      },
      "update": {
        "onBoot": true,
        "interval": "5m",
        "debounceMs": 15000
      },
      "command": "/usr/local/bin/qmd",
      "paths": [
        {
          "path": "/home/node/.openclaw/workspace",
          "name": "workspace",
          "pattern": "**/*.md"
        }
      ]
    }
  }
}
EOF
}

sync_config_with_env() {
    local config_file="$OPENCLAW_HOME/openclaw.json"
    ensure_base_config
    echo "正在根据当前环境变量同步配置状态..."
    local _script_dir
    _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CONFIG_FILE="$config_file" PYTHONPATH="$_script_dir" python3 -m openclaw_config sync
}

normalize_sync_check() {
    local global_sync_check="${SYNC_OPENCLAW_CONFIG:-true}"
    local model_sync_check="${SYNC_MODEL_CONFIG:-true}"
    global_sync_check="$(echo "$global_sync_check" | tr '[:upper:]' '[:lower:]' | xargs)"
    model_sync_check="$(echo "$model_sync_check" | tr '[:upper:]' '[:lower:]' | xargs)"

    if [ "$global_sync_check" = "false" ] || [ "$global_sync_check" = "0" ] || [ "$global_sync_check" = "no" ]; then
        echo "global-disabled"
        return
    fi

    if [ "$model_sync_check" = "false" ] || [ "$model_sync_check" = "0" ] || [ "$model_sync_check" = "no" ]; then
        echo "model-disabled"
        return
    fi

    echo "enabled"
}

collect_provider_names() {
    local names=("default")
    local i
    for i in 2 3 4 5 6; do
        local name_var="MODEL${i}_NAME"
        local provider_name="${!name_var}"
        if [ -n "$provider_name" ]; then
            names+=("$provider_name")
        else
            names+=("model${i}")
        fi
    done
    echo "${names[@]}"
}

normalize_model_ref_shell() {
    local raw="$1"
    shift
    local provider_prefix known
    local known_providers=("$@")

    if [ -z "$raw" ]; then
        echo ""
        return
    fi

    if [[ "$raw" != */* ]]; then
        echo "default/$raw"
        return
    fi

    provider_prefix="${raw%%/*}"
    for known in "${known_providers[@]}"; do
        if [ "$provider_prefix" = "$known" ]; then
            echo "$raw"
            return
        fi
    done

    echo "default/$raw"
}

print_model_summary() {
    local sync_check final_mid final_imid
    local provider_names extra_providers i api_key_var provider_name_var provider_name
    sync_check="$(normalize_sync_check)"

    if [ "$sync_check" = "global-disabled" ]; then
        echo "整体配置: 手动模式 (跳过环境变量同步)"
        return
    fi

    if [ "$sync_check" = "model-disabled" ]; then
        echo "模型配置: 手动模式 (跳过模型环境变量同步)"
        return
    fi

    read -r -a provider_names <<< "$(collect_provider_names)"

    final_mid="${PRIMARY_MODEL:-${MODEL_ID:-gpt-4o}}"
    final_mid="$(normalize_model_ref_shell "$final_mid" "${provider_names[@]}")"

    final_imid="${IMAGE_MODEL_ID:-${MODEL_ID:-gpt-4o}}"
    final_imid="$(normalize_model_ref_shell "$final_imid" "${provider_names[@]}")"

    echo "当前主模型: $final_mid"
    echo "当前图片模型: $final_imid"

    extra_providers=()
    for i in 2 3 4 5 6; do
        api_key_var="MODEL${i}_API_KEY"
        provider_name_var="MODEL${i}_NAME"
        if [ -n "${!api_key_var}" ] || [ -n "${!provider_name_var}" ]; then
            provider_name="${!provider_name_var}"
            if [ -z "$provider_name" ]; then
                provider_name="model${i}"
            fi
            extra_providers+=("$provider_name")
        fi
    done

    if [ ${#extra_providers[@]} -gt 0 ]; then
        echo "额外提供商: ${extra_providers[*]}"
    fi
}

print_runtime_summary() {
    log_section "初始化完成"
    print_model_summary
    echo "API 协议: ${API_PROTOCOL:-openai-completions}"
    echo "Base URL: ${BASE_URL}"
    echo "上下文窗口: ${CONTEXT_WINDOW:-200000}"
    echo "最大 Tokens: ${MAX_TOKENS:-8192}"
    echo "Gateway 端口: $OPENCLAW_GATEWAY_PORT"
    echo "Gateway 绑定: $OPENCLAW_GATEWAY_BIND"
    echo "Gateway 模式: ${OPENCLAW_GATEWAY_MODE:-local}"
    echo "Gateway 允许域: ${OPENCLAW_GATEWAY_ALLOWED_ORIGINS:-未设置}"
    echo "Gateway 允许不安全认证: ${OPENCLAW_GATEWAY_ALLOW_INSECURE_AUTH:-true}"
    echo "Gateway 禁用设备认证: ${OPENCLAW_GATEWAY_DANGEROUSLY_DISABLE_DEVICE_AUTH:-false}"
    echo "插件启用: ${OPENCLAW_PLUGINS_ENABLED:-true}"
    echo "沙箱模式: ${OPENCLAW_SANDBOX_MODE:-off}"
    echo "沙箱范围: ${OPENCLAW_SANDBOX_SCOPE:-agent}"
    echo "沙箱访问权限: ${OPENCLAW_SANDBOX_WORKSPACE_ACCESS:-none}"
    echo "允许插件列表已由系统自动同步"
}
