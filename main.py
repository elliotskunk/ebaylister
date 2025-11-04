import os, json, logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from inventory_flow import (
    build_inventory_item_payload,
    build_offer_payload,
    create_or_replace_inventory_item,
    create_offer,
    publish_offer,
    EbayError,
)
from auth import get_oauth_token

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# logging
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("app")


@app.route("/health")
def health():
    return {"ok": True}


@app.route("/create", methods=["POST"])
def create_draft():
    """
    Create/replace Inventory Item and create an Offer. DOES NOT publish.
    Expects form fields (or JSON):
      sku (optional), title, description, price, category_id (optional), quantity (default 1), image_url
      dry_run = "on" (optional)
    """
    token = get_oauth_token()

    # allow JSON or form
    data = request.get_json(silent=True) or request.form.to_dict()
    dry_run = str(data.get("dry_run", "")).lower() in ("on", "true", "1")

    sku = data.get("sku") or f"SKU-{os.urandom(3).hex()}"
    title = data.get("title", "Untitled")
    description = data.get("description", "")
    price = float(data.get("price", 9.99))
    category_id = data.get("category_id")
    qty = int(data.get("quantity", 1))
    img_url = data.get("image_url")

    if not img_url:
        return jsonify({"error": "Missing image_url"}), 400

    inv_payload = build_inventory_item_payload(
        sku=sku,
        title=title,
        description=description,
        quantity=qty,
        image_urls=[img_url],
    )
    offer_payload = build_offer_payload(
        sku=sku,
        price_value=price,
        category_id=category_id,
    )

    if dry_run:
        return jsonify({
            "dry_run": True,
            "inventory_item": inv_payload,
            "offer": offer_payload,
        })

    try:
        _ = create_or_replace_inventory_item(token, sku, inv_payload)
        offer = create_offer(token, offer_payload)
        return jsonify({
            "status": "draft_created",
            "sku": sku,
            "offer": offer,
            "offerId": offer.get("offerId"),
        })
    except EbayError as e:
        log.exception("eBay error")
        return jsonify({"error": str(e)}), 502


@app.route("/publish/<offer_id>", methods=["POST"])
def publish(offer_id: str):
    token = get_oauth_token()
    try:
        res = publish_offer(token, offer_id)
        return jsonify({"status": "published", "result": res})
    except EbayError as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
