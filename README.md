# Freya AI Agent Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![Home Assistant Version](https://img.shields.io/badge/Home%20Assistant-2026.2.0%2B-blue.svg)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/eoasmxd/ha-integration-freya)](https://github.com/eoasmxd/ha-integration-freya/releases)

Home Assistant integration for [Freya](https://github.com/eoasmxd/freya) — a lightweight microkernel AI agent system.
[Freya](https://github.com/eoasmxd/freya) 微内核智能体 · Home Assistant 原生集成。

---

### Overview

This custom integration bridges Home Assistant with the **Freya AI Agent**:
- **Conversation Assistant**: Acts as a native `conversation` agent for Home Assistant Assist (voice & text chat).
- **Automation Action (`freya.chat`)**: Enables calling the agent from scripts and automations with support for multi-turn sessions, dynamic toolbox activation, skill routing, and response capture.

> 💡 **Prerequisite**: The official [Freya App](https://github.com/eoasmxd/ha-addons) must be installed and running in Home Assistant.

### ✨ Features

- 🗣️ **Native Assist Conversation Agent**: Select Freya directly in **Settings -> Voice assistants** to chat with your configured LLM agent.
- 🛠️ **`freya.chat` Action / Service**:
  - `content`: Message payload.
  - `session_id`: Multi-turn context continuity (optional).
  - `attachments`: Optional list/string of attachments (supports web URLs or local paths like `/config/www/snapshot.jpg`).
  - `toolboxes`: Pass allowed toolbox IDs (e.g. `["homeassistant"]`).
  - `skill_id`: Prioritize or trigger dedicated skills.
  - `response`: Returns full agent response data for automations.
- 🔍 **App Status Detection & Wizard**: Automatically detects the local Freya App status and guides you through setup seamlessly.

### Installation

#### Method 1: Automatic Deployment via Freya App (Recommended)

1. Add the official repository and install the [Freya App](https://github.com/eoasmxd/ha-addons):
   [![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Feoasmxd%2Fha-addons)
2. The app automatically deploys the integration into your `custom_components/freya` directory upon startup.
3. Restart Home Assistant to load the integration.

#### Method 2: Via HACS (Custom Repository)

1. In Home Assistant, open **HACS -> Integrations**.
2. Click the three dots menu (top right) and select **Custom repositories**.
3. Add repository URL: `https://github.com/eoasmxd/ha-integration-freya` with category `Integration`.
4. Click **Download**, then restart Home Assistant.

#### Method 3: Manual Installation

1. Download the latest release archive from [Releases](https://github.com/eoasmxd/ha-integration-freya/releases).
2. Extract the `custom_components/freya` folder into your Home Assistant `<config>/custom_components/freya`.
3. Restart Home Assistant.

### Configuration

1. In Home Assistant, go to **Settings -> Devices & services -> Add integration**.
2. Search for **Freya AI Agent**.
3. The wizard will automatically check the Freya App status:
   - If the app is running, it connects automatically.
   - If the app is not installed or stopped, the wizard guides you to add repository & install, or start it directly.

### Service Usage Example

```yaml
action: freya.chat
data:
  content: "Summarize the energy usage today"
  session_id: "daily-energy-summary"
  toolboxes:
    - homeassistant
response_variable: agent_reply
```

---

### 概述

本集成是将 **Freya 微内核智能体系统** 接入 Home Assistant 的原生桥梁：
- **对话代理助手**：作为原生 `conversation` 平台实体，可直接设为 Assist 对话助手（支持语音与文字聊天）。
- **自动化动作 (`freya.chat`)**：在自动化、脚本中直接调度智能体，支持多轮会话记忆、工具箱动态指派、技能路由及响应数据返回。

> 💡 **前置要求**：需在 Home Assistant 中安装并运行官方 [Freya 应用](https://github.com/eoasmxd/ha-addons)。

### ✨ 核心特性

- 🗣️ **原生 Assist 对话代理**：在 **设置 -> 语音助手** 中即可直接将 Freya 选定为默认助手。
- 🛠️ **`freya.chat` 服务/动作**：
  - `content`：用户提问文本。
  - `session_id`：可选会话标识，用于多轮上下文连续追踪。
  - `attachments`：可选附件列表，支持公网 URL 或 Home Assistant 本地文件路径（如 `/config/www/snapshot.jpg`）。
  - `toolboxes`：可选工具箱列表（如 `["homeassistant"]`），按需激活工具权限。
  - `skill_id`：可选技能标识，直接命中指定任务技能。
  - `response`：支持在自动化中接收智能体的结构化返回结果。
- 🔍 **应用状态检测与引导**：自动检测本地 Freya 应用运行状态，并在未安装或未启动时提供无缝引导。

### 安装方法

#### 方式一：通过 Freya 应用自动部署（首推 / 推荐）

1. 将官方应用仓库添加至 Home Assistant 并安装 [Freya 应用](https://github.com/eoasmxd/ha-addons)：
   [![在 Home Assistant 中添加此仓库](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Feoasmxd%2Fha-addons)
2. 应用在启动时会自动将集成部署至 `custom_components/freya` 目录。
3. 重启 Home Assistant 即可完成集成加载。

#### 方式二：通过 HACS 安装（自定义存储库）

1. 在 Home Assistant 中打开 **HACS -> 集成**。
2. 点击右上角菜单（三个点），选择 **自定义存储库**。
3. 填入仓库地址：`https://github.com/eoasmxd/ha-integration-freya`，类型选择 **集成 (Integration)**。
4. 点击 **下载** 并重启 Home Assistant。

#### 方式三：手动下载安装

1. 从 [Releases 页面](https://github.com/eoasmxd/ha-integration-freya/releases) 下载最新发行版压缩包。
2. 将其中的 `custom_components/freya` 目录复制至 Home Assistant 配置目录下的 `custom_components/freya`。
3. 重启 Home Assistant。

### 配置指南

1. 打开 Home Assistant，进入 **设置 -> 设备与服务 -> 添加集成**。
2. 搜索并选择 **Freya AI Agent**。
3. 向导会自动检测本地 Freya 应用的状态：
   - 若应用已运行，将自动完成连接与配置；
   - 若尚未安装或未启动，向导将直接引导你添加仓库安装或一键启动应用。

### 服务调用示例

```yaml
action: freya.chat
data:
  content: "帮我总结一下今天各个房间的温度情况"
  session_id: "temperature-check"
  toolboxes:
    - homeassistant
response_variable: agent_reply
```

---

## 相关链接 / Links

- Core Agent Runtime / 核心智能体底座：[eoasmxd/freya](https://github.com/eoasmxd/freya)
- Official App Repository / 官方应用仓库：[eoasmxd/ha-addons](https://github.com/eoasmxd/ha-addons)
- Issues & Feedback / 问题反馈：[GitHub Issues](https://github.com/eoasmxd/ha-integration-freya/issues)
