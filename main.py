"""
eBay Lister App - Main Application
Upload images, analyze with AI, and create optimized eBay listings
"""
import os
import json
import logging
from io import BytesIO
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from PIL import Image

# Import our modules
from auth import get_oauth_token
from inventory_flow import (
    build_inventory_item_payload,
    build_offer_payload,
    create_or_replace_inventory_item,
    create_offer,
    publish_offer,
    EbayError,
)
from ebay_picture_service import upload_image_to_eps, EPSError
from ai_analyzer import analyze_image_for_listing, AIAnalysisError
from category_matcher import get_best_category_id

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max to support multiple images

# Configure logging
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("ebay_lister")

# Configuration
FORCE_DRAFTS = os.getenv("FORCE_DRAFTS", "true").lower() == "true"
DEFAULT_CATEGORY_ID = os.getenv("DEFAULT_CATEGORY_ID", "")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_and_process_image(image_file) -> bytes:
    """
    Validate and process uploaded image file.

    Args:
        image_file: Flask file upload object

    Returns:
        bytes: Processed image bytes (as JPEG)

    Raises:
        ValueError: If image is invalid
    """
    try:
        # Read image bytes
        image_bytes = image_file.read()

        # Validate it's a real image
        img = Image.open(BytesIO(image_bytes))

        # Convert to RGB if needed (handles PNG with alpha, etc.)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # Resize if too large (max 1600px on longest side for faster upload)
        max_size = 1600
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            log.info(f"Resized image from original to {img.size}")

        # Save as JPEG to BytesIO
        output = BytesIO()
        img.save(output, format='JPEG', quality=90, optimize=True)
        processed_bytes = output.getvalue()

        log.info(f"Processed image: {img.size}, {len(processed_bytes)} bytes")
        return processed_bytes

    except Exception as e:
        log.error(f"Image validation failed: {e}")
        raise ValueError(f"Invalid image file: {e}")


