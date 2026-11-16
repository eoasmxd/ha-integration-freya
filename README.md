# Freya AI Agent Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![Home Assistant Version](https://img.shields.io/badge/Home%20Assistant-2026.2.0%2B-blue.svg)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/eoasmxd/ha-integration-freya)](https://github.com/eoasmxd/ha-integration-freya/releases)

English | [简体中文](README.zh.md)

Home Assistant integration for [Freya](https://github.com/eoasmxd/freya) — a lightweight microkernel AI agent system.

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

## Links

- Core Agent Runtime: [eoasmxd/freya](https://github.com/eoasmxd/freya)
- Official App Repository: [eoasmxd/ha-addons](https://github.com/eoasmxd/ha-addons)
- Issues & Feedback: [GitHub Issues](https://github.com/eoasmxd/ha-integration-freya/issues)
