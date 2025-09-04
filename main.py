import os
import base64
import json
import uuid
from datetime import datetime

from flask import Flask, request, render_template, jsonify, redirect, url_for
from dotenv import load_dotenv
import openai
import requests

# Load environment variables from .env if present
load_dotenv()

app = Flask(__name__)

# Initialise OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants for eBay API
EBAY_ENDPOINT = "https://api.ebay.com"  # change to https://api.sandbox.ebay.com for sandbox
MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "GBP")


def normalize_specifics(specifics: dict) -> dict:
    """Ensure aspects are shaped as {name: [values]} and strip empties."""
    if not specifics:
        return {}
    out = {}
    for k, v in specifics.items():
        if v is None:
            continue
        if isinstance(v, str):
            val = v.strip()
            if val:
                out[k] = [val]
        elif isinstance(v, (int, float)):
            out[k] = [str(v)]
        elif isinstance(v, list):
            vals = [str(x).strip() for x in v if str(x).strip()]
            if vals:
                out[k] = vals
        else:
            # last resort
            s = str(v).strip()
            if s:
                out[k] = [s]
    return out


def require_keys(obj: dict, keys: list[str]) -> None:
    missing = [k for k in keys if k not in obj or obj[k] in (None, "", [])]
    if missing:
        raise RuntimeError(f"Model response missing keys: {', '.join(missing)}")

def get_env(key: str, required: bool = True) -> str:
    """Helper to read environment variables and optionally enforce presence."""
    value = os.getenv(key)
    if required and not value:
        raise RuntimeError(f"Missing environment variable: {key}")
    return value


def analyse_image(image_bytes: bytes) -> dict:
    """Send the image to OpenAI's vision model and parse structured JSON output.

    Returns a dictionary with keys: title, description, specifics (dict), price (float).
    """
    # Encode to base64 for data URI
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{encoded}"

    # Compose prompt for the model
    system_prompt = (
        "You are an expert vintage clothing seller. "
        "Based on the user's uploaded image, extract detailed information about the garment, "
        "including the type of clothing (e.g. jacket, dress, trousers), the intended wearer "
        "(men, women, unisex, kids), the primary colour(s), the size if visible, approximate era or style, "
        "and overall vibe. Suggest a market‐appropriate price in GBP for a used item in good condition. "
        "Respond in valid JSON with the following keys: title (string), description (string, rich and appealing), "
        "specifics (an object mapping eBay item specific names to their values), and price (number)."
    )

    user_content = [
        {"type": "text", "text": "Analyse this clothing item and return structured JSON as specified."},
        {"type": "image_url", "image_url": {"url": data_uri}},
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.6,
            max_tokens=600,
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")

    # Extract JSON from the response text
    content = response.choices[0].message.content
    try:
        # Attempt to find JSON object in the response
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        parsed = json.loads(json_str)
    except Exception as e:
        raise RuntimeError(f"Failed to parse JSON from model response: {e}\nResponse: {content}")

    # Normalise fields
    if not isinstance(parsed, dict):
        raise RuntimeError("Model returned invalid JSON structure")

    require_keys(parsed, ["title", "description", "specifics", "price"])

    # truncate title to eBay 80 chars
    parsed["title"] = str(parsed["title"])[:80]
    # coerce price
    try:
        parsed["price"] = round(float(parsed["price"]), 2)
    except Exception:
        parsed["price"] = 9.99

    # normalise specifics to list[str]
    parsed["specifics"] = normalize_specifics(parsed.get("specifics", {}))
    return parsed


def create_inventory_item(token: str, sku: str, specifics: dict, description: str) -> dict:
    """Create or replace an eBay inventory item for the given SKU.

    specifics: mapping of item specific names to values.
    description: full description text (not used here – description is set at offer level).
    """
    url = f"{EBAY_ENDPOINT}/sell/inventory/v1/inventory_item/{sku}"
    # Convert item specifics to required format
    name_value_list = [
        {"name": name, "value": value} for name, value in specifics.items()
    ]
    payload = {
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        },
        "product": {
            "aspects": specifics,
            # Additional product details could be added here
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }
    resp = requests.put(url, json=payload, headers=headers)
    if not resp.ok:
        raise RuntimeError(f"eBay inventory item error: {resp.status_code} {resp.text}")
    return resp.json()


def create_offer(token: str, sku: str, title: str, description: str, price: float) -> dict:
    """Create an eBay offer for the given inventory item (SKU)."""
    payment_policy_id = get_env("EBAY_PAYMENT_POLICY_ID")
    return_policy_id = get_env("EBAY_RETURN_POLICY_ID")
    fulfilment_policy_id = get_env("EBAY_FULFILLMENT_POLICY_ID")
    location_key = get_env("EBAY_LOCATION_KEY")
    category_id = get_env("EBAY_CATEGORY_ID")

    url = f"{EBAY_ENDPOINT}/sell/inventory/v1/offer"
    payload = {
        "sku": sku,
        "marketplaceId": MARKETPLACE_ID,
        "format": "FIXED_PRICE",
        "listingDescription": description,
        "availableQuantity": 1,
        "pricingSummary": {
            "price": {
                "value": price,
                "currency": DEFAULT_CURRENCY
            }
        },
        "listingPolicies": {
            "paymentPolicyId": payment_policy_id,
            "returnPolicyId": return_policy_id,
            "fulfillmentPolicyId": fulfilment_policy_id
        },
        "categoryId": category_id,
        "inventoryLocationKey": location_key,
        "name": title
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }
    resp = requests.post(url, json=payload, headers=headers)
    if not resp.ok:
        raise RuntimeError(f"eBay create offer error: {resp.status_code} {resp.text}")
    return resp.json()


def publish_offer(token: str, offer_id: str) -> dict:
    """Publish the given offer, converting it into an active draft listing."""
    url = f"{EBAY_ENDPOINT}/sell/inventory/v1/offer/{offer_id}/publish"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers)
    if not resp.ok:
        raise RuntimeError(f"eBay publish offer error: {resp.status_code} {resp.text}")
    return resp.json()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'image' not in request.files:
            return "No file part", 400
        file = request.files['image']
        if file.filename == '':
            return "No selected file", 400
        image_data = file.read()
        try:
            parsed = analyse_image(image_data)
        except Exception as e:
            return f"Error analysing image: {e}", 500

        # Create unique SKU
        sku = f"SKU-{uuid.uuid4().hex[:12].upper()}"
        token = get_env("EBAY_ACCESS_TOKEN")

        try:
            # Create or update inventory item
            create_inventory_item(token, sku, parsed.get('specifics', {}), parsed.get('description', ''))
            # Create offer
            offer_resp = create_offer(token, sku, parsed.get('title', 'Untitled'), parsed.get('description', ''), float(parsed.get('price', 1.0)))
            offer_id = offer_resp.get('offerId') or offer_resp.get('id')
            # Publish offer
            publish_resp = publish_offer(token, offer_id)
        except Exception as e:
            return f"Error creating eBay listing: {e}", 500

        return render_template(
            "result.html",
            title=parsed.get('title'),
            description=parsed.get('description'),
            specifics=parsed.get('specifics'),
            price=parsed.get('price'),
            sku=sku,
            offer_id=offer_id,
            publish_response=publish_resp,
            DEFAULT_CURRENCY=DEFAULT_CURRENCY
        )
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)