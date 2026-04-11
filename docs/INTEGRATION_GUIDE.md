# DreamAgent Integrations Guide

DreamAgent supports a rich ecosystem of external APIs, bots, and OAuth integrations. Because security is our top priority, we provide three distinct mechanisms for injecting credentials into the system without ever hardcoding them into the repository.

---

## 1. Fast API Key Injection (Via Chat)

The easiest way to add an API key (like OpenAI, Stripe, or Tavily) is directly through the Chat Interface! 

DreamAgent features an intelligent `KeyInjector` that watches your messages. Just paste your key into the chat:
> "Hey, my Stripe key is `sk_live_abc123...`"

**How it works:**
1. The backend automatically detects the key signature.
2. It verifies the key against the provider's API.
3. It securely writes it to your local `.env` file and drops it into the system environment memory instantly.
4. It restarts the relevant tools (no server reboot required).

You can also input your Supabase URL, Anthropic, Gemini, Groq, and HuggingFace keys this way.

---

## 2. Advanced OAuth 2.0 (Google, Microsoft, Slack, Notion)

For services requiring explicit user authorization via OAuth, use the **System Configuration** dashboard.

### Connecting Google Services (Gmail, Drive, Calendar, YouTube)
Because Google requires heavily verified Client IDs, we support a "Bring Your Own OAuth" architecture:

1. Go to the [Google Cloud Console](https://console.cloud.google.com).
2. Create an **OAuth 2.0 Client ID** (Web Application).
3. Add `http://localhost:8001/api/v1/oauth/google/callback` as a Redirect URI.
4. Download the `client_secret.json`.
5. Open DreamAgent -> click **Settings** -> **OAuth Apps**.
6. At the top, under **Google Setup**, click **Upload** and select your `client_secret.json`.
7. Once uploaded, your encrypted vault will store it, and the **Connect** buttons for Gmail, Drive, and Calendar will illuminate. Click them to authorize your account!

### Connecting Slack, Notion, or Microsoft
These integrations use simple predefined app scopes. Just click **Connect** in the **OAuth Apps** settings tab to trigger the universal `/api/v1/oauth/{provider}/connect` securely.

---

## 3. Bot Tokens (Telegram, Discord, WhatsApp)

You can launch fully autonomous background worker bots directly from the UI without touching the terminal!

1. Open **Settings** -> **Bot Tokens**.
2. Paste your bot token (e.g. from the Telegram `BotFather`).
3. Click **Save & Start**.
4. The system will launch `telegram_bot.py` or `.discord_bot.py` as an isolated background subprocess. 
5. You can view the live status of the bot processes running locally in the **Task Queue** section on the same page.

---

## Data Security & Privacy

* All active configuration is stored locally in `.env`.
* Bot credentials and advanced OAuth states are securely encrypted and stored locally in `data/integrations.json` and the SQLite `dreamagent.db` vaults.
* **None of this data is ever committed to Version Control.** Our `.gitignore` strictly blocks them.
