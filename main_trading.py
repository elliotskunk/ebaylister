import os
import base64
import json
import re
from flask import Flask, request, render_template, jsonify
from dotenv import load_dotenv
import openai
import requests

# ── Setup ────────────────────────────────────────────────────────────────────────
load_dotenv()
app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

EBAY_ENDPOINT = "https://api.ebay.com"
OAUTH_URL     = f"{EBAY_ENDPOINT}/identity/v1/oauth2/token"
TRADING_URL   = f"{EBAY_ENDPOINT}/ws/api.dll"
SITE_ID       = "3"       # UK
COMPAT_LEVEL  = "1147"


# Business policy NAMES (recommended; IDs also supported – see XML builder below)
PAYMENT_POLICY_ID     = os.getenv("EBAY_PAYMENT_POLICY_ID", "")
RETURN_POLICY_ID      = os.getenv("EBAY_RETURN_POLICY_ID", "")
FULFILMENT_POLICY_ID    = os.getenv("EBAY_FULFILLMENT_POLICY_ID", "")

# Optional: default leaf category if you don’t provide one per item
DEFAULT_CATEGORY_ID     = os.getenv("EBAY_CATEGORY_ID", "")    # must be a *leaf* ID
# Optional: fallback photo URL (publicly reachable). Trading often requires 1+ photo.
DEFAULT_PICTURE_URL     = os.getenv("EBAY_DEFAULT_PICTURE_URL", "")

# OAuth client + refresh token
APP_ID        = os.getenv("EBAY_APP_ID")
CERT_ID       = os.getenv("EBAY_CERT_ID")
REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")


# ---- Local category suggester (uses your dumped JSON) ----
from functools import lru_cache

CATEGORIES_PATH = os.getenv("EBAY_CATEGORIES_JSON", "data/categories_ebay_gb.json")

@lru_cache(maxsize=1)
def load_categories():
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    cats = data.get("categories", data)  # support both {categories:[...]} and [...]
    out = []
    for c in cats:
        cid = str(c.get("id") or c.get("categoryId"))
        name = str(c.get("name") or c.get("categoryName") or "")
        leaf = bool(c.get("leaf", False))
        if cid and name:
            out.append({"id": cid, "name": name, "leaf": leaf})
    return out

def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())

def suggest_categories_local(query: str, k: int = 5) -> list[dict]:
    """
    Dumb but effective: +2 for whole-word match, +1 for substring. Prefer leaves.
    """
    terms = _tok(query)
    if not terms:
        return []
    cats = load_categories()
    leafs = [c for c in cats if c["leaf"]] or cats

    scored = []
    for c in leafs:
        name_l = c["name"].lower()
        score = 0
        for t in terms:
            if re.search(rf"\b{re.escape(t)}\b", name_l):
                score += 2
            elif t in name_l:
                score += 1
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], len(x[1]["name"])))
    return [c for _, c in scored[:k]]

def pick_category_id_from_ai(title: str, specifics: dict | None = None, fallback_env="EBAY_CATEGORY_ID") -> str:
    bits = [title or ""]
    sp = specifics or {}
    for k in ("Garment Type", "Type", "Department", "Style", "Brand", "Material"):
        v = sp.get(k)
        if isinstance(v, list) and v:
            bits.append(v[0])
        elif isinstance(v, str) and v.strip():
            bits.append(v)
    query = " ".join(bits)
    sugg = suggest_categories_local(query, k=1)
    if sugg:
        return sugg[0]["id"]
    cid = os.getenv(fallback_env)
    if not cid:
        raise RuntimeError("No category match and EBAY_CATEGORY_ID not set. Provide category_id or set env.")
    return cid

# ── Helpers ─────────────────────────────────────────────────────────────────────

from xml.etree import ElementTree as ET

def get_condition_id_for_category(token: str, category_id: str, preferred: int | None = 3000) -> int:
    headers = {
        "X-EBAY-API-CALL-NAME": "GetCategoryFeatures",
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPAT_LEVEL,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml; charset=utf-8",
    }
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetCategoryFeaturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <CategoryID>{category_id}</CategoryID>
  <DetailLevel>ReturnAll</DetailLevel>
  <FeatureID>ConditionEnabled</FeatureID>
  <FeatureID>ConditionValues</FeatureID>
