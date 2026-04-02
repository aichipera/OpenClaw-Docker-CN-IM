# OpenClaw 脚本目录

本目录包含 OpenClaw Docker 镜像的入口脚本和配置管理工具。

## 目录结构

```
scripts/
├── init.sh                  # 容器主入口脚本
├── openclaw-config/        # Python 配置管理模块
│   ├── __init__.py
│   ├── __main__.py          # CLI 入口
│   ├── cli.py               # 命令行接口
│   ├── sync.py              # 配置同步逻辑
│   ├── validators.py        # 配置验证
│   ├── models.py            # 数据模型
│   ├── migrate.py           # 配置迁移
│   └── tests/               # 单元测试
│       ├── __init__.py
│       └── test_sync.py
└── README.md                # 本文件
```

## 使用方式

### 方式 1：Docker 部署（推荐）

```bash
git clone https://github.com/justlikemaki/OpenClaw-Docker-CN-IM.git
cd OpenClaw-Docker-CN-IM

cp .env.example .env
# 编辑 .env 配置文件

docker compose up -d
```

### 方式 2：仅拷贝脚本

```bash
cp -r scripts/ /your/path/

# 修改 Dockerfile 引用路径
COPY ./your-path/scripts/init.sh /usr/local/bin/init.sh
```

### 方式 3：非 Docker 环境测试

```bash
cd scripts

# 安装依赖
pip install pytest

# 运行测试
python -m pytest openclaw-config/tests/ -v

# 测试配置同步
export MODEL_ID=gpt-4
export BASE_URL=https://api.openai.com/v1
export API_KEY=test-key

python -m openclaw_config sync --config-file /path/to/openclaw.json --dry-run
```

## 开发指南

### 运行测试

```bash
cd scripts
python -m pytest openclaw-config/tests/ -v
```

### 单独测试配置同步

```bash
python -m openclaw_config sync \
  --config-file /path/to/openclaw.json \
  --dry-run
```

### 验证配置文件

```bash
python -m openclaw_config validate \
  --config-file /path/to/openclaw.json
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `init.sh` | 容器入口脚本，负责初始化配置、权限、插件等 |
| `openclaw-config/` | Python 配置管理模块，可独立使用 |

## 注意事项

1. `init.sh` 设计为在 Docker 容器内运行，部分功能依赖容器环境
2. `openclaw-config/` 模块可在非容器环境下独立测试和使用
3. 测试用例使用 pytest 框架，需要 Python 3.12+ 环境