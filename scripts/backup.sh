#!/bin/bash
set -e

DATA_DIR="${1:-${OPENCLAW_DATA_DIR:-}}"
OUTPUT_DIR="${2:-.}"

if [ -z "$DATA_DIR" ]; then
    echo "用法: $0 [数据目录] [输出目录]"
    echo "示例: $0 ~/.openclaw ./backups"
    exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
    echo "错误: 数据目录不存在: $DATA_DIR"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/openclaw-backup-$TIMESTAMP.tar.gz"

echo "正在备份 OpenClaw 数据..."
echo "  数据目录: $DATA_DIR"
echo "  输出文件: $OUTPUT_FILE"

tar -czf "$OUTPUT_FILE" \
    -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" \
    --exclude='*.log' \
    --exclude='.npm/*' \
    --exclude='.cache/*' \
    --exclude='node_modules/*' \
    2>/dev/null || \
    tar -czf "$OUTPUT_FILE" -C "$DATA_DIR" . 2>/dev/null || \
    tar -czf "$OUTPUT_FILE" "$DATA_DIR" 2>/dev/null

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ 备份完成: $OUTPUT_FILE ($SIZE)"
else
    echo "❌ 备份失败"
    exit 1
fi