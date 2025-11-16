import os, json, logging, requests
from typing import Dict, Any, Optional

EBAY_ENDPOINT = "https://api.ebay.com"
INV_BASE = f"{EBAY_ENDPOINT}/sell/inventory/v1"

MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB")
PAYMENT_POLICY_ID = os.getenv("EBAY_PAYMENT_POLICY_ID", "")
RETURN_POLICY_ID = os.getenv("EBAY_RETURN_POLICY_ID", "")
FULFILLMENT_POLICY_ID = os.getenv("EBAY_FULFILLMENT_POLICY_ID", "")
MERCHANT_LOCATION_KEY = os.getenv("EBAY_MERCHANT_LOCATION_KEY", "")
DEFAULT_CATEGORY_ID = os.getenv("DEFAULT_CATEGORY_ID", "")
FORCE_DRAFTS = os.getenv("FORCE_DRAFTS", "true").lower() == "true"

log = logging.getLogger(__name__)

class EbayError(RuntimeError): pass

def _headers(token: str) -> Dict[str, str]:
    # Map marketplace IDs to Content-Language values
    lang_map = {
        "EBAY_GB": "en-GB",
        "EBAY_US": "en-US",
        "EBAY_AU": "en-AU",
        "EBAY_DE": "de-DE",
        "EBAY_FR": "fr-FR",
        "EBAY_IT": "it-IT",
        "EBAY_ES": "es-ES",
    }
    content_language = lang_map.get(MARKETPLACE_ID, "en-GB")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": content_language,
    }

def build_inventory_item_payload(
    sku: str,
    title: str,
    description: str,
    quantity: int,
    image_urls: list[str],
    condition: str = "VERY_GOOD",
    brand: Optional[str] = None,
    mpn: Optional[str] = None,
    aspects: Optional[Dict[str, list[str]]] = None,
) -> Dict[str, Any]:
    if not image_urls:
        raise ValueError("image_urls is empty; must include at least one public URL")

    product: Dict[str, Any] = {
        "title": title[:80],
        "description": description[:40000],
        "imageUrls": image_urls,
    }

    # Add brand if provided - must also include MPN
    if brand:
        product["brand"] = brand
        # MPN is required when brand is present - use provided value or "Does Not Apply"
        product["mpn"] = mpn if mpn else "Does Not Apply"
    # Extract brand from aspects if available
    elif aspects and "Brand" in aspects:
        brand_values = aspects.get("Brand", [])
        if brand_values and brand_values[0]:
            product["brand"] = brand_values[0]
            # MPN is required when brand is present
            product["mpn"] = mpn if mpn else "Does Not Apply"

    # Add MPN if provided separately (and brand was already set)
    if mpn and "mpn" not in product:
        product["mpn"] = mpn

    # Add aspects (item specifics)
    if aspects:
        # Filter and validate aspects
        validated_aspects = {}
        for key, values in aspects.items():
            # Skip Brand if we already added it
            if key == "Brand" and "brand" in product:
                continue

            # Ensure values is a list of strings
            if isinstance(values, list) and values:
                validated_aspects[key] = [str(v) for v in values if v]
            elif values:
                validated_aspects[key] = [str(values)]

        if validated_aspects:
            product["aspects"] = validated_aspects

    return {
        "sku": sku,
        "condition": condition,
        "product": product,
        "availability": {
            "shipToLocationAvailability": {"quantity": max(0, int(quantity))}
        },
    }

def build_offer_payload(sku: str, price_value: float, category_id: Optional[str] = None) -> Dict[str, Any]:
    cat = category_id or DEFAULT_CATEGORY_ID
    if not cat:
        raise ValueError("category_id is required (DEFAULT_CATEGORY_ID not set)")

    for k, v in {
        "paymentPolicyId": PAYMENT_POLICY_ID,
        "returnPolicyId": RETURN_POLICY_ID,
        "fulfillmentPolicyId": FULFILLMENT_POLICY_ID,
    }.items():
        if not v:
            raise ValueError(f"Missing required policy env: {k}")

    if not MERCHANT_LOCATION_KEY:
        raise ValueError("Missing EBAY_MERCHANT_LOCATION_KEY")

    return {
        "sku": sku,
        "marketplaceId": MARKETPLACE_ID,
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": str(cat),
        "pricingSummary": {"price": {"value": str(price_value), "currency": "GBP"}},
        "listingPolicies": {
            "paymentPolicyId": PAYMENT_POLICY_ID,
            "returnPolicyId": RETURN_POLICY_ID,
            "fulfillmentPolicyId": FULFILLMENT_POLICY_ID,
        },
        "merchantLocationKey": MERCHANT_LOCATION_KEY,
    }

def create_or_replace_inventory_item(token: str, sku: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{INV_BASE}/inventory_item/{requests.utils.quote(sku)}"
    r = requests.put(url, headers=_headers(token), data=json.dumps(payload))
    if r.status_code not in (200, 201, 204):
        log.error("Inventory item upsert failed %s: %s", r.status_code, r.text)
        raise EbayError(f"Inventory item failed: {r.text}")
    return r.json() if r.text else {"status": r.status_code}

def create_offer(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{INV_BASE}/offer"
    r = requests.post(url, headers=_headers(token), data=json.dumps(payload))
    if r.status_code not in (200, 201):
        log.error("Create offer failed %s: %s", r.status_code, r.text)
        raise EbayError(f"Create offer failed: {r.text}")
    return r.json()

def publish_offer(token: str, offer_id: str) -> Dict[str, Any]:
    url = f"{INV_BASE}/offer/{offer_id}/publish"
    r = requests.post(url, headers=_headers(token))
    if r.status_code not in (200, 201):
        log.error("Publish offer failed %s: %s", r.status_code, r.text)
        raise EbayError(f"Publish failed: {r.text}")
    return r.json()
