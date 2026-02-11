# How to Install AI Scrum Bot in Teams

1.  **Update Manifest**:
    *   Open `manifest.json`.
    *   Replace `{{MICROSOFT_APP_ID}}` with your actual Azure Bot ID (from `.env`).
    *   Replace `{{BOT_DOMAIN}}` with your bot's domain (e.g., `scrum-bot.herokuapp.com` or `ngrok-id.ngrok.io`). **Do not include https://**.

2.  **Add Icons**:
    *   You need two icons in this folder:
        *   `color.png` (192x192 pixels)
        *   `outline.png` (32x32 pixels, transparent white)
    *   *(I will generate placeholders for you shortly)*

3.  **Create Package**:
    *   Select `manifest.json`, `color.png`, and `outline.png`.
    *   Right-click -> Send to -> Compressed (zipped) folder.
    *   Name it `scrum-bot.zip`.

4.  **Upload to Teams**:
    *   Opens **Microsoft Teams**.
    *   Go to **Apps** (bottom left).
    *   Click **Manage your apps**.
    *   Select **Submit an app to your org** (or **Upload a custom app** depending on your permissions).
    *   Upload `scrum-bot.zip`.
    *   Click **Add** to install it for yourself or a team.
