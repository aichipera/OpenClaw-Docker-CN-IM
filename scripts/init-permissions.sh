#!/bin/bash

fix_permissions_if_needed() {
    if ! is_root; then
        return
    fi

    local current_owner
    current_owner="$(stat -c '%u:%g' "$OPENCLAW_HOME" 2>/dev/null || echo unknown:unknown)"

    echo "挂载目录: $OPENCLAW_HOME"
    echo "当前所有者(UID:GID): $current_owner"
    echo "目标所有者(UID:GID): ${NODE_UID}:${NODE_GID}"

    if [ "$current_owner" != "${NODE_UID}:${NODE_GID}" ]; then
        echo "检测到宿主机挂载目录所有者与容器运行用户不一致，尝试自动修复..."
        chown -R node:node "$OPENCLAW_HOME" || true
    fi

    if [ -S /var/run/docker.sock ]; then
        echo "检测到 Docker Socket，正在尝试修复权限以支持沙箱..."
        chmod 666 /var/run/docker.sock || true
    fi

    if ! gosu node test -w "$OPENCLAW_HOME"; then
        echo "❌ 权限检查失败：node 用户无法写入 $OPENCLAW_HOME"
        echo "请在宿主机执行（Linux）："
        echo "  sudo chown -R ${NODE_UID}:${NODE_GID} <your-openclaw-data-dir>"
        echo "或在启动时显式指定用户："
        echo "  docker run --user \$(id -u):\$(id -g) ..."
        echo "若宿主机启用了 SELinux，请在挂载卷后添加 :z 或 :Z"
        exit 1
    fi
}

finalize_permissions() {
    if is_root; then
        chown -R node:node "$OPENCLAW_HOME" || true
    fi
}
