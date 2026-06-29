# DeepLister 部署说明

## 项目简介

DeepLister 是一个 Streamlit Demo，用来展示“AI 辅助问卷调研与人格测评”。它可以导入问卷、生成调研 Agent、进行快速测试或 MBTI 测试，并展示答卷结果。

这个项目适合两种演示方式：

- 公网演示：部署到 Streamlit Community Cloud，面试官和其他设备都可以直接打开网页。
- 本地备用：面试现场网络不稳定时，在自己的电脑上运行，再用浏览器或局域网设备访问。

当前公网演示地址：

```text
https://deeplister-3cwgw9zxuoewyhrwhr5y7f.streamlit.app/?page=home
```

当前主入口文件是根目录的 `app.py`。`streamlit_app.py` 只是兼容旧部署的转发入口。

## 本地运行步骤

先进入项目根目录，然后安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动本地 Demo：

```powershell
streamlit run app.py --server.port 8505
```

浏览器打开：

```text
http://localhost:8505/?page=home
```

也可以直接双击或运行：

```powershell
run_local.bat
```

## 局域网访问

如果想让手机或 iPad 访问电脑上的本地 Demo，用下面的命令启动：

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8505
```

然后在电脑上查局域网 IP：

```powershell
ipconfig
```

找到类似 `192.168.x.x` 的 IPv4 地址后，在手机或 iPad 浏览器打开：

```text
http://电脑局域网IP:8505/?page=home
```

注意：手机不能访问 `localhost`，因为手机上的 `localhost` 指的是手机自己，不是你的电脑。

## Streamlit Cloud 部署步骤

1. 把项目推送到 GitHub 仓库，例如 `https://github.com/sunrise-yc/DeepLister`。
2. 打开 [Streamlit Community Cloud](https://streamlit.io/cloud)。
3. 选择 GitHub 仓库和分支。
4. Main file path 填：

```text
app.py
```

5. 点击部署，等待平台安装 `requirements.txt` 里的依赖。
6. 部署完成后，打开平台给出的公网地址。
7. 如果需要大模型或 GitHub OAuth，在 Streamlit Cloud 的 Secrets 页面配置密钥，不要把真实密钥写进代码。

本项目当前已部署的公网地址是：

```text
https://deeplister-3cwgw9zxuoewyhrwhr5y7f.streamlit.app/?page=home
```

官方参考：

- [Streamlit Community Cloud 部署文档](https://docs.streamlit.io/deploy/streamlit-community-cloud)
- [Streamlit Secrets 管理文档](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

## GitHub 仓库需要具备的文件

这些文件应该提交到 GitHub：

- `app.py`
- `streamlit_app.py`
- `requirements.txt`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `assets/`
- `public/`
- `data/sample_scl90.json`
- `data/mbti_deeplister_questionnaire.json`
- `core/`
- `shared/`
- `storage/`
- `memory/`
- `DEPLOYMENT.md`
- `DEMO_GUIDE.md`

这些文件不要提交真实内容：

- `.streamlit/secrets.toml`
- `.env`
- 本地日志文件
- 本地运行缓存
- 私人的 API Key、账号密码、真实问卷隐私数据

## 可选密钥配置

本地可以复制示例文件：

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

然后只在自己的电脑上填写真实密钥。真实的 `.streamlit/secrets.toml` 已经被 `.gitignore` 忽略，不应该提交到 GitHub。

如果只是演示普通问卷、快速测试、MBTI 测试，可以不配置 API Key。

## 页面和 URL 参数

这个项目没有使用 Streamlit 原生 `pages/` 文件夹。页面是在 `app.py` 里通过 URL 参数控制的。

常用地址：

```text
/?page=home
/?page=quick
/?page=mbti
/?page=import
/?page=take
/?page=results
```

所以本地首页可以这样打开：

```text
http://localhost:8505/?page=home
```

## 常见问题排查

### 本地能跑，云端不能跑

先看 Streamlit Cloud 的日志。通常是依赖没装上、入口文件填错、密钥没配置，或者资源文件没有提交到 GitHub。

### requirements.txt 缺依赖

当前主要依赖是：

```text
streamlit
openai
pydantic
requests
pillow
```

如果云端提示 `ModuleNotFoundError`，说明代码用了新库但 `requirements.txt` 没写进去。

### 资源文件路径错误

代码应该用相对项目的路径，例如 `ROOT / "assets" / "xxx.png"`。不要写只能在自己电脑上使用的本机绝对路径。

### secrets 没有配置

如果开启 LLM 功能或 GitHub OAuth，需要配置 Secrets。普通 Demo 可以不配置。

### 手机无法访问 localhost

手机访问本地 Demo 时不能用 `localhost`。请用电脑的局域网 IP，例如：

```text
http://192.168.1.23:8505/?page=home
```

### 页面刷新或参数跳转异常

确认 URL 里有正确的 `page` 参数，例如 `?page=home`。如果参数写错，项目会回到首页。

### Streamlit Cloud 数据会不会永久保存

当前项目用本地 JSON 文件模拟存储。Streamlit Cloud 上的磁盘更适合临时 Demo，不适合作为长期数据库。面试演示够用，但正式产品需要换成数据库或云存储。
