# DreamAgent Integration Guide

> **Everything you need** to connect OAuth providers, bot tokens, and API keys to DreamAgent.

---

## Table of Contents

1. [API Keys (LLM Providers & Services)](#1-api-keys)
2. [Bot Tokens (Telegram, Discord, Slack, WhatsApp)](#2-bot-tokens)
3. [OAuth 2.0 Apps (Google, Microsoft, Slack, Notion)](#3-oauth-apps)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. API Keys

API keys are the simplest form of integration. You can add them in **two ways**:

### Method A — Chat (Recommended)

Just paste your key directly in the DreamAgent chat window. It detects and stores it automatically.

**Examples:**

```
My OpenAI API key is sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
My Tavily key is tvly-dev-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
My Supabase anon key is sb_publishable_xxxxxxxxxxx
```

DreamAgent will reply with a confirmation and verification result.

### Method B — Settings UI

1. Go to **Settings → API Keys**
2. Find the provider row (OpenAI, Anthropic, Groq, Gemini, etc.)
3. Click **Edit / Add**
4. Paste your API key
5. Click **Save**

### Method C — `.env` file (Manual)

Edit the `.env` file in the root of the project:

```env
OPENAI_API_KEY=sk-proj-xxxxx
GEMINI_API_KEY=AIzaSy-xxxxx
GROQ_API_KEY=gsk_xxxxx
CLAUDE_API_KEY=sk-ant-xxxxx
TAVILY_API_KEY=tvly-xxxxx
SUPABASE_ANON_KEY=sb_publishable_xxxxx
SUPABASE_URL=https://your-project.supabase.co
STRIPE_API_KEY=sk_live_xxxxx
AHREFS_API_KEY=xxxxx
```

Then restart the backend server.

---

### Supported API Key Providers

| Provider | Env Variable | Key Format | Where to Get It |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `sk-proj-...` | [platform.openai.com](https://platform.openai.com/api-keys) |
| Anthropic/Claude | `CLAUDE_API_KEY` | `sk-ant-...` | [console.anthropic.com](https://console.anthropic.com/) |
| Google Gemini | `GEMINI_API_KEY` | `AIzaSy...` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Groq | `GROQ_API_KEY` | `gsk_...` | [console.groq.com](https://console.groq.com/keys) |
| HuggingFace | `HUGGINGFACE_API_KEY` | `hf_...` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| OpenRouter | `OPENROUTER_API_KEY` | `sk-or-v1-...` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Tavily Search | `TAVILY_API_KEY` | `tvly-...` | [app.tavily.com](https://app.tavily.com/) |
| Supabase (Anon) | `SUPABASE_ANON_KEY` | `sb_publishable_...` | Supabase Project Settings → API |
| Supabase (Service) | `SUPABASE_SERVICE_KEY` | `eyJ...` | Supabase Project Settings → API |
| Supabase URL | `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Project Settings → API |
| Stripe | `STRIPE_API_KEY` | `sk_live_...` or `sk_test_...` | [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) |
| Ahrefs | `AHREFS_API_KEY` | 32-64 char string | [ahrefs.com/api](https://ahrefs.com/api) |
| Resend (Email) | `RESEND_API_KEY` | `re_...` | [resend.com/api-keys](https://resend.com/api-keys) |

---

## 2. Bot Tokens

### Telegram Bot

**Step 1:** Talk to [@BotFather](https://t.me/BotFather) on Telegram

```
/newbot
```

**Step 2:** Follow the prompts, get your token in the format:
```
1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxx
```

**Step 3:** Add it via chat or Settings → Bot Tokens

**Chat method:**
```
My Telegram bot token is 1234567890:AAHxxxxxxxxxxxxxxxxxx
```

**Settings method:**
1. Settings → **Bot Tokens** tab
2. Find the Telegram row
3. Click **Add Token**
4. Paste the token, click **Save & Start**

**Permissions required:** None — all bots have basic messaging by default.

---

### Discord Bot

**Step 1:** Go to [discord.com/developers/applications](https://discord.com/developers/applications)

**Step 2:** Create New Application → Bot → Add Bot

**Step 3:** Copy the **Bot Token** (reset if needed)

**Step 4:** Under **Privileged Gateway Intents**, enable:
- ✅ `MESSAGE CONTENT INTENT`
- ✅ `SERVER MEMBERS INTENT`

**Step 5:** Add to DreamAgent:
```
My Discord bot token is MTxxxxxxxxxxxxxxxxxx.xxxxxxx.xxxxxxxxxxxxxxxxx
```

Or in **Settings → Bot Tokens → Discord**.

**Invite URL (replace YOUR_CLIENT_ID):**
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=8
```

---

### Slack Bot

**Step 1:** Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App

**Step 2:** From Scratch → Pick a workspace

**Step 3:** Go to **OAuth & Permissions**, add these **Bot Token Scopes**:
```
channels:read, channels:history, chat:write, im:read, im:write,
app_mentions:read, groups:read, reactions:write
```

**Step 4:** Click **Install to Workspace** → Copy the `xoxb-...` **Bot User OAuth Token**

**Step 5:** Add to DreamAgent:
```
My Slack bot token is xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### WhatsApp Bot

WhatsApp requires a **Meta Developer Account** and a verified Business.

**Step 1:** Go to [developers.facebook.com](https://developers.facebook.com) → Create App

**Step 2:** Add **WhatsApp** product to the app

**Step 3:** Get your **Access Token** from **WhatsApp → API Setup**

**Step 4:** Add to DreamAgent via Settings → Bot Tokens → WhatsApp

---

## 3. OAuth Apps

OAuth apps allow DreamAgent to **act on your behalf** in services like Gmail, Google Drive, and Microsoft Teams.

---

### Google (Gmail, Drive, Calendar, YouTube)

> **Requires:** Google Cloud Console account (free)

#### Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** → **New Project**
3. Name it `DreamAgent` → **Create**

#### Step 2: Enable Required APIs

In your project, go to **APIs & Services → Enable APIs and Services**. Search for and enable:

- ✅ **Gmail API** — for email read/send
- ✅ **Google Drive API** — for file access
- ✅ **Google Calendar API** — for scheduling
- ✅ **YouTube Data API v3** — for video data

#### Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app** (for local dev)
4. Name it `DreamAgent Local`
5. Click **Create**
6. Click **Download JSON** → saves as `client_secret_xxxx.json`

#### Step 4: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. User type: **External** (or Internal if Workspace)  
3. Fill in App Name, Email
4. Add **Test Users** (your own email while in dev)
5. Add **Scopes:** click "Add or remove scopes"  
   Search and add: `gmail.modify`, `drive`, `calendar`, `youtube.readonly`

#### Step 5: Upload to DreamAgent

1. Open DreamAgent → **Settings → OAuth Apps**
2. Under **Google Setup (Advanced)**, click **Choose File**
3. Select your downloaded `client_secret_xxxxx.json`
4. Click **Upload**

✅ You should see: *"Custom Google OAuth Active"*

Now click **Connect** on Gmail, Drive, Calendar, or YouTube to authorize each one.

---

### Microsoft (Teams, Excel)

> **Requires:** Microsoft Azure account (free tier available)

#### Step 1: Register an Azure App

1. Go to [portal.azure.com](https://portal.azure.com) → **Azure Active Directory → App registrations**
2. Click **New registration**
3. Name: `DreamAgent`
4. Redirect URI: `http://localhost:8001/api/v1/oauth/microsoft/callback`
5. Click **Register**

#### Step 2: Get Client ID

On the app overview page, copy the **Application (client) ID** — it's a UUID like:
```
a72b5c3e-1234-5678-abcd-ef0123456789
```

#### Step 3: Create Client Secret

1. **Certificates & secrets → New client secret**
2. Description: `DreamAgent`
3. Expires: Choose a date
4. Click **Add** → **Copy the value immediately** (you can't see it again!)

#### Step 4: Add Permissions

1. **API permissions → Add a permission → Microsoft Graph**
2. Delegated permissions, add:
   - `Mail.Read`, `Mail.Send` (for Teams email)
   - `Files.ReadWrite` (for Excel)
   - `User.Read` (basic profile)
3. Click **Grant admin consent**

#### Step 5: Add to DreamAgent via Chat

```
My Microsoft Client ID is a72b5c3e-1234-5678-abcd-ef0123456789
My Microsoft Client Secret is xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Then go to **Settings → OAuth Apps** and click **Connect** on the Microsoft row.

---

### Slack OAuth (Full OAuth, not just bot)

> For full workspace integration beyond a simple bot token

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → your app
2. **OAuth & Permissions → Redirect URLs:**
   ```
   http://localhost:8001/api/v1/oauth/slack/callback
   ```
3. Go to **Basic Information** → copy:
   - **Client ID** (format: `1234567890.9876543210`)
   - **Client Secret** (32 hex chars)
4. Add via chat:
   ```
   My Slack Client ID is 1234567890.9876543210
   My Slack Client Secret is abcdef1234567890abcdef1234567890
   ```

---

### Notion OAuth

1. Go to [www.notion.so/my-integrations](https://www.notion.so/my-integrations) → **New integration**
2. Name: `DreamAgent`, pick your workspace
3. **Capabilities:** Read content, Update content, Insert content
4. **OAuth Domain & URIs:**  
   Redirect URI: `http://localhost:8001/api/v1/oauth/notion/callback`
5. Click **Submit**
6. Copy:
   - **OAuth client ID** (UUID format)
   - **OAuth client secret** (starts with `secret_`)
7. Add via chat:
   ```
   My Notion Client ID is xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   My Notion Client Secret is secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 4. Environment Variables Reference

Create a `.env` file in the root `DreamAgent/` directory. Copy from `.env.example`:

```env
# ─── LLM Providers (at least 1 required) ────────────────────────
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
CLAUDE_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-v1-...
HUGGINGFACE_API_KEY=hf_...

# ─── Search & Data Tools ─────────────────────────────────────────
TAVILY_API_KEY=tvly-...
AHREFS_API_KEY=...

# ─── Bot Tokens ───────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=1234567890:AAH...
DISCORD_TOKEN=MTx...
SLACK_BOT_TOKEN=xoxb-...

# ─── Payments ─────────────────────────────────────────────────────
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ─── Database & Storage ───────────────────────────────────────────
# SQLite is used by default. For production:
# DATABASE_URL=postgresql://user:pass@localhost:5432/dreamagent
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_KEY=eyJ...

# ─── OAuth Apps ───────────────────────────────────────────────────
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=

# ─── Infrastructure ───────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
BACKEND_URL=http://localhost:8001
FRONTEND_DOMAIN=http://localhost:5000

# ─── Security ─────────────────────────────────────────────────────
# Auto-generated on first run. DO NOT share.
ENCRYPTION_KEY=

# ─── Feature Flags ────────────────────────────────────────────────
TOOL_PYTHON_ENABLED=true
TOOL_JS_ENABLED=true
TOOL_TERMINAL_ENABLED=true
TOOL_FILESYSTEM_ENABLED=true
TOOL_BROWSER_ENABLED=false
TOOL_TAVILY_ENABLED=true
TOOL_GOOGLE_SEARCH_ENABLED=false
TOOL_CALCULATOR_ENABLED=true
TOOL_INTELLIGENCE_ENABLED=true
MAX_STEPS=10
```

---

## 5. Troubleshooting

### "Connected" shows but doesn't work

1. The OAuth token may have expired. Click **Disconnect** then **Connect** again.
2. Make sure the **backend is running** at `http://localhost:8001`
3. Check **Settings → Task Queue** for errors

### Bot says "Not running"

1. Go to **Settings → Bot Tokens**
2. Click **Start** next to the bot
3. Check system runs `python telegram_bot.py` in the Task Queue

### Google Upload fails

- Ensure the JSON file is the correct `client_secret_xxxxx.json` from Google Cloud Console
- File must contain `client_id` and `client_secret` fields
- Only OAuth 2.0 credentials are supported (not service accounts for basic users)

### API key shows "already set"

- The key you pasted is identical to what's already stored
- To update it, go to **Settings → API Keys** and click **Edit**

### Why isn't my key being detected from chat?

- Ensure the key format matches exactly (no extra spaces or characters)
- For Microsoft/Slack/Notion OAuth, you **must** mention the service name too:  
  ✅ `"My Microsoft Client ID is xxxx"`  
  ❌ `"Client ID: xxxx"` (won't match without the service name)

---

*Documentation last updated: April 2026*
