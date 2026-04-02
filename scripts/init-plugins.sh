#!/bin/bash

sync_seed_extensions() {
    local seed_dir="/home/node/.openclaw-seed/extensions"
    local target_dir="$OPENCLAW_HOME/extensions"
    local seed_version_file="$seed_dir/.seed-version"
    local target_version_file="$target_dir/.seed-version"
    local global_sync="${SYNC_OPENCLAW_CONFIG:-true}"
    local sync_mode="${SYNC_EXTENSIONS_MODE:-seed-version}"
    local sync_on_start="${SYNC_EXTENSIONS_ON_START:-true}"
    local normalized_mode normalized_toggle

    global_sync="$(echo "$global_sync" | tr '[:upper:]' '[:lower:]' | xargs)"
    if [ "$global_sync" = "false" ] || [ "$global_sync" = "0" ] || [ "$global_sync" = "no" ]; then
        echo "ℹ️ 已关闭整体配置同步，跳过插件目录同步"
        return
    fi

    normalized_mode="$(echo "$sync_mode" | tr '[:upper:]' '[:lower:]' | xargs)"
    normalized_toggle="$(echo "$sync_on_start" | tr '[:upper:]' '[:lower:]' | xargs)"

    if [ "$normalized_toggle" = "false" ] || [ "$normalized_toggle" = "0" ] || [ "$normalized_toggle" = "no" ]; then
        echo "ℹ️ 已关闭启动时插件同步"
        return
    fi

    if [ ! -d "$seed_dir" ]; then
        echo "ℹ️ 未找到插件 seed 目录，跳过同步: $seed_dir"
        return
    fi

    mkdir -p "$target_dir"

    case "$normalized_mode" in
        missing)
            echo "=== 同步内置插件（仅补充缺失项） ==="
            find "$seed_dir" -mindepth 1 -maxdepth 1 | while IFS= read -r seed_item; do
                local item_name target_item
                item_name="$(basename "$seed_item")"
                target_item="$target_dir/$item_name"
                if [ -e "$target_item" ]; then
                    continue
                fi
                cp -a "$seed_item" "$target_item"
                echo "➕ 已补充插件/文件: $item_name"
            done
            ;;
        overwrite)
            echo "=== 同步内置插件（强制覆盖） ==="
            # 仅删除 seed 中存在的同名项，以保留用户自行添加的其他插件
            find "$seed_dir" -mindepth 1 -maxdepth 1 ! -name '.seed-version' | while IFS= read -r seed_item; do
                rm -rf "$target_dir/$(basename "$seed_item")"
            done
            cp -a "$seed_dir"/. "$target_dir"/
            ;;
        seed-version|versioned|"")
            local seed_version current_version
            seed_version=""
            current_version=""
            if [ -f "$seed_version_file" ]; then
                seed_version="$(cat "$seed_version_file")"
            fi
            if [ -f "$target_version_file" ]; then
                current_version="$(cat "$target_version_file")"
            fi

            if [ -n "$seed_version" ] && [ "$seed_version" = "$current_version" ]; then
                echo "ℹ️ 内置插件已是最新 seed 版本: $seed_version"
                return
            fi

            echo "=== 同步内置插件（按 seed 版本） ==="
            if [ -n "$current_version" ]; then
                echo "当前插件 seed 版本: $current_version"
            else
                echo "当前插件 seed 版本: 未初始化"
            fi
            if [ -n "$seed_version" ]; then
                echo "镜像内置 seed 版本: $seed_version"
            else
                echo "镜像内置 seed 版本: 未标记，执行覆盖同步"
            fi
            # 仅删除 seed 中存在的同名项，以保留用户自行添加的其他插件
            find "$seed_dir" -mindepth 1 -maxdepth 1 ! -name '.seed-version' | while IFS= read -r seed_item; do
                rm -rf "$target_dir/$(basename "$seed_item")"
            done
            cp -a "$seed_dir"/. "$target_dir"/
            ;;
        *)
            echo "⚠️ 未识别的 SYNC_EXTENSIONS_MODE=$sync_mode，支持 missing / overwrite / seed-version，已跳过插件同步"
            return
            ;;
    esac

    if is_root; then
        chown -R node:node "$target_dir" || true
    fi

    rm -rf "$seed_dir"
    echo "🧹 已清空插件 seed 目录: $seed_dir"
    echo "✅ 内置插件同步完成，模式: ${normalized_mode:-seed-version}"
}
