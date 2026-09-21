# jev-哑巴微信 · 第一版品牌改造验证

日期：2026-09-22。来源：完整克隆上游 21 个提交，起始 HEAD `f31bd7112624272644fd6889e2010b763d8e7ead`，本地分支 `brand/jev-yaba-wechat`。保留 `upstream` remote、原 LICENSE 和上游 README。本记录描述品牌改造时的本机验证情况；后续源码开源发布不代表补做了功能验收。

## 已完成

- 品牌名：jev-哑巴微信；独立 bundle ID：com.jevyaba.wechat。
- 透明背景吉祥物：1254 × 1254 PNG，包含真实 alpha。保留参考角色特征，增加微信绿双气泡胸针。生成提示完整保存在 assets/brand/PROMPT.md。
- 真正消费该资产：macOS .icns 图标、原生浮窗 NSImageView；菜单栏更名为「哑巴」，悬停说明显示完整品牌名。
- 浮窗：新增玫红品牌标题和标语「话我帮你想，发送你来定。」，浅粉背景与话术选择框，保留微信绿操作反馈。
- 新配置/日志/运行环境目录使用 jev-yaba-wechat；未读取或迁移旧接话的钥匙串密钥。
- 新增 Responses 生成分支，支持兼容服务 /responses 路径、官方 /v1/responses 路径和完整 endpoint。正文只取 output_text，拒绝失败、未完成和仅 reasoning 的结果。

## 验证证据

- Python 源码 compileall、zsh 脚本语法检查通过。
- 5 项离线 Responses 测试通过：请求形状与回复解析、不同基础路径、未完成/空正文拒绝、网络异常不换成样例、原 Chat Completions 路由保留。
- 本机证书签名和 codesign --verify --strict 通过；3.1 MB 分发 ZIP 已解压复验，应用名、启动器执行权限、plist、图标和 Python 版本文件均通过检查。未做 Apple 公证，未发布。
- build_app.sh 检查 bundle plist、启动器、源码、冻结锁文件、Python 版本、MIT 许可、品牌图片、.icns、NOTICE、无缓存和无内嵌密钥均通过。
- Computer Use 实际打开本机原生品牌预览，确认窗口标题、角色图片、品牌文本、标语、3 个话术下拉框可见。实际截图为 brand-preview.png。
- 预览明示「未读取微信 · 未调用模型」，未启动读屏 timer，未创建判断模型；不会触发本地模型下载或网络推理。仅为该预览安装独立的最小 PyObjC/numpy 虚拟环境，未安装完整推理环境。

## 未验收

- 新品牌应用的真实微信捕获、OCR、辅助功能填入。
- 用户 GPT/TypeSafe API 的真实请求、性能与回复质量。
- 完整启动器首次依赖安装、本地模型下载与推理。
- 分发公证、外部机器安装和权限授权。

品牌预览成功不等于完整产品可用。上游作者的实测结论未当作本机实测结果。

## 后续源码同步

2026-09-22：源码已合入 0.2.0 及后续更新，详情见 [版本同步记录](UPSTREAM_REVIEW.md)。上面的品牌构建与界面记录属于初版；本次同步未重新制作安装包，也未补做真实微信/API 验收。
