# Words to Story

> 丢几个英文单词进去，看 AI 把它们编成一段故事。

## 它是什么

一个极简的网页小工具。输入 1-20 个英文单词，选择风格（荒诞脑洞 / 温馨治愈 / 悬疑推理 / 童话奇遇），DeepSeek 会把这些词串成一段完整的中文故事——故事逐字流式输出，像在屏幕上一行一行长出来。

## 为什么做

背单词很累。但如果每个词都是一段冒险、一个谜、一次相遇，就不一样了。这是语言学习与叙事体验的一次交叉实验。

## 怎么用

1. 在输入框里丢几个英文词（用英文逗号或空格分隔）
2. 选一个风格
3. 点「开始」
4. 看着故事长出来
5. 喜欢就点「夯」，不喜欢就点「拉」

也可以点「试一个示例」，随机抽 5 个英文词直接开始。

## 彩蛋

试试输入 **吴诗琦** 或 **申哲**。

## 技术栈

| 层 | 选型 |
|---|---|
| 框架 | Flask（单文件 `index.py`） |
| 部署 | Vercel（Serverless） |
| AI | DeepSeek API（流式 SSE） |
| 持久化 | GitHub Repository（读写 JSON） |
| 前端 | 原生 HTML/CSS/JS，零依赖 |

## 环境变量

部署到 Vercel 需要配置：

- `DEEPSEEK_API_KEY` — DeepSeek API 密钥
- `GITHUB_TOKEN` — 具有 repo 读写权限的 Personal Access Token
- `GITHUB_REPO` — 形如 `owner/repo` 的仓库名
- `ADMIN_KEY` — （可选）保护 `/admin` 管理页的密钥

## 管理

`/admin` 页面可以查看所有生成记录、评价数据，按用户筛选，设置用户名，删除或清空记录。所有数据以 JSON 格式存储在 GitHub 仓库中，可直接查看和编辑。

---

Made by Grayson Shen
