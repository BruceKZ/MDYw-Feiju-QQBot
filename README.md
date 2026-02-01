# MDY Feiju Bot Project

基于 [NapCat](https://github.com/NapNeko/NapCat-Docker) (OneBot 11) + [NoneBot2](https://nonebot.dev/) 的 QQ 机器人项目。

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

```
