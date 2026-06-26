# YouTube → DeepSeek 自动化摘要工具

从 YouTube 视频提取 CC 字幕 → DeepSeek 深度分析 → 输出排版精美的 HTML 网页。

全程后台运行（CDP 协议操控 Edge），不抢鼠标键盘。

## 效果演示

```
YouTube URL
    │
    ▼
[1] yt-dlp 离线抓取 CC 字幕 → 剪贴板
    │
    ▼
[2] Playwright CDP 连接 Edge → 粘贴到 DeepSeek → 发送
    │
    ▼
[3] 等待 30 秒生成回复 → 提取（排除思维链）→ 清理引用角标
    │
    ▼
[4] Markdown → HTML 排版 → 输出到桌面（.html + .txt）
```

## 前提条件

- **Windows 10/11**  +  **Python 3.12+**
- **Microsoft Edge** 浏览器
- 已登录 DeepSeek 网页版（chat.deepseek.com）

## 安装

```bash
git clone https://github.com/wudibaolongxiaozi/yt-deepseek-summarizer.git
cd yt-deepseek-summarizer

pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### 1. 启动 Edge 调试模式

双击运行，或手动执行：

```bash
scripts\launch_edge_debug.bat
```

或手动命令行：

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

### 2. 运行

```bash
python yt_to_deepseek.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

输出文件会出现在桌面上：
- `视频标题.html` — 排版精美的网页版
- `视频标题.txt` — 纯文本备用

## 项目结构

```
yt-deepseek-summarizer/
├── README.md
├── requirements.txt
├── .gitignore
├── yt_to_deepseek.py            # 主入口：编排全流程
├── subtitle_extractor.py         # YouTube CC 字幕提取
├── deepseek_automation.py        # DeepSeek CDP 后台自动化
└── scripts/
    └── launch_edge_debug.bat     # Edge 调试模式启动器
```

## 工作原理

| 环节 | 技术 | 说明 |
|------|------|------|
| 字幕提取 | yt-dlp | 离线下载 YouTube CC 字幕（优先中文手动字幕） |
| 剪贴板 | PowerShell | 读取系统剪贴板 Unicode 文本 |
| 浏览器操控 | Playwright + CDP | 连接已运行的 Edge，DOM 级操作 DeepSeek 页面 |
| 回复提取 | DOM 解析 | 识别并排除思维链，提取最终回复 |
| 文本清理 | 正则 | 清除 DeepSeek 引用角标碎片 |
| 排版输出 | Markdown→HTML | 纯 Python 实现，无外部依赖 |

## 常见问题

**Q: Edge 连接失败？**
A: 确保 Edge 以 `--remote-debugging-port=9222` 启动。脚本会自动检测并尝试重启。

**Q: DeepSeek 要求登录？**
A: CDP 连接复用了你本地 Edge 的登录状态。确保在 Edge 中已登录 DeepSeek。

**Q: 提取的内容包含思维链？**
A: 不会。脚本通过 `[class*=think]` 选择器识别并排除思考过程，只保留最终回复。

**Q: 提取时间太长？**
A: 默认等待 30 秒。可以在 `deepseek_automation.py` 中修改 `time.sleep(30)`。

**Q: 文件名太长？**
A: 自动截断到 120 字符以内，避免 Windows MAX_PATH 限制。

**Q: 支持其他 AI 平台吗？**
A: 修改 `deepseek_automation.py` 中的 `DEEPSEEK_URL` 和选择器即可适配其他平台。

## License

MIT
