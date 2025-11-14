# 🚀 Quick Start Guide

Get your eBay Lister app running in 3 minutes!

## Step 1: Add Your OpenAI API Key

Open the `.env` file and add your OpenAI API key:

```bash
nano .env
```

Find this line:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

Replace `your_openai_api_key_here` with your actual OpenAI API key (starts with `sk-`).

**Don't have an OpenAI API key?**
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key and paste it in your `.env` file

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Flask (web framework)
- OpenAI (vision models: gpt-4o-mini, gpt-4o, etc.)
- Pillow (image processing)
- python-dotenv (environment variables)
- requests (HTTP client)

## Step 3: Run the App

```bash
python main.py
```

You should see:
```
============================================================
eBay Lister App Starting
============================================================
Port: 5001
Debug: True
Force Drafts: True
Default Category: 11450
============================================================
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://192.168.x.x:5001
```

## Step 4: Upload Your First Item

1. Open your browser and go to: **http://localhost:5001**
2. Click or drag to upload a product image
3. (Optional) Override title, price, or category
4. Click "🚀 Analyze & Create Draft Listing"
5. Wait 10-30 seconds for the magic to happen!

## What Happens Next?

The app will:
1. ✅ Analyze your image with AI (gpt-4o-mini by default)
2. ✅ Generate an SEO-optimized title
3. ✅ Create a detailed description
4. ✅ Extract item specifics (Brand, Size, Color, etc.)
5. ✅ Suggest a competitive price
6. ✅ Upload image to eBay Picture Service
7. ✅ Auto-select the best category
8. ✅ Create a DRAFT listing on eBay

Your draft listing will be in **eBay Seller Hub** → **Listings** → **Unsold** (Drafts)

## 📱 Use on Mobile

### Same Device
- On your phone, go to: `http://localhost:5001`

### Other Devices on Your Network
1. Find your computer's IP address:
   - **Windows**: `ipconfig` → look for "IPv4 Address"
   - **Mac/Linux**: `ifconfig` or `ip addr` → look for your local IP
   - Usually something like `192.168.1.100`

2. On your phone/tablet, open: `http://YOUR-IP:5001`
   - Example: `http://192.168.1.100:5001`

3. Take a photo or upload from gallery!

## ⚙️ Configuration

All settings are in `.env`:

```env
# Your eBay credentials (already configured)
EBAY_CLIENT_ID=TobiasKu-ellioton-PRD-cd444012e-0af8aae4
EBAY_CLIENT_SECRET=PRD-d444012e2c12-9c50-4384-86c4-37d0
EBAY_REFRESH_TOKEN=v^1.1#...

# Your eBay policies (already configured)
EBAY_PAYMENT_POLICY_ID=272576530014
EBAY_RETURN_POLICY_ID=272576531014
EBAY_FULFILLMENT_POLICY_ID=272578581014
EBAY_MERCHANT_LOCATION_KEY=DERBY1

# Default category for items
DEFAULT_CATEGORY_ID=11450

# ADD YOUR OPENAI KEY HERE!
OPENAI_API_KEY=your_key_here

# AI Model (gpt-4o-mini is cost-effective, gpt-4o for better quality)
OPENAI_MODEL=gpt-4o-mini

# Safety mode (prevents accidental publishing)
FORCE_DRAFTS=true
```

## 🐛 Troubleshooting

### "AI analysis failed"
→ Check your `OPENAI_API_KEY` in `.env`

### "Module not found" errors
→ Run `pip install -r requirements.txt`

### "Port already in use"
→ Change `PORT=5001` in `.env` to another port (e.g., `PORT=5002`)

### Can't access from phone
→ Make sure your computer's firewall allows connections on port 5001

### Image upload fails
→ Make sure image is under 16MB and is a valid image file (JPG, PNG, WEBP)

## 📊 Check Logs

Application logs are in `logs/app.log`:

```bash
tail -f logs/app.log
```

## 🎉 Success!

You're now ready to:
1. Upload product images
2. Get AI-powered listing data
3. Create optimized eBay drafts
4. Review and publish on eBay Seller Hub

**Happy Listing!**

---

Need more details? Check the full **README.md**
