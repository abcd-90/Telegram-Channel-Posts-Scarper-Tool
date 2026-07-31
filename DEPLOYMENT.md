# 🌐 24/7 Cloud Deployment Guide (Free 24/7 Running)

This Telegram Cloner requires a continuous background MTProto socket connection, so traditional Serverless hosts like **Vercel** will time out after 10-60 seconds.

Below are the **Best 100% Free 24/7 Cloud Hosting Options** where you can deploy this bot so it runs continuously even when your laptop/PC is turned off.

---

## 🏆 Option 1: Koyeb (100% Free - Recommended)
**Koyeb** offers 1 Free Micro Instance that runs Docker containers 24/7 without sleeping.

### Steps:
1. Create a GitHub Repository and push this project code:
   ```bash
   git init
   git add .
   git commit -m "Deploy 24/7 Cloner"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/telegram-cloner.parser.git
   git push -u origin main
   ```
2. Sign up at [Koyeb.com](https://www.koyeb.com/).
3. Click **Create App** -> Select **GitHub**.
4. Choose your repository and select **Dockerfile**.
5. Add Environment Variables in Koyeb Web Interface:
   - `TELEGRAM_API_ID` = `37604254`
   - `TELEGRAM_API_HASH` = `a3e5e613247c608bb81a3000c9bb9785`
6. Click **Deploy**! Koyeb will run your bot 24/7 uninterrupted.

---

## 🏆 Option 2: Render.com (Background Worker)
**Render** allows running background workers that execute Python scripts continuously.

### Steps:
1. Sign up at [Render.com](https://render.com/).
2. Click **New +** -> Select **Background Worker**.
3. Connect your GitHub Repo.
4. Set Build Command: `pip install -r requirements.txt`
5. Set Start Command: `python src/run_userbot_cloner.py`
6. Click **Create Background Worker**!

---

## 🏆 Option 3: Railway.app
**Railway** gives $5 free monthly credits which runs small Python bots 24/7.

1. Sign up at [Railway.app](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Add your `user_session.session` file or login credentials in env.
4. Click **Deploy**.
