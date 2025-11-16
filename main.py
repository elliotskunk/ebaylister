"""
eBay Lister App - Main Application
Upload images, analyze with AI, and create optimized eBay listings
"""
import os
import json
import logging
from io import BytesIO
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
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
from ebay_picture_service import upload_image_to_eps, upload_multiple_images_to_eps, EPSError
from ai_analyzer import analyze_image_for_listing, analyze_multiple_images_for_listing, AIAnalysisError
from category_matcher import get_best_category_id

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max for multiple images

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
    Main endpoint: Upload images, analyze with AI, create eBay draft listing.

    Accepts:
        - multipart/form-data with 'images' files (multiple) or 'image' file (single)
        - Optional form fields: category_id, price_override, title_override

    Returns:
        JSON with listing details and offer ID
    """
    try:
        # 1. Validate image upload - support both 'images' (multiple) and 'image' (single)
        image_files = request.files.getlist('images')
        if not image_files or not image_files[0].filename:
            # Fallback to single 'image' field for backward compatibility
            if 'image' in request.files and request.files['image'].filename:
                image_files = [request.files['image']]
            else:
                return jsonify({"error": "No image files provided"}), 400

        # Filter out empty files
        image_files = [f for f in image_files if f.filename]
        if not image_files:
            return jsonify({"error": "No valid image files selected"}), 400

        if len(image_files) > 12:
            return jsonify({"error": "Maximum 12 images allowed per listing"}), 400

        log.info(f"Processing {len(image_files)} image(s): {[f.filename for f in image_files]}")

        # Get optional overrides from form
        category_override = request.form.get("category_id", "").strip()
        price_override = request.form.get("price_override", "").strip()
        title_override = request.form.get("title_override", "").strip()

        # 2. Process all images
        processed_images = []
        for i, image_file in enumerate(image_files, 1):
            try:
                image_bytes = validate_and_process_image(image_file)
                processed_images.append(image_bytes)
                log.info(f"Processed image {i}/{len(image_files)}: {image_file.filename}")
            except ValueError as e:
                return jsonify({"error": f"Invalid image {i} ({image_file.filename}): {e}"}), 400

        # 3. Analyze images with AI (send all images in one request)
        log.info(f"Analyzing {len(processed_images)} image(s) with AI...")
        try:
            ai_result = analyze_multiple_images_for_listing(processed_images)
            log.info(f"AI analysis complete: {ai_result['title'][:50]}...")
        except AIAnalysisError as e:
            log.error(f"AI analysis failed: {e}")
            return jsonify({"error": f"AI analysis failed: {e}"}), 500

        # 4. Upload all images to eBay Picture Service
        log.info(f"Uploading {len(processed_images)} image(s) to eBay Picture Service...")
        try:
            token = get_oauth_token()
            sku_base = generate_sku()
            images_data = [
                (img_bytes, f"{sku_base}_{i}.jpg")
                for i, img_bytes in enumerate(processed_images, 1)
            ]
            image_urls = upload_multiple_images_to_eps(token, images_data)
            log.info(f"Uploaded {len(image_urls)} image(s) to EPS")
        except EPSError as e:
            log.error(f"EPS upload failed: {e}")
            return jsonify({"error": f"Image upload failed: {e}"}), 500

        # 5. Determine category
        # For now, use DEFAULT_CATEGORY_ID (T-shirts) to ensure clothing conditions work
        # TODO: Re-enable auto-category matching after testing
        if category_override:
            category_id = category_override
            log.info(f"Using override category: {category_id}")
        elif DEFAULT_CATEGORY_ID:
            category_id = DEFAULT_CATEGORY_ID
            log.info(f"Using default category (T-shirts): {category_id}")
        else:
            try:
                category_id = get_best_category_id(
                    title=ai_result["title"],
                    aspects=ai_result.get("aspects"),
                    category_keywords=ai_result.get("category_keywords"),
                    fallback_category_id="15687"  # Men's T-Shirts
                )
                log.info(f"Auto-selected category: {category_id}")
            except ValueError as e:
                log.error(f"Category selection failed: {e}")
                return jsonify({"error": str(e)}), 400

        # 6. Apply overrides if provided
        title = title_override if title_override else ai_result["title"]
        price = float(price_override) if price_override else ai_result["price"]

        # 7. Generate SKU
        sku = sku_base

        # 8. Create inventory item with ALL image URLs
        log.info(f"Creating inventory item: {sku}")
        try:
            inv_payload = build_inventory_item_payload(
                sku=sku,
                title=title,
                description=ai_result["description"],
                quantity=1,
                image_urls=image_urls,  # Now supports multiple images
                condition=ai_result.get("condition", "PRE_OWNED_EXCELLENT"),
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

        # 10. Store listing data in session for preview
        session['pending_listing'] = {
            "sku": sku,
            "offer_id": offer_id,
            "title": title,
            "description": ai_result["description"],
            "price": price,
            "currency": "GBP",
            "category_id": category_id,
            "category_name": ai_result.get("category_keywords", ["General"])[0] if ai_result.get("category_keywords") else "General",
            "image_urls": image_urls,
            "condition": ai_result.get("condition", "USED_VERY_GOOD"),
            "quantity": 1,
            "marketplace": os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB"),
            "aspects": ai_result.get("aspects", {}),
            "brand": ai_result.get("aspects", {}).get("Brand", [""])[0] if ai_result.get("aspects", {}).get("Brand") else "",
        }

        log.info(f"Redirecting to preview page for offer: {offer_id}")

        # Redirect to preview page
        return redirect(url_for('preview_listing'))

    except Exception as e:
        log.exception("Unexpected error in upload_and_create_listing")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/preview")
def preview_listing():
    """Show preview of listing before publishing"""
    listing_data = session.get('pending_listing')
    if not listing_data:
        return redirect(url_for('index'))

    return render_template('preview.html', **listing_data)


@app.route("/publish", methods=["POST"])
def publish_listing():
    """Publish the pending listing to eBay"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        offer_id = data.get('offer_id')
        if not offer_id:
            return jsonify({"error": "No offer_id provided"}), 400

        # Get token and publish
        token = get_oauth_token()
        result = publish_offer(token, offer_id)

        listing_id = result.get("listingId")

        # Generate eBay listing URL
        marketplace = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB")
        if marketplace == "EBAY_GB":
            listing_url = f"https://www.ebay.co.uk/itm/{listing_id}"
        elif marketplace == "EBAY_US":
            listing_url = f"https://www.ebay.com/itm/{listing_id}"
        else:
            listing_url = f"https://www.ebay.com/itm/{listing_id}"

        # Clear the pending listing from session
        session.pop('pending_listing', None)

        log.info(f"✅ Listing published successfully! ID: {listing_id}")

        return jsonify({
            "success": True,
            "listing_id": listing_id,
            "listing_url": listing_url,
        })

    except EbayError as e:
        log.error(f"Failed to publish listing: {e}")
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        log.exception("Error publishing listing")
        return jsonify({"error": str(e)}), 500


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
    return jsonify({"error": "Files too large. Maximum total size is 50MB."}), 413


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
