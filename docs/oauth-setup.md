# DreamAgent OAuth Setup Guide

This guide explains how to set up OAuth for the various services supported by DreamAgent.

## Table of Contents
1. [Google OAuth](#google-oauth)
2. [Microsoft OAuth](#microsoft-oauth)
3. [Slack OAuth](#slack-oauth)
4. [Notion OAuth](#notion-oauth)

---

## Google OAuth

1. **Go to Google Cloud Console**
   - Visit [console.cloud.google.com](https://console.cloud.google.com).
2. **Create a Project**
   - Create a new project or select an existing one.
3. **Configure OAuth Consent Screen**
   - APIs & Services -> OAuth consent screen.
   - Choose "External" and follow the prompts.
4. **Create Credentials**
   - APIs & Services -> Credentials -> Create Credentials -> OAuth 2.0 Client ID.
   - **Application type**: Web application.
   - **Name**: DreamAgent.
   - **Authorized redirect URIs**: `http://localhost:8000/api/oauth/google/callback`.
5. **Download credentials.json**
   - Download the JSON file and place it in your DreamAgent project root as `credentials.json`.
6. **Enable APIs**
   - Enable Gmail API, Google Calendar API, Google Drive API, and **YouTube Data API v3** in the Library.

---

## Microsoft OAuth

See the detailed [Microsoft Setup Guide](./microsoft-setup.md) for step-by-step instructions.

---

## Slack OAuth

1. **Go to Slack API**
   - Visit [api.slack.com/apps](https://api.slack.com/apps).
2. **Create a New App**
   - Create from scratch -> Name: "DreamAgent" -> Select Workspace.
3. **Configure Redirect URLs**
   - OAuth & Permissions -> Redirect URLs -> Add New Redirect URL: `http://localhost:8000/api/oauth/slack/callback`.
4. **Add Scopes**
   - Under **Bot Token Scopes**, add:
     - `chat:write`
     - `channels:read`
     - `users:read`
5. **Install App to Workspace**
   - Click "Install to Workspace" and authorize.
6. **Copy Credentials**
   - Basic Information -> App Credentials -> Copy **Client ID** and **Client Secret**.
7. **Paste into DreamAgent Settings**
   - Paste the keys into the Slack section in DreamAgent Settings.

---

## Notion OAuth

1. **Go to Notion Integrations**
   - Visit [notion.so/my-integrations](https://www.notion.so/my-integrations).
2. **Create a New Integration**
   - Click "+ New integration".
   - **Name**: DreamAgent.
   - **Type**: Public (required for OAuth).
3. **Configure Redirect URI**
   - Under "Redirect URIs", add: `http://localhost:8000/api/oauth/notion/callback`.
4. **Copy Credentials**
   - Copy the **Client ID** and **Client Secret**.
5. **Paste into DreamAgent Settings**
   - Paste the keys into the Notion section in DreamAgent Settings.

---
**Note**: All redirect URIs assume you are running DreamAgent locally on port 8000. If you are using a different port or hosting the app, update the URIs accordingly.
