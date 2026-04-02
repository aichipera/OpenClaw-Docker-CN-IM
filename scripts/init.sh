#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

OPENCLAW_HOME="/home/node/.openclaw"
OPENCLAW_WORKSPACE_ROOT="${OPENCLAW_WORKSPACE_ROOT:-$OPENCLAW_HOME}"
OPENCLAW_WORKSPACE_ROOT="${OPENCLAW_WORKSPACE_ROOT%/}"
OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE_ROOT}/workspace"
NODE_UID="$(id -u node)"
NODE_GID="$(id -g node)"
GATEWAY_PID=""

source "$SCRIPT_DIR/init-utils.sh"
source "$SCRIPT_DIR/init-permissions.sh"
source "$SCRIPT_DIR/init-plugins.sh"
source "$SCRIPT_DIR/init-config.sh"
source "$SCRIPT_DIR/init-agent-reach.sh"

cleanup() {
    echo "=== 接收到停止信号,正在关闭服务 ==="
    if [ -n "$GATEWAY_PID" ]; then
        kill -TERM "$GATEWAY_PID" 2>/dev/null || true
        wait "$GATEWAY_PID" 2>/dev/null || true
    fi
    echo "=== 服务已停止 ==="
    exit 0
}

setup_runtime_env() {
    export BUN_INSTALL="/usr/local"
    export PATH="$BUN_INSTALL/bin:$PATH"
    export AGENT_REACH_HOME="/home/node/.agent-reach"
    export AGENT_REACH_VENV_HOME="/home/node/.agent-reach-venv"
    export PATH="$AGENT_REACH_HOME/bin:$PATH"
    if [ -d "$AGENT_REACH_VENV_HOME/bin" ]; then
        export PATH="$AGENT_REACH_VENV_HOME/bin:$PATH"
    fi
    if [ -x "$AGENT_REACH_VENV_HOME/bin/agent-reach" ]; then
        cat > /usr/local/bin/agent-reach <<'WRAPPER'
#!/bin/bash
source "$AGENT_REACH_VENV_HOME/bin/activate"
exec "$AGENT_REACH_VENV_HOME/bin/agent-reach" "$@"
WRAPPER
        chmod +x /usr/local/bin/agent-reach
    fi
    export DBUS_SESSION_BUS_ADDRESS=/dev/null
}

start_gateway() {
    log_section "启动 OpenClaw Gateway"
    gosu node env HOME=/home/node DBUS_SESSION_BUS_ADDRESS=/dev/null \
        BUN_INSTALL="/usr/local" AGENT_REACH_HOME="/home/node/.agent-reach" \
        AGENT_REACH_VENV_HOME="/home/node/.agent-reach-venv" \
        PATH="/home/node/.agent-reach-venv/bin:/usr/local/bin:$PATH" \
        openclaw gateway run \
        --bind "$OPENCLAW_GATEWAY_BIND" \
        --port "$OPENCLAW_GATEWAY_PORT" \
        --token "$OPENCLAW_GATEWAY_TOKEN" \
        --verbose &
    GATEWAY_PID=$!
    echo "=== OpenClaw Gateway 已启动 (PID: $GATEWAY_PID) ==="
}

main() {
    log_section "OpenClaw 初始化脚本"
    ensure_directories
    ensure_config_persistence
    fix_permissions_if_needed
    sync_seed_extensions
    install_agent_reach
    sync_config_with_env
    finalize_permissions
    print_runtime_summary
    setup_runtime_env
    trap cleanup SIGTERM SIGINT SIGQUIT
    start_gateway
    wait "$GATEWAY_PID"
    local exit_code=$?
    echo "=== OpenClaw Gateway 已退出 (退出码: $exit_code) ==="
    exit "$exit_code"
}

main
