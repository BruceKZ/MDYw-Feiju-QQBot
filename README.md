# MDY Feiju Bot Project

基于 [NapCat](https://github.com/NapNeko/NapCat-Docker) (OneBot 11) + [NoneBot2](https://nonebot.dev/) 的 QQ 机器人项目。

## ✨ 核心功能 (Core Features)

本项目通过不断迭代，已集成了一系列强大的定制化功能和插件：

*   **🛡️ 2FA 双重认证管理器**: 安全可靠地为指定用户/群组提供动态令牌(6位数)生成，支持超级管理员增加和管理密钥权限、管理用户备注，数据原生安全落盘于独立的本地 SQLite。
*   **🖼️ 自定义梗图/表情包 (Custom Memes)**: 增强版自建库！支持通过指令添加、调取纯文本或图文混合的自定义表情消息与别名。(注：同时也集成了官方的 `nonebot-plugin-petpet` 和 `nonebot-plugin-memes`)
*   **🔔 外部 Webhook 联动**: 内置对外 Webhook API 端点。可接收外部系统（如实验运行结束等）发送的 HTTP/JSON 数据，并在机器人上进行即时推送通知。
*   **📺 B 站解析 (Bilibili Parser)**: 能够自动嗅探捕捉聊天中的 B 站视频连接/小程序，并解析返回详细信息。
*   **👁️‍🗨️ 防撤回 (Anti-Recall)**: 捕捉并记录消息撤回动作。
*   *(注：NTP 缓慢的时间同步功能与庞大杂乱的词云功能已在最近一次重构中移除)*

## 🚀 快速开始 (Windows / Mac / Linux)

本项目已完全容器化，推荐使用 Docker 运行，无论是 Windows、Mac 还是 Linux 体验一致。

### 1. 前置准备

*   **Windows / Mac**: 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并启动。
*   **Linux**: 安装 Docker Engine 和 Docker Compose。

### 2. 配置环境

1.  在项目根目录复制 `.env.example` 为 `.env`：
    *   Windows (PowerShell): `cp .env.example .env`
    *   Mac/Linux: `cp .env.example .env`
2.  编辑 `.env` 文件，填入你的配置：
    ```ini
    # NapCat Configuration
    NAPCAT_ACCOUNT=123456789       # 你的 QQ 号
    ONEBOT_ACCESS_TOKEN=secret     # 设置一个 Token，用于 NapCat 和 NoneBot 通信鉴权
    
    # NoneBot Configuration
    SUPERUSERS=["123456789"]       # 机器人超级管理员 QQ 号列表
    ```

### 3. 启动服务

在项目根目录打开终端 (Windows 推荐使用 PowerShell 或 CMD)，运行：

```bash
docker-compose up -d
```

等待镜像拉取和构建完成。

### 4. 登录 QQ

服务启动后，NapCat 会启动并等待登录。

1.  访问 Web 管理面板: `http://localhost:6099/webui/` (Token 为 `docker-compose.yml` 中未设置时默认为空，或者查看日志)
    *   *注：本项目配置中未显式设置 WebUI Token，默认可能需要查看容器日志获取，或者配置 `NAPCAT_WEBUI_TOKEN`*
2.  或者直接扫描二维码登录：
    *   查看 NapCat 容器日志获取二维码:
        ```bash
        docker logs -f napcat
        ```
    *   使用手机 QQ 扫描终端显示的二维码即可登录。

### 5. 常用命令

*   **查看日志**:
    ```bash
    docker-compose logs -f
    ```
*   **重启服务**:
    ```bash
    docker-compose restart
    ```
*   **停止服务**:
    ```bash
    docker-compose down
    ```
*   **重建 NoneBot 镜像** (当修改了 python 代码或依赖时):
    ```bash
    docker-compose build nonebot
    docker-compose up -d
    ```

## 📂 项目结构

*   `docker-compose.yml`: 定义 NapCat 和 NoneBot 服务编排。
*   `napcat/`: 存放 NapCat 的配置和 QQ 数据 (自动生成)。
*   `mdy_feiju/`: NoneBot 机器人逻辑代码。

## 🛠️ 开发说明

*   Python 代码位于 `mdy_feiju/src/`。
*   修改代码后，重启 NoneBot 容器即可生效 (取决于是否挂载了源码，当前配置需重建或重启)。
```shell
docker-compose up -d --build nonebot 
```
