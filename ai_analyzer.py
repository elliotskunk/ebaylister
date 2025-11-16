"""
AI Image Analysis for eBay Listings
Uses OpenAI vision models (gpt-4o-mini by default) to analyze product images and generate SEO-optimized listings.
"""
import os
import base64
import json
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI, OpenAIError

log = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default to cost-effective model
_openai_client = None

def get_openai_client() -> OpenAI:
    """Get or create OpenAI client instance"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AIAnalysisError("OPENAI_API_KEY not set in environment")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


class AIAnalysisError(RuntimeError):
    """Error analyzing image with AI"""
    pass


def analyze_image_for_listing(image_bytes: bytes, category_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze an image using OpenAI vision models and generate eBay listing data optimized for Cassini SEO.

    Args:
        image_bytes: Raw image bytes
        category_hint: Optional category hint to help with analysis

    Returns:
        dict: {
            "title": str,           # SEO-optimized title (max 80 chars)
            "description": str,     # Detailed HTML description
            "price": float,         # Suggested price in GBP
            "condition": str,       # NEW, USED_EXCELLENT, USED_GOOD, etc.
            "aspects": dict,        # Item specifics as {name: [values]}
            "category_keywords": str  # Keywords for category matching
        }

    Raises:
        AIAnalysisError: If analysis fails
    """
    try:
        # Encode image to base64
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        data_uri = f"data:image/jpeg;base64,{b64_image}"

        # Enhanced prompt for Cassini SEO optimization
        system_prompt = """You are an expert eBay listing specialist with deep knowledge of Cassini SEO (eBay's search algorithm).

Your task is to analyze product images and create highly optimized eBay listings that rank well in search results.

CRITICAL SEO RULES FOR CASSINI:
1. TITLE: Must be keyword-rich, specific, and front-loaded with most important terms
   - Include: Brand, Type/Model, Key Features, Size/Color, Condition
   - Use exact product names, not generic terms
   - Max 80 characters - use every character wisely
   - Example: "Vintage Levi's 501 Jeans Blue Denim W32 L34 Made in USA 90s"

2. ITEM SPECIFICS: Critical for Cassini ranking
   - Provide as many accurate specifics as possible
   - Use eBay's standard aspect names (Brand, Size, Color, Material, Style, etc.)
   - Be specific and detailed

3. DESCRIPTION: Should be detailed and keyword-rich
   - Include measurements, condition details, material composition
   - Use HTML formatting for readability
   - Mention any flaws honestly
   - Include style/fit information

4. CONDITION: Be accurate and honest (use these exact values)
   - NEW: Brand new with tags
   - USED_EXCELLENT: Like new, minimal wear
   - USED_VERY_GOOD: Light wear, fully functional
   - FOR_PARTS_OR_NOT_WORKING: Damaged or non-functional

5. CATEGORY KEYWORDS: Help with categorization
   - Provide specific terms that identify the item category

Return ONLY valid JSON with this exact structure:
{
  "title": "SEO-optimized title max 80 chars",
  "description": "Detailed HTML description",
  "price": 19.99,
  "condition": "USED_EXCELLENT",
  "aspects": {
    "Brand": ["Brand Name"],
    "Type": ["Item Type"],
    "Size": ["Size"],
    "Colour": ["Color"],
    "Material": ["Material"],
    "Style": ["Style"],
    "Fit": ["Fit Type"],
    "Era": ["Decade/Era"],
    "Country/Region of Manufacture": ["Country"],
    "Features": ["Feature1", "Feature2"]
  },
  "category_keywords": "specific category identifying terms"
}"""

        user_prompt = "Analyze this item and create an eBay listing optimized for Cassini SEO. Return only the JSON response."

        if category_hint:
            user_prompt += f"\n\nCategory hint: {category_hint}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ]

        log.info(f"Sending image to {OPENAI_MODEL} for analysis...")

        client = get_openai_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=1500,
        )

        content = response.choices[0].message.content or ""
        log.debug(f"AI response: {content[:200]}...")

        # Extract JSON from response
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1

        if start_idx == -1 or end_idx <= start_idx:
            log.error(f"No JSON found in AI response: {content[:500]}")
            raise AIAnalysisError("AI did not return valid JSON")

        json_str = content[start_idx:end_idx]
        parsed = json.loads(json_str)

        # Validate and normalize the response
        result = _normalize_ai_response(parsed)

        log.info(f"Successfully analyzed image: {result['title'][:50]}...")
        return result

    except OpenAIError as e:
        log.exception("OpenAI API error during image analysis")
        raise AIAnalysisError(f"OpenAI API error: {e}")
    except json.JSONDecodeError as e:
        log.exception(f"Failed to parse AI response as JSON: {json_str[:500]}")
        raise AIAnalysisError(f"Invalid JSON from AI: {e}")
    except Exception as e:
        log.exception("Unexpected error during image analysis")
        raise AIAnalysisError(f"Image analysis failed: {e}")


