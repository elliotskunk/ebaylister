"""
eBay Category Matching
Suggests the best eBay category based on item details using local category database.
"""
import os
import json
import re
import logging
from functools import lru_cache
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

CATEGORIES_PATH = os.getenv("EBAY_CATEGORIES_JSON", "categories.json")


@lru_cache(maxsize=1)
def load_categories() -> List[Dict[str, any]]:
    """Load eBay categories from JSON file (cached)"""
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both {categories:[...]} and [...] formats
        cats = data.get("categories", data) if isinstance(data, dict) else data

        # Normalize category data
        normalized = []
        for cat in cats:
            cat_id = str(cat.get("CategoryID") or cat.get("id") or cat.get("categoryId") or "")
            name = str(cat.get("CategoryName") or cat.get("name") or cat.get("categoryName") or "")
            leaf = bool(cat.get("LeafCategory", cat.get("leaf", False)))

            if cat_id and name:
                normalized.append({
                    "id": cat_id,
                    "name": name,
                    "leaf": leaf
                })

        log.info(f"Loaded {len(normalized)} categories from {CATEGORIES_PATH}")
        return normalized

    except FileNotFoundError:
        log.warning(f"Categories file not found: {CATEGORIES_PATH}")
        return []
    except json.JSONDecodeError as e:
        log.error(f"Invalid JSON in categories file: {e}")
        return []
    except Exception as e:
        log.exception("Error loading categories")
        return []


def _tokenize(text: str) -> List[str]:
    """Extract alphanumeric tokens from text"""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def suggest_category(
    title: str,
    aspects: Optional[Dict[str, List[str]]] = None,
    category_keywords: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, any]]:
    """
    Suggest eBay categories based on item details.

    Args:
        title: Item title
        aspects: Item specifics/aspects
        category_keywords: Additional category hints
        top_k: Number of suggestions to return

    Returns:
        List of category dicts with 'id', 'name', 'score'
    """
    categories = load_categories()
    if not categories:
        log.warning("No categories loaded, cannot suggest category")
        return []

    # Prefer leaf categories (actual listing categories)
    leaf_categories = [cat for cat in categories if cat["leaf"]]
    search_pool = leaf_categories if leaf_categories else categories

    # Build search query from all available information
    query_parts = [title or ""]

    if category_keywords:
        query_parts.append(category_keywords)

    if aspects:
        # Add key aspects that help identify category
        priority_aspects = [
            "Type", "Garment Type", "Product Type",
            "Department", "Gender",
            "Style", "Category",
            "Brand"  # Brand can help narrow down
        ]

        for aspect_name in priority_aspects:
            values = aspects.get(aspect_name, [])
            if values:
                query_parts.extend(values[:2])  # Top 2 values

    query = " ".join(query_parts)
    query_tokens = _tokenize(query)

    if not query_tokens:
        log.warning("No query tokens to search with")
        return []

    log.debug(f"Category search query: {query}")
    log.debug(f"Query tokens: {query_tokens}")

    # Score each category
    scored = []
    for cat in search_pool:
        name_lower = cat["name"].lower()
        score = 0

        for token in query_tokens:
            # +3 points for whole word match
            if re.search(rf"\b{re.escape(token)}\b", name_lower):
                score += 3
            # +1 point for substring match
            elif token in name_lower:
                score += 1

        if score > 0:
            scored.append({
                "id": cat["id"],
                "name": cat["name"],
                "score": score,
                "leaf": cat["leaf"]
            })

    # Sort by score (descending), then by name length (ascending for more specific)
    scored.sort(key=lambda x: (-x["score"], len(x["name"])))

    top_suggestions = scored[:top_k]

    if top_suggestions:
        log.info(f"Top category suggestion: {top_suggestions[0]['name']} (ID: {top_suggestions[0]['id']}, score: {top_suggestions[0]['score']})")
    else:
        log.warning("No category matches found")

    return top_suggestions


def get_best_category_id(
    title: str,
    aspects: Optional[Dict[str, List[str]]] = None,
    category_keywords: Optional[str] = None,
    fallback_category_id: Optional[str] = None
) -> str:
    """
    Get the best matching category ID.

    Args:
        title: Item title
        aspects: Item specifics
        category_keywords: Category hints
        fallback_category_id: Fallback if no match found

    Returns:
        str: Category ID

    Raises:
        ValueError: If no category can be determined
    """
    suggestions = suggest_category(title, aspects, category_keywords, top_k=1)

    if suggestions:
        return suggestions[0]["id"]

    # Try fallback
    if fallback_category_id:
        log.warning(f"No category match found, using fallback: {fallback_category_id}")
        return fallback_category_id

    # Try environment default
    default_category = os.getenv("DEFAULT_CATEGORY_ID")
    if default_category:
        log.warning(f"No category match found, using DEFAULT_CATEGORY_ID: {default_category}")
        return default_category

    raise ValueError(
        "Could not determine category. No matches found and no fallback provided. "
        "Please set DEFAULT_CATEGORY_ID environment variable or provide category_id."
    )
