# eBay Listing Application

This application allows you to upload images of clothing, have them analysed by
OpenAI’s vision models to generate a title, description, item specifics and a
suggested price, and then automatically create draft listings on eBay via
their Sell Inventory API.

## Features

* Web‐based interface for uploading images (drag‐and‐drop supported).
* Uses OpenAI’s `gpt-4o` model to analyse images and extract structured
  attributes (e.g. garment type, colour, size, target gender, vibe).
* Generates a descriptive title, detailed description and recommended price.
* Integrates with eBay’s Inventory API to:
  * Create or update inventory items (one per unique SKU).
  * Create offers referencing the inventory item with correct marketplace,
    category, pricing and policies.
  * Publish the offer to create a draft listing ready for review and
    activation on eBay.

## Requirements

* Python 3.9+
* An [OpenAI API key](https://platform.openai.com/account/api-keys).
* An eBay developer account with access to the Sell Inventory API.
* OAuth user access token with the following scopes:
  * `https://api.ebay.com/oauth/api_scope/sell.inventory`
  * `https://api.ebay.com/oauth/api_scope/sell.account`
  * `https://api.ebay.com/oauth/api_scope/sell.fulfillment`
* Active listing policies on your eBay seller account (payment, return and
  shipping/fulfilment policies) and an inventory location.

## Setup

1. **Clone this repository or copy the folder** on your machine.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set environment variables**. Create a `.env` file in the project root
   containing the following keys (replace the values with your own):

   ```env
   OPENAI_API_KEY=sk-...

   # eBay API credentials and configuration
   EBAY_ACCESS_TOKEN=<your OAuth user access token>
   EBAY_MARKETPLACE_ID=EBAY_GB          # or EBAY_US, EBAY_DE, etc.
   EBAY_LOCATION_KEY=<your location key> # previously created via createInventoryLocation
   EBAY_PAYMENT_POLICY_ID=<payment policy ID>
   EBAY_RETURN_POLICY_ID=<return policy ID>
   EBAY_FULFILLMENT_POLICY_ID=<fulfilment (shipping) policy ID>
   EBAY_CATEGORY_ID=<default category ID, e.g. 11450 for Clothing>
   DEFAULT_CURRENCY=GBP
   ```

   You can retrieve your listing policy IDs from the eBay Seller Hub or via the
   Sell Account API.  The `EBAY_LOCATION_KEY` refers to a seller inventory
   location created via the `createInventoryLocation` call; it defines where
   items are shipped from.

4. Run the application:

   ```bash
   flask --app main run --debug
   ```

5. Navigate to `http://127.0.0.1:5000` in your browser, upload a clothing
   image and follow the instructions.  The app will display the AI‐generated
   listing details and, if the eBay API calls succeed, will show the offer and
   item IDs returned by eBay.

## Caveats and Notes

* This application produces draft listings; it does **not** automatically
  activate your listing on eBay.  After reviewing the generated offer
  details, you can log in to eBay and finalise the listing before it goes
  live.
* eBay’s policy IDs, marketplace ID and location key must be valid for
  your seller account.  Listing creation will fail if these identifiers
  are incorrect.
* Pricing suggestions are heuristic; always review and adjust the price
  before publishing.
* For security reasons the application does not store your eBay access
  token.  When the server restarts you must ensure that the
  `EBAY_ACCESS_TOKEN` environment variable is up to date.

## File Overview

* `main.py` – Flask application defining routes and integration logic.
* `templates/index.html` – HTML form for uploading images and displaying
  results.
* `requirements.txt` – Python dependencies.
* `.env.example` – Sample environment configuration file (copy to `.env`).

## Licence

This project is provided as is, without warranty of any kind.  Use it at
your own risk.  You are responsible for complying with eBay’s developer
terms and conditions and all applicable laws.