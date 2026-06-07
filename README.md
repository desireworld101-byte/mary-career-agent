# Mary 的大学生求职智能体 Demo

这是一个可部署到公网的前后端一体 Demo。部署后，用户只需要打开公网链接即可使用，不需要在自己的电脑安装模型或运行代码。

## 本地启动

```bash
cd "/Users/desireworld/Documents/AI-HR demo"
python3 server.py
```

打开：

```text
http://127.0.0.1:8000
```

## 公网部署

可部署到 Render、Railway、Fly.io 等支持 Python Web Service 的平台。

启动命令：

```bash
python3 server.py
```

服务会自动读取平台提供的 `PORT`，并监听 `0.0.0.0`，适合公网访问。

## 在线 DeepSeek 大模型

本产品使用服务端调用在线 DeepSeek API。用户不需要配置任何模型或密钥。

部署方需要在云平台环境变量中配置：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
```

如果没有配置 `DEEPSEEK_API_KEY`，系统会自动回退到规则引擎，上传、画像、匹配、看板和 DOC 下载仍可使用。

## 多用户隔离

后端使用浏览器会话隔离用户数据。每个访问者的简历、画像、投递看板和下载文件互不覆盖。

## 已实现功能

- 简历上传与文本兜底
- 作品集/补充材料选择性上传
- 学生画像生成
- MBTI、性格、base 城市、工作强度、岗位方向等可选偏好
- 岗位匹配与匹配解释
- 简历优化建议与可编辑 DOC 下载
- 投递看板：感兴趣、已投递、面试中、等待结果
- 可选择看板中的岗位生成面试准备包

一键优化遵守真实性保护：基于用户上传的原简历内容生成优化后的 DOC 文档，只优化结构和表达，不虚构学历、公司、经历、证书和结果数据。
