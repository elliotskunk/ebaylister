"""
Category-specific rules for eBay listings.
Each item type has different required aspects and condition mappings.
"""

# Item type definitions with their eBay requirements
ITEM_TYPE_RULES = {
    "clothing": {
        "name": "Clothing",
        "default_category_id": "15687",  # Men's T-Shirts
        "condition_mapping": {
            # Clothing/Apparel conditions (eBay UI labels → ConditionEnum)
            "new": "NEW",  # "New with tags"
            "new_without_tags": "NEW_OTHER",  # "New without tags"
            "new_with_defects": "NEW_WITH_DEFECTS",  # "New with imperfections"
            "like_new": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "excellent": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "very_good": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "good": "USED_EXCELLENT",  # "Pre-owned - Good" (ID 3000 shows as this in apparel)
            "fair": "PRE_OWNED_FAIR",  # "Pre-owned - Fair"
            "acceptable": "PRE_OWNED_FAIR",  # "Pre-owned - Fair"
        },
        "default_condition": "PRE_OWNED_EXCELLENT",  # Safest default for used clothing
        "required_aspects": ["Brand", "Department"],
        "default_aspects": {
            "Brand": "Unbranded",
            "Department": "Unisex Adults",
        },
        "single_value_aspects": ["Colour", "Size", "Department"],
    },
    "kitchenware": {
        "name": "Kitchenware/Crockery",
        "default_category_id": "20693",  # Mugs category
        "condition_mapping": {
            # Kitchenware conditions (eBay UI: "New", "New (Other)", "Used")
            "new": "NEW",  # "New"
            "new_other": "NEW_OTHER",  # "New (Other)"
            "like_new": "NEW_OTHER",  # Map to "New (Other)"
            "excellent": "USED_EXCELLENT",  # "Used"
            "very_good": "USED_EXCELLENT",  # "Used"
            "good": "USED_EXCELLENT",  # "Used"
            "fair": "USED_EXCELLENT",  # "Used"
            "acceptable": "USED_EXCELLENT",  # "Used"
            "used": "USED_EXCELLENT",  # "Used"
        },
        "default_condition": "USED_EXCELLENT",  # Default to "Used"
        "required_aspects": ["Brand"],
        "default_aspects": {
            "Brand": "Unbranded",
        },
        "single_value_aspects": ["Colour"],
    },
    "shoes": {
        "name": "Shoes",
        "default_category_id": "93427",  # Men's Shoes
        "condition_mapping": {
            # Shoes conditions (eBay UI labels → ConditionEnum) - same as clothing (apparel)
            "new": "NEW",  # "New with box"
            "new_without_box": "NEW_OTHER",  # "New without box"
            "new_with_defects": "NEW_WITH_DEFECTS",  # "New with defects"
            "like_new": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "excellent": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "very_good": "PRE_OWNED_EXCELLENT",  # "Pre-owned - Excellent"
            "good": "USED_EXCELLENT",  # "Pre-owned - Good" (ID 3000)
            "fair": "PRE_OWNED_FAIR",  # "Pre-owned - Fair"
            "acceptable": "PRE_OWNED_FAIR",  # "Pre-owned - Fair"
        },
        "default_condition": "PRE_OWNED_EXCELLENT",  # Safest default for used shoes
        "required_aspects": ["Brand", "UK Shoe Size"],
        "default_aspects": {
            "Brand": "Unbranded",
        },
        "single_value_aspects": ["Colour", "UK Shoe Size"],
    },
    "books": {
        "name": "Books & Media",
        "default_category_id": "261186",  # Books
        "condition_mapping": {
            # Books/Media/Collectibles conditions (eBay UI: "New", "Like New", "Very Good", "Good", "Acceptable")
            "new": "NEW",  # "New"
            "like_new": "LIKE_NEW",  # "Like New"
            "excellent": "LIKE_NEW",  # "Like New"
            "very_good": "USED_VERY_GOOD",  # "Very Good"
            "good": "USED_GOOD",  # "Good"
            "fair": "USED_ACCEPTABLE",  # "Acceptable"
            "acceptable": "USED_ACCEPTABLE",  # "Acceptable"
        },
        "default_condition": "USED_VERY_GOOD",  # "Very Good"
        "required_aspects": ["Brand"],  # Books use Author but Brand is still needed
        "default_aspects": {
            "Brand": "Unbranded",
        },
        "single_value_aspects": [],
    },
    "electronics": {
        "name": "Electronics",
        "default_category_id": "175672",  # Consumer Electronics
        "condition_mapping": {
            # Electronics conditions - similar to general items
            "new": "NEW",  # "New"
            "like_new": "LIKE_NEW",  # "Like New"
            "excellent": "USED_EXCELLENT",  # "Excellent" / "Used - Excellent"
            "very_good": "USED_VERY_GOOD",  # "Very Good"
            "good": "USED_GOOD",  # "Good"
            "fair": "USED_ACCEPTABLE",  # "Acceptable"
            "acceptable": "USED_ACCEPTABLE",  # "Acceptable"
            "for_parts": "FOR_PARTS_OR_NOT_WORKING",  # "For parts or not working"
        },
        "default_condition": "USED_VERY_GOOD",  # "Very Good"
        "required_aspects": ["Brand"],
        "default_aspects": {
            "Brand": "Unbranded",
        },
        "single_value_aspects": ["Colour"],
    },
    "general": {
        "name": "General/Other",
        "default_category_id": "11450",  # Other
        "condition_mapping": {
            # General/Collectibles/Memorabilia conditions (eBay UI: "New", "Like New", "Very Good", "Good", "Acceptable")
            "new": "NEW",  # "New"
            "like_new": "LIKE_NEW",  # "Like New"
            "excellent": "USED_EXCELLENT",  # "Excellent" / "Used - Excellent"
            "very_good": "USED_VERY_GOOD",  # "Very Good"
            "good": "USED_GOOD",  # "Good"
            "fair": "USED_ACCEPTABLE",  # "Acceptable"
            "acceptable": "USED_ACCEPTABLE",  # "Acceptable"
        },
        "default_condition": "USED_VERY_GOOD",  # "Very Good"
        "required_aspects": ["Brand"],
        "default_aspects": {
            "Brand": "Unbranded",
        },
        "single_value_aspects": ["Colour"],
    },
}


