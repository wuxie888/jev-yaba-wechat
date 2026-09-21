# jev-哑巴微信

**话我帮你想，发送你来定。**

<p align="center"><img src="assets/brand/mascot-v1.png" width="320" alt="jev-哑巴微信吉祥物"></p>

基于 [jev-jarvis/jev-jarvis](https://github.com/jev-jarvis/jev-jarvis) 改造的 macOS 微信回复助手：在微信旁读当前聊天、分析意图、生成不同语气的候选，再由你选择填入和发送。

## 当前版本

**开发预览版：源码已开放，真实微信/API 完整流程尚未验收。**

这一版完成品牌更名、玫红吉祥物、微信绿胸针、应用图标、浮窗品牌区、菜单栏和独立配置目录；保留上游读屏、OCR、判断、话术、填入逻辑。补充 GPT Responses 接口，继续支持上游 Chat Completions。

品牌预览不是实际聊天结果。构建、界面和离线接口测试与真实微信/API 联调分开记录，见 [验证记录](docs/BRAND_VERIFICATION.md)。

## 打包与启动

需要 macOS 13+。克隆本仓库后进入目录执行：

```sh
./packaging/build_app.sh
open 'jev-哑巴微信.app'
```

应用包是上游方案的 Python 启动器：首次正式启动会安装锁定的运行依赖。判断层未配置 TypeSafe key 时仍采用上游本地模型，首次分析可能下载约 7 GB 模型。品牌预览模式不会下载模型、读屏或发网络请求。

```sh
# 完整依赖已安装时，可直接查看品牌界面
uv run python src/hud.py --brand-preview
```

## GPT 配置

配置文件使用本品牌独立目录 `~/.config/jev-yaba-wechat/env`。不会自动读取或迁移旧接话钥匙串，也不会覆盖上游 jev-jarvis 的配置。

```sh
OPENAI_API_KEY=填写你的key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=your-gpt-model-id
OPENAI_API_FORMAT=responses
TYPESAFE_API_KEY=填写你的TypeSafekey
TYPESAFE_BASE_URL=https://api.typesafe.ai
TYPESAFE_MODEL=jev-latest
```

将 `your-gpt-model-id` 替换成你账号可用的 GPT 模型 ID。也可配置自己的兼容服务地址。Responses 路径为 `/responses`，不会自动插入 `/v1`；使用上述官方 `/v1` 基础地址时，实际路径为 `/v1/responses`。若切换到 Chat Completions，设置 `OPENAI_API_FORMAT=openai`。

Key 只放在本机配置，建议文件权限 600。配置属于使用者自己的本机环境，不随源码发布。离线请求结构测试不代表实际接口已连通。

## 品牌预览

![原生浮窗品牌预览：未读取聊天、未调用模型](docs/brand-preview.png)

## 品牌资产

- `assets/brand/mascot-v1.png`：透明背景形象，保留无嘴表情、玫红圆身体、青色眼睛与黑色几何徽记，增加微信绿双气泡胸针。
- `assets/brand/PROMPT.md`：内置 imagegen 的完整编辑提示与来源记录。
- `src/brand.py`：品牌名、标语、资源路径。
- `packaging/make_icon.py`：将同一形象转换为 macOS 图标尺寸，不再重绘另一个角色。

## 上游与许可

本项目保留上游提交历史，起始提交 `f31bd7112624272644fd6889e2010b763d8e7ead`。完整原 README 保存在 [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md)，MIT 原文在 [LICENSE](LICENSE)，归属说明在 [NOTICE.md](NOTICE.md)。

现有局限仍包括 OCR 受布局影响、引用/图片/文章卡片可能识别不完整、真实填入需要辅助功能权限。品牌调整不意味着这些问题已经在本机验证解决。