</GetCategoryFeaturesRequest>"""
    r = requests.post(TRADING_URL, headers=headers, data=xml.encode("utf-8"), timeout=45)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
    ids = [int(x.text) for x in root.findall(".//e:ConditionValues/e:Condition/e:ID", ns)]
    if preferred and preferred in ids: return preferred
    return ids[0] if ids else (preferred or 3000)


def get_access_token() -> str:
    """Mint a fresh user access token from refresh token."""
    if not (APP_ID and CERT_ID and REFRESH_TOKEN):
        raise RuntimeError("Missing EBAY_APP_ID / EBAY_CERT_ID / EBAY_REFRESH_TOKEN")
    basic = base64.b64encode(f"{APP_ID}:{CERT_ID}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    scopes = " ".join([
        "https://api.ebay.com/oauth/api_scope/sell.account",
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
    ])
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN, "scope": scopes}
    r = requests.post(OAUTH_URL, headers=headers, data=data, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Token error: {r.status_code} {r.text}")
    return r.json()["access_token"]

def analyse_image(image_bytes: bytes) -> dict:
    """Use OpenAI to extract title/description/specifics/price from the image."""
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:image/jpeg;base64,{b64}"
    messages = [
        {"role": "system", "content": (
            "You are an expert vintage clothing seller. "
            "Return VALID JSON only with keys: "
            "title (string ≤80 chars), description (string), "
            "specifics (object of name -> array of values), price (number in GBP)."
        )},
        {"role": "user", "content": [
            {"type": "text", "text": "Analyse this clothing item and return only JSON."},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]},
    ]
    resp = openai.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.4, max_tokens=600)
    content = resp.choices[0].message.content or ""
    s, e = content.find("{"), content.rfind("}") + 1
    if s == -1 or e <= s:
        raise RuntimeError(f"Model did not return JSON. Raw: {content[:200]}")
    parsed = json.loads(content[s:e])

    # Normalise
    parsed["title"] = str(parsed.get("title", ""))[:80]
    try:
        parsed["price"] = round(float(parsed.get("price", 9.99)), 2)
    except Exception:
        parsed["price"] = 9.99
    specs = parsed.get("specifics") or {}
    # Ensure lists
    norm = {}
    for k, v in specs.items():
        if v is None: continue
        if isinstance(v, list): norm[k] = [str(x).strip() for x in v if str(x).strip()]
        else: norm[k] = [str(v).strip()] if str(v).strip() else []
        if not norm[k]: norm.pop(k, None)
    parsed["specifics"] = norm
    return parsed

def specifics_to_item_specifics_xml(specs: dict) -> str:
    """Build Trading <ItemSpecifics> XML."""
    if not specs: return ""
    blocks = []
    for name, values in specs.items():
        vals = "".join([f"<Value>{escape_xml(str(v))}</Value>" for v in (values or []) if str(v).strip()])
        if vals:
            blocks.append(f"<NameValueList><Name>{escape_xml(name)}</Name>{vals}</NameValueList>")
    return f"<ItemSpecifics>{''.join(blocks)}</ItemSpecifics>" if blocks else ""

def escape_xml(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

def pick_category_id(title: str, explicit: str | None = None) -> str:
    """Simple picker: explicit > env default; error if neither present."""
    if explicit and explicit.strip():
        return explicit.strip()
    if DEFAULT_CATEGORY_ID:
        return DEFAULT_CATEGORY_ID
    raise RuntimeError("No category ID provided. Set EBAY_CATEGORY_ID or pass category_id.")

def add_fixed_price_item(
    token: str,
    title: str,
    description: str,
    category_id: str,
    price: float,
    payment_policy_name: str,
    return_policy_name: str,
    shipping_policy_name: str,
    picture_urls: list[str] | None = None,
    postal_code: str = "DE22 3UP",
    location_str: str = "Derby, GB",
    item_specifics_xml: str = "",
) -> str:
    """Call Trading API AddFixedPriceItem. Returns raw XML response."""
    headers = {
        "X-EBAY-API-CALL-NAME": "AddFixedPriceItem",
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPAT_LEVEL,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml; charset=utf-8",
    }

    pics_xml = ""
    urls = [u for u in (picture_urls or []) if isinstance(u, str) and u.strip()]
    if not urls and DEFAULT_PICTURE_URL.strip():
        urls = [DEFAULT_PICTURE_URL.strip()]
    if urls:
        pics_xml = "<PictureDetails>" + "".join(f"<PictureURL>{escape_xml(u)}</PictureURL>" for u in urls) + "</PictureDetails>"

    # You can switch to IDs by replacing the Name tags with *ProfileID variants.
    if PAYMENT_POLICY_ID and RETURN_POLICY_ID and FULFILMENT_POLICY_ID:
        seller_profiles_xml = f"""
        <SellerProfiles>
        <SellerPaymentProfile><PaymentProfileID>{escape_xml(PAYMENT_POLICY_ID)}</PaymentProfileID></SellerPaymentProfile>
        <SellerReturnProfile><ReturnProfileID>{escape_xml(RETURN_POLICY_ID)}</ReturnProfileID></SellerReturnProfile>
        <SellerShippingProfile><ShippingProfileID>{escape_xml(FULFILMENT_POLICY_ID)}</ShippingProfileID></SellerShippingProfile>
        </SellerProfiles>"""
    else:
        seller_profiles_xml = f"""
        <SellerProfiles>
        <SellerPaymentProfile><PaymentProfileName>{escape_xml(payment_policy_name)}</PaymentProfileName></SellerPaymentProfile>
        <SellerReturnProfile><ReturnProfileName>{escape_xml(return_policy_name)}</ReturnProfileName></SellerReturnProfile>
        <SellerShippingProfile><ShippingProfileName>{escape_xml(shipping_policy_name)}</ShippingProfileName></SellerShippingProfile>
        </SellerProfiles>"""


    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <WarningLevel>High</WarningLevel>
  <ErrorLanguage>en_GB</ErrorLanguage>
  <Item>
    <Title>{escape_xml(title)}</Title>
    <Description>{escape_xml(description)}</Description>
    <PrimaryCategory><CategoryID>{escape_xml(str(category_id))}</CategoryID></PrimaryCategory>
    <StartPrice>{price:.2f}</StartPrice>
    <Country>GB</Country>
    <Currency>GBP</Currency>
    <PostalCode>{escape_xml(postal_code)}</PostalCode>
    <Location>{escape_xml(location_str)}</Location>
    <DispatchTimeMax>3</DispatchTimeMax>
    <ListingDuration>GTC</ListingDuration>
    <ListingType>FixedPriceItem</ListingType>
    <Quantity>1</Quantity>
    <ConditionID>3000</ConditionID>
    {pics_xml}
    {item_specifics_xml}
    {seller_profiles_xml}
  </Item>
</AddFixedPriceItemRequest>"""

    r = requests.post(TRADING_URL, headers=headers, data=xml.encode("utf-8"), timeout=45)
    r.raise_for_status()
    return r.text

