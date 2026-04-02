# 高级使用

本文收集不走默认新手路径时常会用到的操作，包括使用 `docker run` 直接启动、数据持久化说明、端口说明与自定义配置文件方式。

## 使用 Docker 命令直接运行

如果不使用 [`docker-compose.yml`](../docker-compose.yml)，也可以直接使用 `docker run`：

```bash
docker run -d \
  --name openclaw-gateway \
  --cap-add=CHOWN \
  --cap-add=SETUID \
  --cap-add=SETGID \
  --cap-add=DAC_OVERRIDE \
  -e MODEL_ID=model id \
  -e BASE_URL=http://xxxxx/v1 \
  -e API_KEY=123456 \
  -e API_PROTOCOL=openai-completions \
  -e CONTEXT_WINDOW=200000 \
  -e MAX_TOKENS=8192 \
  -e FEISHU_APP_ID=your-app-id \
  -e FEISHU_APP_SECRET=your-app-secret \
  -e OPENCLAW_GATEWAY_TOKEN=123456 \
  -e OPENCLAW_GATEWAY_BIND=lan \
  -e OPENCLAW_GATEWAY_PORT=18789 \
  -v ~/.openclaw:/home/node/.openclaw \
  -v ~/.openclaw/workspace:/home/node/.openclaw/workspace \
  -p 18789:18789 \
  -p 18790:18790 \
  --restart unless-stopped \
  justlikemaki/openclaw-docker-cn-im:latest
```

## 数据持久化

默认持久化目录：

- `/home/node/.openclaw`：OpenClaw 配置和数据目录
- `/home/node/.openclaw/workspace`：工作空间目录

在 Compose 方式下，宿主机目录由 [`.env.example`](../.env.example) 中的 `OPENCLAW_DATA_DIR` 控制。

## 端口说明

| 端口 | 说明 |
| --- | --- |
| `18789` | OpenClaw Gateway |
| `18790` | OpenClaw Bridge |

## 自定义配置文件

如果你不希望完全依赖环境变量生成配置，也可以手动维护 `openclaw.json`：

1. 在宿主机创建 `~/.openclaw/openclaw.json`
2. 挂载目录到容器：`-v ~/.openclaw:/home/node/.openclaw`
3. 容器启动时检测到现有配置后，将跳过自动生成步骤

配置结构可参考 [`openclaw.json.example`](../openclaw.json.example)。

## 适合查看的相关文件

- 镜像构建：[`Dockerfile`](../Dockerfile)
- 启动逻辑：[`init.sh`](../init.sh)
- Compose 编排：[`docker-compose.yml`](../docker-compose.yml)
- 配置模板：[`docs/configuration.md`](configuration.md)
