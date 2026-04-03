# 开发者说明

本文面向需要理解镜像构建与启动流程的维护者。

## 仓库关键文件

| 文件 | 说明 |
| --- | --- |
| [`Dockerfile`](../Dockerfile) | Docker 镜像构建定义（多阶段构建） |
| [`scripts/init.sh`](../scripts/init.sh) | 容器主入口脚本（orchestration 层） |
| [`scripts/init-*.sh`](../scripts/) | 模块化初始化脚本 |
| [`scripts/openclaw_config/`](../scripts/openclaw_config) | Python 配置管理模块 |
| [`docker-compose.yml`](../docker-compose.yml) | 默认部署编排 |
| [`.env.example`](../.env.example) | 环境变量模板 |
| [`openclaw.json.example`](../openclaw.json.example) | 默认配置结构示例 |
| [`README.md`](../README.md) | 项目入口文档 |

## 构建镜像

```bash
# 构建（启用 BuildKit 多阶段构建）
DOCKER_BUILDKIT=1 docker build -t justlikemaki/openclaw-docker-cn-im:latest .

# 或使用 docker compose
docker compose build
```

## 多阶段构建说明

Dockerfile 采用 5 阶段构建优化：

| Stage | 作用 |
|---|---|
| `builder` | 安装构建工具 (bun, uv, Python) |
| `base` | 基础系统环境 |
| `npm-deps` | npm 全局包安装 |
| `user-setup` | 用户级工具和插件 |
| `final` | 运行时配置 |

优势：
- 减小最终镜像体积（排除构建工具）
- 更好的构建缓存（修改代码只重建 final stage）
- 提高安全性（减少攻击面）

## 模块化启动脚本

[`scripts/init.sh`](../scripts/init.sh) 在容器启动时负责 orchestration，实际逻辑拆分为多个模块：

| 模块 | 职责 |
|---|---|
| [`init-utils.sh`](../scripts/init-utils.sh) | 共享工具函数 (`log_section`, `is_root`) |
| [`init-config.sh`](../scripts/init-config.sh) | 配置初始化、基础配置生成 |
| [`init-permissions.sh`](../scripts/init-permissions.sh) | 权限修复 |
| [`init-plugins.sh`](../scripts/init-plugins.sh) | 插件同步 |
| [`init-agent-reach.sh`](../scripts/init-agent-reach.sh) | Agent Reach 安装 |

### 启动流程

```bash
# init.sh main() 执行顺序：
1. ensure_directories        # 创建必要目录
2. ensure_config_persistence # .config 目录持久化
3. fix_permissions_if_needed # 修复权限
4. sync_seed_extensions      # 同步内置插件
5. install_agent_reach       # 安装 Agent Reach
6. sync_config_with_env     # 环境变量同步配置（调用 Python 模块）
7. finalize_permissions     # 最终权限修复
8. print_runtime_summary    # 打印运行时信息
9. setup_runtime_env        # 设置环境变量
10. start_gateway           # 启动 OpenClaw Gateway
```

## `openclaw.json` 的生成逻辑

首次启动时，如果 `/home/node/.openclaw/openclaw.json` 不存在，初始化脚本会基于环境变量生成配置，主要包括：

- 模型配置
- 通道配置
- Gateway 配置
- 插件启用配置
- 工具配置

如果宿主机已经挂载了自己的 `openclaw.json`，则通常会跳过自动生成过程。

## Python 配置模块

`scripts/openclaw_config/` 提供配置管理功能：

```bash
# 独立运行配置同步
CONFIG_FILE=/path/to/openclaw.json python3 -m openclaw_config sync
```

可用的子命令：
- `sync` - 根据环境变量同步配置
- `validate` - 验证配置文件

## 镜像中安装的主要组件

当前镜像内主要包含以下几类组件：

- 全局 Node.js 工具：`openclaw`、`opencode-ai`、`playwright`、`playwright-extra`、`puppeteer-extra-plugin-stealth`、`@steipete/bird`、`@tobilu/qmd`
- 浏览器与系统依赖：`chromium`、`ffmpeg`、`websockify`、`jq`、`gosu`、`python3` 等
- Linuxbrew 环境：`brew`
- 预装 / 预拉取的 IM 相关扩展与插件：
  - `openclaw-channel-dingtalk`
  - `openclaw-napcat`
  - `qqbot`
  - `@sunnoy/wecom`
- 飞书相关能力以镜像内预置配置和后续安装步骤为主，并不是直接全局安装 `@openclaw/feishu`

更准确的安装来源、安装方式与版本，以 [`Dockerfile`](../Dockerfile) 为准。

## 默认启动命令

容器最终通过以下方式启动：

```bash
openclaw gateway --verbose
```

入口点由 [`Dockerfile`](../Dockerfile) 中的 `ENTRYPOINT` 配合 [`scripts/init.sh`](../scripts/init.sh) 完成。

## 文档维护建议

当你修改以下文件时，建议同步检查文档是否需要更新：

- [`.env.example`](../.env.example)
- [`docker-compose.yml`](../docker-compose.yml)
- [`Dockerfile`](../Dockerfile)
- [`openclaw.json.example`](../openclaw.json.example)
- [`scripts/init.sh`](../scripts/init.sh) 及相关模块
