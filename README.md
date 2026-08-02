# 单词故事生成器 · Word Story

输入 5 个以上英文单词 → 调用 DeepSeek 生成一句荒诞中文小故事，每个单词的中文含义都嵌在故事里并高亮显示。风格示例：

> marriage, against, produce, attention, dull
> 有个婚庆公司专门生产无聊的婚礼，吸引了很多注意力，大家都反对他们。

## 技术栈
- 后端：[Flask](https://flask.palletsprojects.com/) 单体应用（`index.py`），页面渲染 + `/api/generate` 接口都在同一个文件里
- 前端：单文件模板 `templates/index.html`（CSS/JS 内联，无构建步骤）
- 模型：DeepSeek `deepseek-chat`
- 部署：Vercel（Python runtime，见 `vercel.json`）

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
├── index.py              # Flask 应用：页面路由 + /api/generate 调 DeepSeek
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
