# 更新核对 · 2026-09-22

本次核对基准为 `f31bd7112624272644fd6889e2010b763d8e7ead`，远端 master 为 `51e752f`。通过 git fetch 获取实际提交与差异；网页抓取缓存可能仍显示旧版 README。

本次仅更新产品文档与仓库简介，没有合并以下运行逻辑变更，也没有进行真实微信或模型接口测试。

| 提交 | 变更 | 对当前版本的影响 |
|---|---|---|
| [08d2716](https://github.com/jev-jarvis/jev-jarvis/commit/08d2716) | 聊天区域图像指纹、静止/变化双档轮询、独立分析线程 | 当前版本尚未包含这些优化；不能引用新版本的延迟与 CPU 数据作为本版本性能 |
| [e4d9e02](https://github.com/jev-jarvis/jev-jarvis/commit/e4d9e02) | 精简 README，更新实测口径，简化 Issue/PR 模板 | 参考产品介绍结构，按本项目实际功能与 GPT 配置重写；未照搬实测数字 |
| [a977ae2](https://github.com/jev-jarvis/jev-jarvis/commit/a977ae2) | 版本升级为 0.2.0 | 本项目仍为自身的 0.1.0 开发预览版 |
| [51e752f](https://github.com/jev-jarvis/jev-jarvis/commit/51e752f) | 干净工作目录生成图标前先安装 Python 依赖 | 本项目的图标脚本已改用标准库调用 sips/iconutil，不依赖原图标脚本的 PyObjC 绘制方式，无需照搬完整依赖安装步骤 |

对应 [v0.2.0 Release](https://github.com/jev-jarvis/jev-jarvis/releases/tag/v0.2.0) 发布于北京时间 2026-09-22 01:10:59。

如后续合并轮询优化，需要检查快速切换会话、分析途中到达新消息、暂停/恢复及窗口关闭重开时的缓存和结果归属，再测响应时间。