def get_item_type_rules(item_type: str) -> dict:
    """Get the rules for a specific item type."""
    item_type_lower = item_type.lower().strip()

    # Map common variations to standard types
    type_mapping = {
        # Clothing variations
        "clothing": "clothing",
        "clothes": "clothing",
        "apparel": "clothing",
        "t-shirt": "clothing",
        "tshirt": "clothing",
        "shirt": "clothing",
        "dress": "clothing",
        "jacket": "clothing",
        "jeans": "clothing",
        "trousers": "clothing",
        "pants": "clothing",

        # Kitchenware variations
        "kitchenware": "kitchenware",
        "crockery": "kitchenware",
        "mug": "kitchenware",
        "mugs": "kitchenware",
        "cup": "kitchenware",
        "plate": "kitchenware",
        "bowl": "kitchenware",
        "dish": "kitchenware",
        "ceramic": "kitchenware",
        "pottery": "kitchenware",

        # Shoes variations
        "shoes": "shoes",
        "shoe": "shoes",
        "footwear": "shoes",
        "trainers": "shoes",
        "boots": "shoes",
        "heels": "shoes",
        "sandals": "shoes",
        "sneakers": "shoes",

        # Books variations
        "books": "books",
        "book": "books",
        "media": "books",
        "dvd": "books",
        "cd": "books",
        "vinyl": "books",
        "magazine": "books",

        # Electronics variations
        "electronics": "electronics",
        "electronic": "electronics",
        "phone": "electronics",
        "laptop": "electronics",
        "computer": "electronics",
        "camera": "electronics",
        "tablet": "electronics",
        "gadget": "electronics",

        # General
        "general": "general",
        "other": "general",
    }

    # Try to find a match
    standard_type = type_mapping.get(item_type_lower, "general")

    return ITEM_TYPE_RULES.get(standard_type, ITEM_TYPE_RULES["general"])


def normalize_condition_for_type(condition: str, item_type: str) -> str:
    """Normalize condition value based on item type."""
    rules = get_item_type_rules(item_type)
    condition_map = rules["condition_mapping"]

    # Clean up the condition string
    condition_lower = condition.lower().replace("_", " ").replace("-", " ").strip()

    # Try to map to standard condition
    for key, value in condition_map.items():
        if key in condition_lower:
            return value

    # If no match, return the default for this item type
    return rules["default_condition"]


def apply_required_aspects(aspects: dict, item_type: str) -> dict:
    """
    Apply required aspects for the item type.
    Ensures all required fields are present with defaults if needed.
    """
    rules = get_item_type_rules(item_type)

    # Ensure all required aspects are present
    for aspect_name in rules["required_aspects"]:
        if aspect_name not in aspects or not aspects[aspect_name]:
            default_value = rules["default_aspects"].get(aspect_name, "Not Specified")
            aspects[aspect_name] = [default_value]

    # Ensure single-value aspects only have one value
    for aspect_name in rules["single_value_aspects"]:
        if aspect_name in aspects and len(aspects[aspect_name]) > 1:
            # Special handling for Colour - use Multicoloured
            if aspect_name == "Colour":
                aspects[aspect_name] = ["Multicoloured"]
            else:
                # Keep first value
                aspects[aspect_name] = [aspects[aspect_name][0]]

    # Handle Color -> Colour conversion for UK marketplace
    if "Color" in aspects and "Colour" not in aspects:
        aspects["Colour"] = aspects["Color"]
        del aspects["Color"]

    return aspects


def get_default_category_id(item_type: str) -> str:
    """Get the default eBay category ID for an item type."""
    rules = get_item_type_rules(item_type)
    return rules["default_category_id"]
