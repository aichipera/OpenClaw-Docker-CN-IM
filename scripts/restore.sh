#!/bin/bash
set -e

ARCHIVE="$1"
TARGET_DIR="${2:-${OPENCLAW_DATA_DIR:-}}"

if [ -z "$ARCHIVE" ]; then
    echo "用法: $0 <备份文件> [目标目录]"
    echo "示例: $0 ./backups/openclaw-backup-20240101.tar.gz ~/.openclaw"
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    echo "错误: 备份文件不存在: $ARCHIVE"
    exit 1
fi

if tar -tzf "$ARCHIVE" >/dev/null 2>&1; then
    echo "✅ 备份文件完整性检查通过"
else
    echo "❌ 备份文件损坏或格式错误"
    exit 1
fi

if [ -z "$TARGET_DIR" ]; then
    echo "错误: 未指定目标目录，请提供目标目录或设置 OPENCLAW_DATA_DIR 环境变量"
    exit 1
fi

echo "正在恢复 OpenClaw 数据..."
echo "  备份文件: $ARCHIVE"
echo "  目标目录: $TARGET_DIR"

mkdir -p "$TARGET_DIR"
if tar -xzf "$ARCHIVE" -C "$TARGET_DIR"; then
    echo "✅ 恢复完成: $TARGET_DIR"
else
    echo "❌ 恢复失败"
    exit 1
fi