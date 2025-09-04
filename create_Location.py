import os, requests, json

TOKEN = os.getenv("EBAY_ACCESS_TOKEN") or "PASTE_ACCESS_TOKEN"  # paste if not in .env

url = "https://api.ebay.com/sell/inventory/v1/location/derby1"

variants = [
    # v1: minimal, GB locale, postcode without space, WAREHOUSE
    ({
        "location": {
            "address": {
                "addressLine1": "40 May Street",
                "city": "Derby",
                "postalCode": "DE223UP",
                "country": "GB",
            }
        },
        "name": "Main Warehouse",
        "merchantLocationStatus": "ENABLED",
        "locationTypes": ["WAREHOUSE"],
    }, "en-GB"),

    # v2: same body, en-US (yes, some UK accounts only accept en-US… because reasons)
    ({
        "location": {
            "address": {
                "addressLine1": "40 May Street",
                "city": "Derby",
                "postalCode": "DE223UP",
                "country": "GB",
            }
        },
        "name": "Main Warehouse",
        "merchantLocationStatus": "ENABLED",
        "locationTypes": ["WAREHOUSE"],
    }, "en-US"),

    # v3: add phone + instructions + site URL
    ({
        "location": {
            "address": {
                "addressLine1": "40 May Street",
                "city": "Derby",
                "postalCode": "DE223UP",
                "country": "GB",
            }
        },
        "name": "Main Warehouse",
        "merchantLocationStatus": "ENABLED",
        "locationTypes": ["WAREHOUSE"],
        "phone": "+447722207381",
        "locationInstructions": "Main warehouse",
        "locationWebUrl": "https://ramvolt.com",
    }, "en-GB"),
]

for body, lang in variants:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": lang,
        # Marketplace header usually not required for this endpoint, but harmless:
        # "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    r = requests.put(url, headers=headers, json=body, timeout=30)
    print("\n=== Attempt with Content-Language:", lang, "===")
    print("Status:", r.status_code)
    print("Body  :", r.text)
    if r.ok:
        break

# Verify creation
r = requests.get(
    "https://api.ebay.com/sell/inventory/v1/location",
    headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    timeout=30,
)
print("\n=== Verify locations ===")
print("Status:", r.status_code)
print(r.text)
