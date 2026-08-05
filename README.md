# 单词故事生成器 · Word Story

输入英文单词（1 个或多个） → 调用 DeepSeek 生成一句荒诞中文小故事，每个单词的中文含义都嵌在故事里并高亮显示。风格示例：

> marriage, against, produce, attention, dull
> 有个婚庆公司专门生产无聊的婚礼，吸引了很多注意力，大家都反对他们。

## 技术栈
- 后端：[Flask](https://flask.palletsprojects.com/) 单体应用（`index.py`），页面渲染 + `/api/generate` 接口都在同一个文件里
- 前端：单文件模板 `templates/index.html`（CSS/JS 内联，无构建步骤）
- 模型：DeepSeek `deepseek-chat`
- 部署：Vercel（Python runtime，见 `vercel.json`）
- 输出方式：**流式（Streaming）**——故事由 DeepSeek 边生成边返回，前端逐字显示打字机效果

## 接口说明（`/api/generate`）
- 请求：`POST`，`Content-Type: application/json`，body 为 `{"words": ["英文单词"...], "style": "荒诞脑洞"}`。单词数量 1–20 个。
- 响应：`Content-Type: application/x-ndjson`，每行一条 JSON（**不是**一次性返回整个 JSON 对象）：
  - `{"type":"chunk","text":"..."}` —— 故事正文的增量片段，前端实时拼接显示
  - `{"type":"meta","story":"完整故事","words":[{"word":"原词","cn":"中文"}]}` —— 流结束后给出规范故事与词表，用于高亮
  - `{"type":"done"}` —— 结束标记
  - `{"type":"error","error":"..."}` —— 出错时推送
- DeepSeek API Key 仅存在于服务端环境变量，前端永不持有。

## 本地运行
```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=你的Key      # Windows PowerShell: $env:DEEPSEEK_API_KEY="你的Key"
python index.py
# 打开 http://localhost:5000
```

## 部署到 Vercel（GitHub 导入）
1. 把本项目推送到一个 GitHub 仓库：
   ```bash
   git init
   git add .
   git commit -m "init word story"
   git branch -M main
   git remote add origin https://github.com/<用户名>/<仓库名>.git
   git push -u origin main
   ```
2. 打开 https://vercel.com/new ，点击 **Import Git Repository**，授权 GitHub 并选中该仓库。
3. Framework Preset 选 **Other**（或直接默认），先点 **Deploy**。
4. 进入项目 **Settings → Environment Variables**，新增：
   - 名称：`DEEPSEEK_API_KEY`
   - 值：你的 DeepSeek API Key
5. 回到项目页点 **Redeploy**，环境变量生效后即可使用。

## 申请 DeepSeek API Key
1. 注册登录 https://platform.deepseek.com
2. 左侧 **API Keys** → 创建 Key，复制保存（只显示一次）
3. 新账号有免费额度，调用 `deepseek-chat` 按 token 计费

## 自定义域名（可选）
Vercel 项目 **Settings → Domains** 添加你的域名，按提示配置 DNS 即可。

## 文件结构
```
wordstory-web/
├── index.py              # Flask 应用：页面路由 + /api/generate 流式调 DeepSeek（含小彩蛋）
├── templates/
│   └── index.html        # 前端页面（CSS/JS 内联）
├── requirements.txt      # flask, requests
├── vercel.json           # Vercel Python 构建与路由配置
├── .gitignore
└── README.md
```

## 故障排查
- **「服务端未配置 DEEPSEEK_API_KEY」**：Vercel 环境变量没加，或加了没重新 Deploy。
- **502 接口错误**：检查 Key 是否有效、账户是否欠费。
- **某个词没高亮**：模型用了与 `words` 里 `cn` 不一致的说法，属偶发，点「生成」重试即可。

## 新增：夯 / 拉 反馈与记忆

每次生成结果下方有「夯 👍 / 拉 👎」两个按钮。点「夯」会把这条结果存起来，并由模型自动生成一句"好在哪里"的特征；点「拉」只记录评价。下次生成时，所有「夯」的特征短句会被注入提示词，作为风格参考（**不存全文、不经过前端**）。

记忆保存在 **GitHub 仓库** 的 `data/feedback.json`（默认路径，可用 `GITHUB_DATA_PATH` 改）。你能在 GitHub 网页上直接查看 / 编辑 / 删除任意一条记录。

### 新增环境变量（Vercel → Settings → Environment Variables）
- `GITHUB_TOKEN`：有该仓库写入权限的 GitHub Personal Access Token（建议 fine-grained，仅授予该仓库的 Contents 读写）。
- `GITHUB_REPO`：仓库名，形如 `你的用户名/你的仓库名`。
- `GITHUB_DATA_PATH`（可选）：数据文件路径，默认 `data/feedback.json`。
- `GITHUB_BRANCH`（可选）：分支名，默认 `main`。
- `ADMIN_KEY`（可选）：设置后，管理页与接口需要 `?key=该值` 才能访问，避免公开部署时被他人清空。**公开部署强烈建议设置。**

### 管理页（删除 / 清空历史）
主页不再显示历史记录。访问隐藏地址管理所有记录：

```
https://你的域名/admin            # 若设置了 ADMIN_KEY：/admin?key=你的密钥
```

页面内可逐条删除或一键清空全部。

