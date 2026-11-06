# Freya AI Agent Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![Home Assistant Version](https://img.shields.io/badge/Home%20Assistant-2026.2.0%2B-blue.svg)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/eoasmxd/ha-integration-freya)](https://github.com/eoasmxd/ha-integration-freya/releases)

Home Assistant integration for [Freya](https://github.com/eoasmxd/freya) — a lightweight microkernel AI agent system.
[Freya](https://github.com/eoasmxd/freya) 微内核智能体 · Home Assistant 原生集成。

---

### Overview

This custom integration bridges Home Assistant with the **Freya AI Agent**:
- **Conversation Assistant**: Acts as a native `conversation` agent for Home Assistant Assist (voice & text chat).
- **Automation Action (`freya.chat`)**: Enables calling the agent from scripts and automations with support for multi-turn sessions, dynamic toolbox activation, skill routing, and response capture.

> 💡 **Prerequisite**: Freya server must be running (either as a Home Assistant App or as a standalone service).

### ✨ Features

- 🗣️ **Native Assist Conversation Agent**: Select Freya directly in **Settings -> Voice assistants** to chat with your configured LLM agent.
- 🛠️ **`freya.chat` Action / Service**:
  - `content`: Message payload.
  - `session_id`: Multi-turn context continuity (optional).
  - `attachments`: Optional list/string of attachments (supports web URLs or local paths like `/config/www/snapshot.jpg`).
  - `toolboxes`: Pass allowed toolbox IDs (e.g. `["homeassistant"]`).
  - `skill_id`: Prioritize or trigger dedicated skills.
  - **Response**: Captures agent text response (`text`) via `response_variable`.

### Installation & Setup

#### Step 1: Install Integration (via HACS)

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=eoasmxd&repository=ha-integration-freya)

1. Click the badge above to open the repository directly in Home Assistant, or open **HACS -> Integrations** and search for **Freya**.
2. Click **Download**, then restart Home Assistant after the download completes.

#### Step 2: Run Freya Server

Freya integration communicates with the Freya Agent server. Run the server using one of the following methods:

- **Option A: Home Assistant App (Recommended)**

  [![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Feoasmxd%2Fha-addons)

  Click the badge above to add the official repository, then install and start the **Freya** app.
- **Option B: Standalone / Docker Deployment**
  Follow the [Freya documentation](https://github.com/eoasmxd/freya) to run the server in a container or external host.

#### Step 3: Add Integration

1. In Home Assistant, go to **Settings -> Devices & services -> Add integration**.
2. Search for and select **Freya AI Agent**.
3. Complete the setup wizard:
   - **App Deployment**: The wizard detects and connects to the local app automatically.
   - **Standalone Deployment**: Enter the server URL (e.g. `http://192.168.1.100:3000`) and optional access token/password.

### Service Usage Example

```yaml
action: freya.chat
data:
  content: "Summarize the energy usage today"
  session_id: "daily-energy-summary"
  toolboxes:
    - homeassistant
response_variable: agent_reply
# Access response text in subsequent steps: {{ agent_reply.text }}
```

---

### 概述

本集成是将 **Freya 微内核智能体系统** 接入 Home Assistant 的原生桥梁：
- **对话代理助手**：作为原生 `conversation` 平台实体，可直接设为 Assist 对话助手（支持语音与文字聊天）。
- **自动化动作 (`freya.chat`)**：在自动化、脚本中直接调度智能体，支持多轮会话记忆、工具箱动态指派、技能路由及响应数据返回。

> 💡 **前置要求**：需运行 Freya 智能体服务（支持以 Home Assistant 应用或独立外部服务形式运行）。

### ✨ 核心特性

- 🗣️ **原生 Assist 对话代理**：在 **设置 -> 语音助手** 中即可直接将 Freya 选定为默认助手。
- 🛠️ **`freya.chat` 服务/动作**：
  - `content`：用户提问文本。
  - `session_id`：可选会话标识，用于多轮上下文连续追踪。
  - `attachments`：可选附件列表，支持公网 URL 或 Home Assistant 本地文件路径（如 `/config/www/snapshot.jpg`）。
  - `toolboxes`：可选工具箱列表（如 `["homeassistant"]`），按需激活工具权限。
  - `skill_id`：可选技能标识，直接命中指定任务技能。
  - **响应数据**：支持在自动化中通过 `response_variable` 接收智能体文本回复（通过 `.text` 获取）。

### 安装与配置

#### 第一步：安装集成 (HACS)

[![在 Marketplace 中打开此存储库](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=eoasmxd&repository=ha-integration-freya)

1. 点击上方徽章直接在 Home Assistant 中打开，或前往 **HACS -> 集成** 搜索 **Freya**。
2. 点击 **下载**，下载完成后**重启 Home Assistant**。

#### 第二步：运行 Freya 服务端

Freya 集成需与 Freya 智能体服务协同工作，支持以下任一方式运行：

- **方式 A：通过 Home Assistant 应用运行（推荐）**

  [![在 Home Assistant 中添加此仓库](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Feoasmxd%2Fha-addons)

  点击上方徽章添加官方仓库，安装并启动 **Freya** 应用。
- **方式 B：外部独立 / Docker 部署**
  参考 [Freya 核心项目文档](https://github.com/eoasmxd/freya) 在外部服务器或容器中运行 Freya 服务。

#### 第三步：添加并启用集成

1. 前往 **设置 -> 设备与服务 -> 添加集成**，搜索并选择 **Freya AI Agent**。
2. 根据向导完成连接：
   - **应用部署**：向导会自动识别本地应用并完成连接；
   - **独立部署**：按提示输入服务地址（如 `http://192.168.1.100:3000`）及访问密码。

### 服务调用示例

```yaml
action: freya.chat
data:
  content: "帮我总结一下今天各个房间的温度情况"
  session_id: "temperature-check"
  toolboxes:
    - homeassistant
response_variable: agent_reply
# 后续步骤中可通过变量获取回复文本：{{ agent_reply.text }}
```

---

## 相关链接 / Links

- Core Agent Runtime / 核心智能体底座：[eoasmxd/freya](https://github.com/eoasmxd/freya)
- Official App Repository / 官方应用仓库：[eoasmxd/ha-addons](https://github.com/eoasmxd/ha-addons)
- Issues & Feedback / 问题反馈：[GitHub Issues](https://github.com/eoasmxd/ha-integration-freya/issues)
