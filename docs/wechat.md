# 微信 (WeChat) 接入指南

> 🛡️ **官方版** — 通过微信官方插件接入 OpenClaw

---

## 快速安装

由于微信官方插件的安装过程涉及交互和环境配置，建议使用本项目提供的**安装助手（独立工具容器）**来完成。

### 1. 启动安装助手容器

在宿主机项目根目录下运行：

```bash
docker compose --profile tools up -d openclaw-installer
```

### 2. 进入容器执行安装命令

```bash
docker exec -it openclaw-installer bash
su node
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

按照终端提示完成微信账号的绑定与配置。

## 配置说明

安装助手执行完成后，相关的配置会自动写入容器卷挂载的 `openclaw.json`。你可以在其中找到 `weixin` 渠道的配置段。


## 激活渠道

安装并配置完成后，你需要重启主服务容器以加载新配置：

```bash
docker compose restart openclaw-gateway
```