def generate_sku() -> str:
    """Generate a unique SKU"""
    import time
    return f"SKU-{int(time.time())}-{os.urandom(2).hex()}"


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Render the upload form"""
    return render_template("upload.html")


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/upload", methods=["POST"])
def upload_and_create_listing():
    """
    Main endpoint: Upload image, analyze with AI, create eBay draft listing.

    Accepts:
        - multipart/form-data with 'image' file
        - Optional form fields: category_id, price_override, title_override

    Returns:
        JSON with listing details and offer ID
    """
    try:
        # 1. Validate image upload
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        image_file = request.files['image']
        if not image_file.filename:
            return jsonify({"error": "No image file selected"}), 400

        log.info(f"Processing upload: {image_file.filename}")

        # Get optional overrides from form
        category_override = request.form.get("category_id", "").strip()
        price_override = request.form.get("price_override", "").strip()
        title_override = request.form.get("title_override", "").strip()

        # 2. Process image
        try:
            image_bytes = validate_and_process_image(image_file)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # 3. Analyze image with AI
        log.info("Analyzing image with AI...")
        try:
            ai_result = analyze_image_for_listing(image_bytes)
            log.info(f"AI analysis complete: {ai_result['title'][:50]}...")
        except AIAnalysisError as e:
            log.error(f"AI analysis failed: {e}")
            return jsonify({"error": f"AI analysis failed: {e}"}), 500

        # 4. Upload image to eBay Picture Service
        log.info("Uploading image to eBay Picture Service...")
        try:
            token = get_oauth_token()
            image_url = upload_image_to_eps(
                token,
                image_bytes,
                image_name=f"{generate_sku()}.jpg"
            )
            log.info(f"Image uploaded to EPS: {image_url}")
        except EPSError as e:
            log.error(f"EPS upload failed: {e}")
            return jsonify({"error": f"Image upload failed: {e}"}), 500

        # 5. Determine category
        if category_override:
            category_id = category_override
            log.info(f"Using override category: {category_id}")
        else:
            try:
                category_id = get_best_category_id(
                    title=ai_result["title"],
                    aspects=ai_result.get("aspects"),
                    category_keywords=ai_result.get("category_keywords"),
                    fallback_category_id=DEFAULT_CATEGORY_ID
                )
                log.info(f"Auto-selected category: {category_id}")
            except ValueError as e:
                log.error(f"Category selection failed: {e}")
                return jsonify({"error": str(e)}), 400

        # 6. Apply overrides if provided
        title = title_override if title_override else ai_result["title"]
        price = float(price_override) if price_override else ai_result["price"]

        # 7. Generate SKU
        sku = generate_sku()

        # 8. Create inventory item
        log.info(f"Creating inventory item: {sku}")
        try:
            inv_payload = build_inventory_item_payload(
                sku=sku,
                title=title,
                description=ai_result["description"],
                quantity=1,
                image_urls=[image_url],
                aspects=ai_result.get("aspects"),
            )

            create_or_replace_inventory_item(token, sku, inv_payload)
            log.info(f"Inventory item created: {sku}")

        except EbayError as e:
            log.error(f"Failed to create inventory item: {e}")
            return jsonify({"error": f"Failed to create inventory item: {e}"}), 502

        # 9. Create offer (draft listing)
        log.info(f"Creating offer for SKU: {sku}")
        try:
            offer_payload = build_offer_payload(
                sku=sku,
                price_value=price,
                category_id=category_id,
            )

            offer_response = create_offer(token, offer_payload)
            offer_id = offer_response.get("offerId")

            log.info(f"✅ Draft listing created! Offer ID: {offer_id}")

        except EbayError as e:
            log.error(f"Failed to create offer: {e}")
            return jsonify({"error": f"Failed to create offer: {e}"}), 502

        # 10. Return success response
        return jsonify({
            "success": True,
            "message": "Draft listing created successfully!",
            "sku": sku,
            "offer_id": offer_id,
            "title": title,
            "price": price,
            "category_id": category_id,
            "image_url": image_url,
            "condition": ai_result.get("condition", "USED_GOOD"),
            "ai_analysis": {
                "title": ai_result["title"],
                "description": ai_result["description"][:200] + "...",
                "aspects": ai_result.get("aspects", {}),
                "suggested_price": ai_result["price"],
            },
            "note": "This is a DRAFT listing. It will not be published automatically." if FORCE_DRAFTS else "Listing created as draft."
        }), 201

    except Exception as e:
        log.exception("Unexpected error in upload_and_create_listing")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/create", methods=["POST"])
def api_create_listing():
    """
    API endpoint for creating listings with manual data (no AI analysis).

    Expects JSON:
    {
        "title": "Item Title",
        "description": "Item description",
        "price": 19.99,
        "image_url": "https://...",  // eBay EPS URL
        "category_id": "12345",      // Optional
        "aspects": {...},            // Optional
        "sku": "CUSTOM-SKU"          // Optional
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate required fields
        required = ["title", "description", "price", "image_url"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        # Get token
        token = get_oauth_token()

        # Extract data
        title = str(data["title"])[:80]
        description = str(data["description"])
        price = float(data["price"])
        image_url = str(data["image_url"])
        category_id = data.get("category_id") or DEFAULT_CATEGORY_ID
        aspects = data.get("aspects", {})
        sku = data.get("sku") or generate_sku()

        if not category_id:
            return jsonify({"error": "category_id required (or set DEFAULT_CATEGORY_ID)"}), 400

        # Create inventory item
        inv_payload = build_inventory_item_payload(
            sku=sku,
            title=title,
            description=description,
            quantity=1,
            image_urls=[image_url],
            aspects=aspects,
        )
        create_or_replace_inventory_item(token, sku, inv_payload)

        # Create offer
        offer_payload = build_offer_payload(
            sku=sku,
            price_value=price,
            category_id=category_id,
        )
        offer_response = create_offer(token, offer_payload)

        return jsonify({
            "success": True,
            "sku": sku,
            "offer_id": offer_response.get("offerId"),
            "offer": offer_response,
        }), 201

    except EbayError as e:
        log.error(f"eBay API error: {e}")
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        log.exception("Error in api_create_listing")
        return jsonify({"error": str(e)}), 500


@app.route("/api/publish/<offer_id>", methods=["POST"])
def api_publish_offer(offer_id: str):
    """
    Publish an offer (make it live on eBay).

    WARNING: This will publish the listing live!
    Disabled by default when FORCE_DRAFTS=true
    """
    try:
        token = get_oauth_token()
        result = publish_offer(token, offer_id)

        return jsonify({
            "success": True,
            "message": "Offer published successfully!",
            "listing_id": result.get("listingId"),
            "result": result,
        })

    except EbayError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/analyze", methods=["POST"])
def api_analyze_image():
    """
    Analyze image with AI without creating listing.
    Returns AI analysis results only.
    """
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        image_file = request.files['image']
        if not image_file.filename:
            return jsonify({"error": "No image selected"}), 400

        # Process image
        image_bytes = validate_and_process_image(image_file)

        # Analyze with AI
        ai_result = analyze_image_for_listing(image_bytes)

        # Suggest category
        try:
            category_id = get_best_category_id(
                title=ai_result["title"],
                aspects=ai_result.get("aspects"),
                category_keywords=ai_result.get("category_keywords"),
                fallback_category_id=DEFAULT_CATEGORY_ID
            )
            ai_result["suggested_category_id"] = category_id
        except ValueError:
            ai_result["suggested_category_id"] = None

        return jsonify({
            "success": True,
            "analysis": ai_result,
        })

    except AIAnalysisError as e:
        return jsonify({"error": str(e)}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors"""
    return jsonify({"error": "File too large. Maximum size is 16MB."}), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    log.exception("Internal server error")
    return jsonify({"error": "Internal server error. Check logs for details."}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    log.info("=" * 60)
    log.info("eBay Lister App Starting")
    log.info("=" * 60)
    log.info(f"Port: {port}")
    log.info(f"Debug: {debug}")
    log.info(f"Force Drafts: {FORCE_DRAFTS}")
    log.info(f"Default Category: {DEFAULT_CATEGORY_ID or 'Not set'}")
    log.info("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=debug)