# ── Routes ───────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # file upload
        if "image" not in request.files or not request.files["image"].filename:
            return "No file uploaded", 400
        img_bytes = request.files["image"].read()

        # optional manual overrides from the form
        category_override = request.form.get("category_id", "").strip()
        picture_override  = request.form.get("picture_url", "").strip()
        picture_urls = [picture_override] if picture_override else []

        try:
            parsed = analyse_image(img_bytes)
            category_id = category_override or pick_category_id_from_ai(parsed.get("title",""), parsed.get("specifics"))
            token = get_access_token()
            item_specs_xml = specifics_to_item_specifics_xml(parsed.get("specifics", {}))

            resp_xml = add_fixed_price_item(
                token=token,
                title=parsed["title"],
                description=parsed["description"],
                category_id=category_id,
                price=parsed["price"],
                payment_policy_name=PAYMENT_POLICY_ID,
                return_policy_name=RETURN_POLICY_ID,
                shipping_policy_name=FULFILMENT_POLICY_ID,
                picture_urls=picture_urls,
                item_specifics_xml=item_specs_xml,
            )
        except Exception as e:
            return f"Error: {e}", 500

        return render_template(
            "result.html",
            title=parsed["title"],
            description=parsed["description"],
            specifics=parsed.get("specifics", {}),
            price=parsed["price"],
            response_xml=resp_xml,
        )
    return render_template("index.html")

@app.route("/api/list", methods=["POST"])
def api_list():
    """
    JSON body:
    {
      "title": "...",
      "description": "...",
      "price": 14.99,
      "category_id": "LEAF_ID",         # optional if EBAY_CATEGORY_ID is set
      "picture_urls": ["https://..."]   # optional; falls back to EBAY_DEFAULT_PICTURE_URL
    }
    """
    data = request.get_json(force=True, silent=False)
    try:
        title = str(data["title"])[:80]
        description = str(data["description"])
        price = round(float(data["price"]), 2)
        category_id = (data.get("category_id") or
               pick_category_id_from_ai(title, data.get("specifics") or {}))
        picture_urls = data.get("picture_urls") or []
        item_specs_xml = specifics_to_item_specifics_xml(data.get("specifics") or {})

        token = get_access_token()
        resp_xml = add_fixed_price_item(
            token=token,
            title=title,
            description=description,
            category_id=category_id,
            price=price,
            payment_policy_name=PAYMENT_POLICY_ID,
            return_policy_name=RETURN_POLICY_ID,
            shipping_policy_namE=FULFILMENT_POLICY_ID,
            picture_urls=picture_urls,
            item_specifics_xml=item_specs_xml,
        )
        return jsonify({"ok": True, "response_xml": resp_xml})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/health")
def health():
    return {"status": "ok"}, 200

# ── Main ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