def analyze_multiple_images_for_listing(
    images_bytes: List[bytes],
    category_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze multiple images using OpenAI vision models and generate eBay listing data.
    All images are sent in a single API request for comprehensive analysis.

    Args:
        images_bytes: List of raw image bytes (JPEG format)
        category_hint: Optional category hint to help with analysis

    Returns:
        dict: Same structure as analyze_image_for_listing

    Raises:
        AIAnalysisError: If analysis fails
    """
    if not images_bytes:
        raise AIAnalysisError("No images provided for analysis")

    if len(images_bytes) == 1:
        # Use single image function for efficiency
        return analyze_image_for_listing(images_bytes[0], category_hint)

    try:
        # Build content array with all images
        content_parts = [
            {
                "type": "text",
                "text": f"Analyze these {len(images_bytes)} product images and create a single eBay listing. "
                       f"Consider all angles and details visible across all images. "
                       f"Return only the JSON response optimized for Cassini SEO."
            }
        ]

        # Add each image to the content
        for i, img_bytes in enumerate(images_bytes, 1):
            b64_image = base64.b64encode(img_bytes).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{b64_image}"
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri}
            })

        if category_hint:
            content_parts[0]["text"] += f"\n\nCategory hint: {category_hint}"

        # Enhanced system prompt for multiple images
        system_prompt = """You are an expert eBay listing specialist with deep knowledge of Cassini SEO (eBay's search algorithm).

You are analyzing MULTIPLE product images to create a comprehensive eBay listing. Use ALL the images to:
- Identify the product from different angles
- Note any details, labels, tags, or measurements visible
- Assess overall condition from all perspectives
- Extract brand information if visible on any tag/label

CRITICAL SEO RULES FOR CASSINI:
1. TITLE: Must be keyword-rich, specific, and front-loaded with most important terms
   - Include: Brand, Type/Model, Key Features, Size/Color, Condition
   - Use exact product names, not generic terms
   - Max 80 characters - use every character wisely
   - Example: "Vintage Levi's 501 Jeans Blue Denim W32 L34 Made in USA 90s"

2. ITEM SPECIFICS: Critical for Cassini ranking
   - Provide as many accurate specifics as possible from ALL images
   - Use eBay's standard aspect names (Brand, Size, Color, Material, Style, etc.)
   - Be specific and detailed - check all images for tags/labels

3. DESCRIPTION: Should be detailed and keyword-rich
   - Include measurements, condition details, material composition
   - Use HTML formatting for readability
   - Mention any flaws honestly (visible in any image)
   - Include style/fit information

4. CONDITION: Be accurate based on ALL images (use these exact values)
   - NEW: Brand new with tags
   - USED_EXCELLENT: Like new, minimal wear
   - USED_VERY_GOOD: Light wear, fully functional
   - FOR_PARTS_OR_NOT_WORKING: Damaged or non-functional

5. CATEGORY KEYWORDS: Help with categorization
   - Provide specific terms that identify the item category

Return ONLY valid JSON with this exact structure:
{
  "title": "SEO-optimized title max 80 chars",
  "description": "Detailed HTML description based on all images",
  "price": 19.99,
  "condition": "USED_EXCELLENT",
  "aspects": {
    "Brand": ["Brand Name"],
    "Type": ["Item Type"],
    "Size": ["Size"],
    "Colour": ["Color"],
    "Material": ["Material"],
    "Style": ["Style"],
    "Fit": ["Fit Type"],
    "Era": ["Decade/Era"],
    "Country/Region of Manufacture": ["Country"],
    "Features": ["Feature1", "Feature2"]
  },
  "category_keywords": "specific category identifying terms"
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ]

        log.info(f"Sending {len(images_bytes)} images to {OPENAI_MODEL} for analysis...")

        client = get_openai_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,  # More tokens for multiple images
        )

        content = response.choices[0].message.content or ""
        log.debug(f"AI response: {content[:200]}...")

        # Extract JSON from response
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1

        if start_idx == -1 or end_idx <= start_idx:
            log.error(f"No JSON found in AI response: {content[:500]}")
            raise AIAnalysisError("AI did not return valid JSON")

        json_str = content[start_idx:end_idx]
        parsed = json.loads(json_str)

        # Validate and normalize the response
        result = _normalize_ai_response(parsed)

        log.info(f"Successfully analyzed {len(images_bytes)} images: {result['title'][:50]}...")
        return result

    except OpenAIError as e:
        log.exception("OpenAI API error during multi-image analysis")
        raise AIAnalysisError(f"OpenAI API error: {e}")
    except json.JSONDecodeError as e:
        log.exception(f"Failed to parse AI response as JSON")
        raise AIAnalysisError(f"Invalid JSON from AI: {e}")
    except Exception as e:
        log.exception("Unexpected error during multi-image analysis")
        raise AIAnalysisError(f"Multi-image analysis failed: {e}")


def _normalize_ai_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate AI response data"""

    # Normalize title (max 80 chars)
    title = str(data.get("title", "Untitled Item"))[:80].strip()
    if not title:
        title = "Item for Sale"

    # Normalize description
    description = str(data.get("description", "")).strip()
    if not description:
        description = "<p>Item in good condition. Please see photos for details.</p>"

    # Normalize price
    try:
        price = float(data.get("price", 9.99))
        price = max(0.99, min(999999.99, round(price, 2)))
    except (ValueError, TypeError):
        price = 9.99

    # Normalize condition - use VALID eBay ConditionEnum values
    # See: https://developer.ebay.com/api-docs/sell/inventory/types/slr:ConditionEnum
    # Valid enums: NEW, LIKE_NEW, USED_EXCELLENT, USED_VERY_GOOD, USED_GOOD, USED_ACCEPTABLE, etc.
    # IMPORTANT: There is NO plain "VERY_GOOD" or "GOOD" enum - those are INVALID!
    # The UI displays "Very Good" but the API enum is "USED_VERY_GOOD"
    condition = str(data.get("condition", "USED_VERY_GOOD")).upper().replace(" ", "_")

    # Valid eBay ConditionEnum values per official documentation
    valid_conditions = {
        "NEW", "LIKE_NEW", "NEW_OTHER", "NEW_WITH_DEFECTS",
        "CERTIFIED_REFURBISHED", "EXCELLENT_REFURBISHED", "VERY_GOOD_REFURBISHED", "GOOD_REFURBISHED",
        "SELLER_REFURBISHED", "USED_EXCELLENT", "USED_VERY_GOOD", "USED_GOOD", "USED_ACCEPTABLE",
        "PRE_OWNED_EXCELLENT", "PRE_OWNED_FAIR", "FOR_PARTS_OR_NOT_WORKING"
    }

    # Map INVALID values to VALID eBay enum values
    invalid_to_valid = {
        "VERY_GOOD": "USED_VERY_GOOD",  # INVALID! Must use USED_VERY_GOOD
        "GOOD": "USED_GOOD",  # INVALID! Must use USED_GOOD
        "ACCEPTABLE": "USED_ACCEPTABLE",  # INVALID! Must use USED_ACCEPTABLE
        "EXCELLENT": "USED_EXCELLENT",
        "FAIR": "PRE_OWNED_FAIR",
        "NEW_WITH_TAGS": "NEW",
        "NEW_WITHOUT_TAGS": "NEW",
    }

    if condition in invalid_to_valid:
        condition = invalid_to_valid[condition]
    elif condition not in valid_conditions:
        # Try to infer from keywords
        if "NEW" in condition:
            condition = "NEW"
        elif "LIKE" in condition and "NEW" in condition:
            condition = "LIKE_NEW"
        elif "EXCELLENT" in condition:
            condition = "USED_EXCELLENT"
        elif "VERY" in condition and "GOOD" in condition:
            condition = "USED_VERY_GOOD"
        elif "GOOD" in condition:
            condition = "USED_GOOD"
        elif "ACCEPTABLE" in condition or "FAIR" in condition:
            condition = "USED_ACCEPTABLE"
        else:
            condition = "USED_VERY_GOOD"  # Safe default - widely supported

    # Normalize aspects/item specifics
    aspects = data.get("aspects", {})
    if not isinstance(aspects, dict):
        aspects = {}

    normalized_aspects = {}
    for key, value in aspects.items():
        if value is None:
            continue

        # Ensure values are lists of strings
        if isinstance(value, list):
            values = [str(v).strip() for v in value if v and str(v).strip()]
        else:
            values = [str(value).strip()] if value and str(value).strip() else []

        if values:
            normalized_aspects[str(key).strip()] = values

    # Category keywords
    category_keywords = str(data.get("category_keywords", "")).strip()

    return {
        "title": title,
        "description": description,
        "price": price,
        "condition": condition,
        "aspects": normalized_aspects,
        "category_keywords": category_keywords,
    }


def enhance_description_for_mobile(description: str) -> str:
    """
    Enhance description with mobile-friendly HTML formatting.

    Args:
        description: Plain or simple HTML description

    Returns:
        str: Enhanced HTML description optimized for mobile viewing
    """
    # Basic HTML wrapper with mobile-friendly styling
    enhanced = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
    {description}
</div>
"""
    return enhanced.strip()
