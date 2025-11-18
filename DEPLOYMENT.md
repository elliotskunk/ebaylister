# 🚀 Deployment Guide

This app is **platform-agnostic** and can be deployed to any hosting service that supports Python/Flask.

## 📦 What We Added for Deployment

- **Procfile** - Tells platforms how to run the app (Railway, Render, Heroku)
- **gunicorn** - Production-ready web server (in requirements.txt)
- **railway.toml** - Railway-specific config (ignored by other platforms)

**No changes to your main code!** You can switch platforms anytime.

---

## 🚂 Option 1: Railway (Recommended)

**Pros:** No sleep, simple setup, $5/month free credit

### Step-by-Step:

1. **Push to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Add deployment files"
   git push
   ```

2. **Sign up at Railway**
   - Go to https://railway.app
   - Sign in with GitHub

3. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `ebaylister` repository

4. **Add Environment Variables**
   - In Railway dashboard, go to your project
   - Click "Variables" tab
   - Add ALL variables from your `.env` file:
     ```
     EBAY_CLIENT_ID=...
     EBAY_CLIENT_SECRET=...
     EBAY_REFRESH_TOKEN=...
     EBAY_PAYMENT_POLICY_ID=...
     EBAY_RETURN_POLICY_ID=...
     EBAY_FULFILLMENT_POLICY_ID=...
     EBAY_MERCHANT_LOCATION_KEY=...
     OPENAI_API_KEY=...
     OPENAI_MODEL=gpt-4o-mini
     DEFAULT_CATEGORY_ID=11450
     FORCE_DRAFTS=true
     FLASK_DEBUG=false
     PORT=5001
     ```

5. **Deploy**
   - Railway auto-deploys on push
   - Wait 2-3 minutes
   - Click "Generate Domain" to get your public URL
   - Example: `https://ebaylister-production.up.railway.app`

6. **Done!** Access from your phone anywhere.

---

## 🎨 Option 2: Render

**Pros:** Completely free tier (with sleep), $7/month for always-on

### Step-by-Step:

1. **Push to GitHub** (same as above)

2. **Sign up at Render**
   - Go to https://render.com
   - Sign in with GitHub

3. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Select `ebaylister`

4. **Configure Service**
   - Name: `ebaylister`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - Instance Type: Free (or Starter for $7/month)

5. **Add Environment Variables**
   - In "Environment" section
   - Add all variables from your `.env` file (same as Railway)

6. **Deploy**
   - Click "Create Web Service"
   - Wait 3-5 minutes
   - Your URL: `https://ebaylister.onrender.com`

7. **Note:** Free tier sleeps after 15 min inactivity (takes 30-60s to wake up)

---

## 🐍 Option 3: PythonAnywhere

**Pros:** Python-specific, free tier, no sleep

### Step-by-Step:

1. **Sign up at PythonAnywhere**
   - Go to https://www.pythonanywhere.com
   - Create free account

2. **Clone Repo**
   - Go to "Consoles" → Start new Bash console
   ```bash
   git clone https://github.com/yourusername/ebaylister.git
   cd ebaylister
   pip install -r requirements.txt
   ```

3. **Create .env file**
   - In Bash console:
   ```bash
   nano .env
   # Paste all your environment variables
   # Save with Ctrl+X, Y, Enter
   ```

4. **Configure Web App**
   - Go to "Web" tab → "Add a new web app"
   - Choose "Manual configuration" → Python 3.10
   - Set source code: `/home/yourusername/ebaylister`
   - Set working directory: `/home/yourusername/ebaylister`
   - Edit WSGI file:
   ```python
   import sys
   path = '/home/yourusername/ebaylister'
   if path not in sys.path:
       sys.path.append(path)

   from main import app as application
   ```

5. **Reload** the web app

6. **Your URL:** `https://yourusername.pythonanywhere.com`

---

## 🔄 Switching Platforms

**Want to move to a different platform?**

1. Your code works on ALL platforms (unchanged)
2. Just follow the new platform's setup steps
3. Copy environment variables
4. Deploy

**No vendor lock-in!**

---

## 🔐 Security Checklist

Before deploying to production:

- [ ] Set `FLASK_DEBUG=false` in environment variables
- [ ] Set `FORCE_DRAFTS=true` (prevents accidental publishing)
- [ ] Never commit `.env` file to GitHub (already in .gitignore)
- [ ] Use strong, unique secrets
- [ ] Consider adding authentication (see AUTHENTICATION.md - coming soon)
- [ ] Monitor your OpenAI API usage (costs money per request)
- [ ] Check eBay API rate limits (5,000 calls/day)

---

## 📱 Using on Your Phone

Once deployed:

1. Open your deployment URL in phone browser
2. Bookmark it for quick access
3. Add to home screen (works like an app!)
   - **iPhone:** Share → Add to Home Screen
   - **Android:** Menu → Add to Home Screen

---

## 🐛 Troubleshooting

### App won't start
- Check logs in your platform's dashboard
- Verify all environment variables are set
- Ensure `OPENAI_API_KEY` is valid

### Image uploads fail
- Check if platform has file size limits
- Verify `MAX_CONTENT_LENGTH` in environment (200MB)

### "Module not found" errors
- Platform didn't install dependencies
- Check build logs
- Verify `requirements.txt` exists

### 500 errors
- Check application logs
- Usually environment variables missing
- Verify eBay tokens are valid

---

## 💰 Cost Estimates

**Railway:**
- $5/month free credit
- ~500 hours uptime = plenty for personal use
- Extra usage: ~$5-10/month

**Render:**
- Free: Unlimited (with sleep)
- Starter: $7/month (no sleep)

**PythonAnywhere:**
- Free: 1 web app, 512MB storage
- Hacker: $5/month (more resources)

**OpenAI API (all platforms):**
- gpt-4o-mini: ~$0.01 per 10 images analyzed
- Budget ~$5-20/month depending on usage

---

## 📊 Platform Comparison

| Feature | Railway | Render | PythonAnywhere |
|---------|---------|--------|----------------|
| Free tier | $5 credit | Yes (with sleep) | Yes |
| Always-on free | ✅ (until credit) | ❌ | ✅ |
| Setup difficulty | ⭐ Easy | ⭐⭐ Medium | ⭐⭐⭐ Complex |
| GitHub auto-deploy | ✅ | ✅ | ❌ |
| Custom domain | ✅ | ✅ | ✅ (paid) |

---

**Need help?** Check the main README.md or check logs in your platform's dashboard.
