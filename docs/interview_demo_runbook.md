# DeepLister 面试演示运行手册

## 线上演示

目标场景：面试前发给面试官，或现场直接打开公网链接。

推荐部署方式：

1. GitHub 仓库：`https://github.com/sunrise-yc/DeepLister`
2. Streamlit Community Cloud：入口文件选择 `streamlit_app.py`
3. 备选 Render：仓库根目录已经提供 `render.yaml`

线上环境需要安装 `requirements.txt`。普通体验、发起调研、邀请码作答、快速体验的规则追问不需要 API Key。只有开启 LLM 追问、自定义主题生成、GitHub 开发者认证时，才需要额外配置对应密钥。

## 本地备用演示

目标场景：现场网络不稳定，或线上平台冷启动较慢。

最简单方式：

```powershell
run_local.bat
```

或者手动执行：

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.port 8505 --server.headless false
```

打开：

```text
http://localhost:8505/?page=home
```

## 面试推荐演示路径

1. 首页：说明三类用户入口，强调不是展示页，而是可用的调研工作台。
2. 快速体验：选择一个主题和题量，展示规则追问或 LLM 追问。
3. 发起调研：创建项目、设置人数上限、生成邀请码。
4. 输入邀请码：模拟被调研者提交答卷。
5. 调研结果：展示发起者如何看回收结果。
6. 开发者模式：说明 GitHub OAuth 只允许开发者进入，看匿名回流和 Agent 影响。

## 现场注意

- 线上 demo 如果冷启动，先打开页面等几十秒。
- 本地 demo 不依赖公网，但 LLM 功能仍需要可用的 OpenAI 兼容 API Key。
- 不要把 `.streamlit/secrets.toml`、API Key、本地答卷、运行日志提交到公开仓库。
