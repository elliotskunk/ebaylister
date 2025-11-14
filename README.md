# 🚀 eBay Lister App

**AI-Powered eBay Listing Creator**

Upload product images, let AI analyze them with OpenAI vision models, and automatically create SEO-optimized eBay draft listings with just a few clicks!

## ✨ Features

- 📸 **Image Upload** - Drag & drop or click to upload product images
- 🤖 **AI Analysis** - OpenAI vision models (gpt-4o-mini) analyze your images and extract:
  - SEO-optimized titles (Cassini-optimized)
  - Detailed descriptions
  - Item specifics/aspects
  - Suggested pricing
  - Condition assessment
- 🏷️ **Auto-Categorization** - Automatically selects the best eBay category from 15,989 UK categories
- 📤 **eBay Picture Service (EPS)** - Uploads images directly to eBay's servers
- 📝 **Draft Listings** - Creates draft listings on eBay (ready to publish when you're ready)
- 📱 **Mobile-Friendly** - Responsive design works great on phones, tablets, and desktops
- 🔒 **Safe** - Draft-only mode prevents accidental publishing

## 🛠️ Technology Stack

- **Backend**: Python 3.9+ with Flask
- **AI**: OpenAI vision models (gpt-4o-mini by default, configurable)
- **eBay API**: Inventory API v1 (modern REST API) + Trading API (for EPS)
- **Authentication**: OAuth 2.0 with automatic token refresh
- **Frontend**: Vanilla JavaScript with modern responsive CSS

## 📋 Prerequisites

1. **Python 3.9+**
2. **eBay Developer Account** with:
   - Production API credentials (Client ID, Client Secret)
   - OAuth User Refresh Token
   - Business policies set up (Payment, Return, Fulfillment)
   - Merchant location configured
3. **OpenAI API Key** (for vision-enabled models)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file is already created with your eBay credentials. **Update the OpenAI API key**:

```env
# OpenAI Configuration (UPDATE THIS!)
OPENAI_API_KEY=your_actual_openai_api_key_here
```

All other eBay credentials are already configured.

### 3. Run the App

```bash
python main.py
```

The app will start on `http://localhost:5001`

### 4. Upload and List!

1. Open `http://localhost:5001` in your browser
2. Upload a product image
3. Optionally override title, price, or category
4. Click "Analyze & Create Draft Listing"
5. Wait for AI to analyze and create the listing
6. Check your eBay Seller Hub for the draft listing!

## 📁 Project Structure

```
ebaylister/
├── main.py                      # Main Flask application
├── auth.py                      # OAuth token management with auto-refresh
├── inventory_flow.py            # eBay Inventory API integration
├── ebay_picture_service.py      # EPS image upload
├── ai_analyzer.py               # OpenAI vision analysis with Cassini SEO
├── category_matcher.py          # Category auto-selection
├── categories.json              # 15,989 eBay UK categories
├── requirements.txt             # Python dependencies
├── .env                         # Configuration (credentials)
├── templates/
│   └── upload.html             # Mobile-friendly upload interface
├── logs/
│   └── app.log                 # Application logs
└── legacy/                     # Old Trading API implementation
```

## 🔌 API Endpoints

### Web Interface

- `GET /` - Upload form (mobile-friendly UI)
- `GET /health` - Health check

### API Endpoints

#### Upload & Create Listing

```http
POST /upload
Content-Type: multipart/form-data

Fields:
- image: Image file (required)
- title_override: Override AI title (optional)
- price_override: Override AI price (optional)
- category_id: Override category (optional)

Response: JSON with listing details and offer ID
```

#### Create Listing (Manual Data)

```http
POST /api/create
Content-Type: application/json

{
  "title": "Item Title",
  "description": "Description",
  "price": 19.99,
  "image_url": "https://ebay-eps-url",
  "category_id": "12345",
  "aspects": {"Brand": ["Nike"], "Size": ["L"]},
  "sku": "CUSTOM-SKU"
}
```

#### Analyze Only (No Listing)

```http
POST /api/analyze
Content-Type: multipart/form-data

Fields:
- image: Image file

Response: JSON with AI analysis only
```

#### Publish Offer (Disabled by Default)

```http
POST /api/publish/{offer_id}

Note: Only works when FORCE_DRAFTS=false
```

## 🎯 How It Works

1. **Image Upload** → User uploads product image via web interface or API
2. **Image Processing** → Image is validated, resized if needed, and converted to JPEG
3. **AI Analysis** → OpenAI vision model analyzes the image and generates:
   - SEO-optimized title (Cassini algorithm)
   - Detailed description
   - Item specifics (Brand, Size, Color, Material, etc.)
   - Suggested price
   - Condition assessment
4. **Image Upload to EPS** → Image is uploaded to eBay Picture Service
5. **Category Selection** → Best category is auto-selected from 15,989 categories
6. **Inventory Item Creation** → Creates inventory item with eBay Inventory API
7. **Offer Creation** → Creates draft offer (listing) on eBay
8. **Done!** → Draft listing is ready in eBay Seller Hub

## 🔐 Security & Safety

- ✅ **Draft Mode** - `FORCE_DRAFTS=true` prevents accidental publishing
- ✅ **OAuth 2.0** - Secure authentication with automatic token refresh
- ✅ **Secrets Management** - All credentials in `.env` (gitignored)
- ✅ **Input Validation** - Images and data validated before processing
- ✅ **Error Handling** - Comprehensive error handling and logging

## 📊 Cassini SEO Optimization

The AI is specifically trained to optimize for eBay's Cassini search algorithm:

- **Front-loaded titles** - Most important keywords first
- **Rich item specifics** - Maximum relevant attributes
- **Keyword-rich descriptions** - Natural language with search terms
- **Accurate categorization** - Proper category = better visibility
- **Condition accuracy** - Honest condition descriptions

## 🐛 Troubleshooting

### Common Issues

**1. "AI analysis failed" error**
- Check your `OPENAI_API_KEY` is set correctly in `.env`
- Ensure you have access to vision-enabled models (gpt-4o-mini, gpt-4o, etc.)
- Check OpenAI API quotas/billing
- Verify `OPENAI_MODEL` is set to a valid vision model in `.env`

**2. "EPS upload failed" error**
- Verify eBay OAuth tokens are valid
- Check image file is valid (JPG, PNG)
- Ensure image is under 16MB

**3. "Category selection failed" error**
- Set `DEFAULT_CATEGORY_ID` in `.env` as fallback
- Ensure `categories.json` exists
- Check category ID is a leaf category

**4. "Missing required policy env" error**
- Verify all policy IDs are set in `.env`
- Create business policies in eBay Seller Hub if needed

### Checking Logs

Application logs are saved to `logs/app.log`:

```bash
tail -f logs/app.log
```

## 📱 Mobile Use

The app is fully mobile-responsive! You can:

1. Access from any device on your local network
2. Use your phone's camera to take photos
3. Upload and create listings on the go

To access from other devices on your network:
1. Find your computer's local IP (e.g., `192.168.1.100`)
2. The app is already configured to listen on all interfaces (`0.0.0.0`)
3. Open `http://192.168.1.100:5001` on your phone/tablet

## 🚀 Deployment

For production deployment:

1. **Change secrets** in `.env`
2. **Set FLASK_DEBUG=false**
3. **Use a production WSGI server** (gunicorn, uWSGI)
4. **Enable HTTPS**
5. **Configure firewall** appropriately

Example with gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 main:app
```

## 📝 Important Notes

- **Draft Listings**: All listings are created as drafts by default. Review them in eBay Seller Hub before publishing.
- **API Limits**: Be aware of eBay API rate limits (5,000 calls/day for production)
- **OpenAI Costs**: Vision API calls cost money (gpt-4o-mini is 60x cheaper than gpt-4o). Monitor usage at platform.openai.com
- **Categories**: The `categories.json` file contains eBay UK categories. Update for other marketplaces.
- **OAuth Tokens**: The app automatically refreshes access tokens using your refresh token

## 📄 License

Private project - All rights reserved

## 🙏 Acknowledgments

- eBay Developer Program
- OpenAI Vision Models (gpt-4o-mini, gpt-4o)
- Flask Framework

---

**Happy Listing!** 🎉

For questions or issues, check the logs at `logs/app.log` or refer to eBay Developer documentation.
