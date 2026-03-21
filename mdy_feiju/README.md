# MDY Feiju Bot (NoneBot Core)

> ⚠️ 该目录下主要为机器人的**核心业务代码 (Python 源码)**。
> 关于本项目的整体环境配置、Docker 部署信息及功能介绍，请统一回到项目根目录查看 **[`../README.md`](../README.md)**！

## 目录结构
- `src/plugins/`: 全部自定义插件（2FA, Webhook, 防撤回, 自定义表情等）。
- `data/`: 存放所有 SQLite 数据库、临时缓存和持久化文件，强烈建议不要将大体积 db 文件上传至 Git。
- `requirements.txt`: 机器人依赖管理。
- `Dockerfile`: 用于构建 `mdy_feiju` 容器环境的镜像文件。

## 开发调试

如果你需要在本地调试 (不使用根目录的 Docker-Compose)：
1. 确保你有 `Python >=3.9` 环境。
2. 在此目录下执行 `pip install -r requirements.txt`。
3. 执行 `nb run` (需依赖根目录的 `.env` 以及运行中的 NapCat 服务)。
