# Microsoft OAuth Setup Guide

Follow these steps to connect your Microsoft account to DreamAgent.

## Part 1 — Azure Portal Setup (One-time setup)

1. **Go to Azure Portal**
   - Visit [portal.azure.com](https://portal.azure.com) and log in with your Microsoft account. A free account is sufficient.

2. **Register a New Application**
   - Search for **"App registrations"** in the top search bar.
   - Click the **"New registration"** button at the top left.

3. **Fill in the Registration Form**
   - **Name**: Enter a name (e.g., "DreamAgent").
   - **Supported account types**: Select **"Personal Microsoft accounts only"**.
   - **Redirect URI**: 
     - Select **"Web"** from the dropdown.
     - Enter: `http://localhost:8000/api/oauth/microsoft/callback` (or your production callback URL).
   - Click **"Register"**.

4. **Copy the Application (client) ID**
   - On the app **Overview** page, copy the **"Application (client) ID"**. This is your `CLIENT_ID`.

5. **Create a Client Secret**
   - On the left sidebar, go to **"Certificates & secrets"**.
   - Click **"New client secret"**.
   - Set a description and an expiry (e.g., 24 months).
   - Click **"Add"**.
   - **IMPORTANT**: Copy the secret **Value** immediately. It will be hidden forever once you leave the page!

6. **Add API Permissions**
   - On the left sidebar, go to **"API permissions"**.
   - Click **"Add a permission"**.
   - Select **"Microsoft Graph"** -> **"Delegated permissions"**.
   - Search and add the following permissions:
     - `User.Read`
     - `Mail.Read`
     - `Calendars.Read`
     - `Files.Read`
     - `Team.ReadBasic.All`
     - `offline_access`
   - Click **"Add permissions"**.

## Part 2 — Integration with DreamAgent

7. **Open DreamAgent Settings**
   - Go to the **Settings** page in your DreamAgent UI.
   - Locate the **Microsoft** section.
   - Paste your **Client ID** and **Client Secret**.

8. **Connect Your Account**
   - Click **"Connect Microsoft"**.
   - You will be redirected to the Microsoft login page.
   - Once authorized, you'll be returned to DreamAgent, and the connection is complete!

---
DreamAgent will securely store your credentials in the local database and handle token refresh automatically.
