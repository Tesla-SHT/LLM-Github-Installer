# 🚀 GitHub 项目智能安装器

一个基于大语言模型的智能工具，能够自动分析 GitHub 项目的 README 文件，并生成相应的安装和设置命令，帮助用户快速部署开源项目。

## ✨ 特性

- 🤖 **智能分析**: 使用大语言模型（通义千问/Google Gemini）分析项目 README
- 📋 **自动生成命令**: 根据项目特点生成适合的安装命令序列
- 🔄 **交互式执行**: 支持命令的逐步执行和错误处理
- 🌐 **多 API 支持**: 支持阿里云通义千问和 Google Gemini API
- 🐍 **环境优化**: 优先推荐使用 conda 虚拟环境进行依赖管理
- 🎨 **美观界面**: 使用 Rich 库提供彩色终端输出

## 🛠️ 安装

### 环境要求

- Python 3.7+
- 互联网连接
- 至少一个可用的 API 密钥（通义千问或 Google Gemini）

### 快速安装

1. 克隆项目：
```bash
git clone https://github.com/your-username/LLM-Github-Installer.git
cd LLM-Github-Installer
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并添加您的 API 密钥：
```env
# 阿里云通义千问 API（二选一）
DASHSCOPE_API_KEY="your_dashscope_api_key_here"

# Google Gemini API（二选一）
GOOGLE_API_KEY="your_google_api_key_here"
```

## 🚀 使用方法

### 基本使用

运行主程序：
```bash
python main.py
```

然后按照提示：
1. 选择要使用的 API 提供商（通义千问或 Gemini）
2. 输入 GitHub 项目链接
3. 查看大模型生成的安装命令
4. 选择执行、跳过或编辑命令

### 使用示例

```bash
$ python main.py
🚀 GitHub 项目智能安装器

请选择API提供商:
1. 通义千问 (qwen-turbo)
2. Google Gemini (gemini-2.0-flash)
请输入选择 (1-2): 1

请输入 GitHub 项目链接: https://github.com/example/awesome-project

[AI] 正在向通义千问 (qwen-turbo) 请求初始命令...

━━━━━━━━━━━━━━━━━━━━ 大模型推荐的初始命令 ━━━━━━━━━━━━━━━━━━━━
1  conda create -n awesome-project python=3.8 -y
2  conda activate awesome-project
3  git clone https://github.com/example/awesome-project.git
4  cd awesome-project
5  pip install -r requirements.txt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

命令 1/5: conda create -n awesome-project python=3.8 -y
选择操作: [e]执行 / [s]跳过 / [m]修改 / [q]退出: e
```

## 📁 项目结构

```
LLM-Github-Installer/
├── main.py                 # 主程序入口
├── config.py              # 配置管理（环境变量、API选择）
├── github_utils.py        # GitHub 相关工具函数
├── llm_providers.py       # LLM API 提供商封装
├── command_executor.py    # 命令执行器
├── requirements.txt       # 项目依赖
├── .env.example          # 环境变量模板
└── discard/              # 废弃的实验代码
    └── gemini-api.ipynb  # Gemini API 测试笔记
```

## 🔧 配置说明

### API 配置

#### 通义千问 API
1. 访问 [阿里云灵积平台](https://dashscope.console.aliyun.com/)
2. 获取 API 密钥
3. 在 `.env` 文件中设置 `DASHSCOPE_API_KEY`

#### Google Gemini API
1. 访问 [Google AI Studio](https://aistudio.google.com/)
2. 获取 API 密钥
3. 在 `.env` 文件中设置 `GOOGLE_API_KEY`

### 支持的模型

- **通义千问**: `qwen-turbo`, `qwen-plus`, `qwen-max`
- **Google Gemini**: `gemini-2.0-flash`, `gemini-1.5-pro`

## 🎯 核心功能

### 1. README 分析
- 自动获取 GitHub 项目的 README 文件
- 支持多种 README 格式（.md, .rst, .txt）
- 智能解析安装步骤和依赖关系

### 2. 命令生成
- 基于项目特点生成定制化命令
- 优先推荐 conda 虚拟环境
- 处理占位符和用户输入项

### 3. 交互式执行
- 逐步执行生成的命令
- 实时显示执行结果和错误信息
- 支持命令修改和跳过

### 4. 错误处理
- 自动将执行结果反馈给 LLM
- 基于错误信息生成修复命令
- 智能重试机制

## 📝 示例场景

### 深度学习项目
```bash
输入: https://github.com/pytorch/pytorch
生成命令:
1. conda create -n pytorch python=3.8 -y
2. conda activate pytorch
3. conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
4. git clone https://github.com/pytorch/pytorch.git
5. cd pytorch
6. python setup.py develop
```

### Web 应用项目
```bash
输入: https://github.com/flask/flask
生成命令:
1. conda create -n flask-env python=3.9 -y
2. conda activate flask-env
3. git clone https://github.com/flask/flask.git
4. cd flask
5. pip install -e .
6. export FLASK_APP=src/flask
7. flask run
```

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📋 TODO

- [ ] 支持更多 LLM 提供商（OpenAI GPT, Claude 等）
- [ ] 添加命令执行历史记录
- [ ] 支持批量处理多个项目
- [ ] 添加 GUI 界面
- [ ] 支持 Docker 容器化部署
- [ ] 添加命令模板系统

## ⚠️ 注意事项

1. **API 费用**: 使用 LLM API 可能产生费用，请注意用量控制
2. **命令安全**: 执行前请仔细检查生成的命令，避免潜在的安全风险
3. **网络要求**: 需要稳定的网络连接访问 GitHub 和 API 服务
4. **权限问题**: 某些命令可能需要管理员权限

## 📄 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Rich](https://github.com/Textualize/rich) - 美观的终端输出
- [阿里云通义千问](https://tongyi.aliyun.com/) - 强大的中文 LLM
- [Google Gemini](https://ai.google.dev/) - 先进的多模态 AI
- [python-dotenv](https://github.com/theskumar/python-dotenv) - 环境变量管理

## 📞 联系方式

如有问题或建议，请：
- 提交 [Issue](https://github.com/your-username/LLM-Github-Installer/issues)
- 发送邮件至：your-email@example.com

---

⭐ 如果这个项目对您有帮助，请给个 Star！