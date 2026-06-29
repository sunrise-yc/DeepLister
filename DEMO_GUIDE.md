# DeepLister 面试演示说明

## 演示原则

面试时优先打开公网 Streamlit 地址。这样面试官可以在任何设备上直接访问。

如果公网较慢、冷启动太久，或者现场网络不稳定，就切换到本地版本：

```powershell
streamlit run app.py --server.port 8505
```

本地打开：

```text
http://localhost:8505/?page=home
```

如果要用手机或 iPad 看本地版本：

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8505
```

然后打开：

```text
http://电脑局域网IP:8505/?page=home
```

## 建议演示顺序

1. 首页：说明这是一个可以实际操作的问卷调研 Demo，不只是静态展示页。
2. 导入问卷：展示可以上传 JSON 或 docx 问卷，并生成可作答的调研 Agent。
3. 快速测试：选择一个主题，快速体验 Agent 如何提问和追问。
4. MBTI 测试：展示人格测评场景，说明 Demo 不只支持单一问卷。
5. 结果展示或分析页面：展示答卷如何沉淀成结果，说明项目闭环。

## 简短介绍词

这是一个 AI 辅助问卷调研与人格测评 Demo。传统问卷只能收集固定答案，但 DeepLister 会在用户回答含糊、信息不足或需要补充细节时进行追问，让问卷更接近一次轻量访谈。项目用 Streamlit 实现，可以公网部署，也可以本地离线备用，适合面试现场稳定演示。

## 备用说明

如果现场网络不稳定，我可以切换到本地运行版本。它和线上版本使用同一个 `app.py` 入口，功能与线上版本一致，只是访问地址从公网链接换成了 `localhost` 或局域网 IP。

## 演示前检查清单

- 已经能打开公网 Streamlit 地址。
- 本地已经安装依赖：`python -m pip install -r requirements.txt`。
- 本地能运行：`streamlit run app.py --server.port 8505`。
- 首页地址可用：`http://localhost:8505/?page=home`。
- 需要演示的样例问卷和图片资源已经在 GitHub 仓库里。
- 不把 API Key、账号密码、真实隐私问卷数据展示给面试官。
