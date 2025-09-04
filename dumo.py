import os, base64, time, json, xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")
REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")

OAUTH_URL   = "https://api.ebay.com/identity/v1/oauth2/token"
TRADING_URL = "https://api.ebay.com/ws/api.dll"
SITE_ID     = "3"     # UK
COMPAT      = "1147"

def get_access_token():
    if not (APP_ID and CERT_ID and REFRESH_TOKEN):
        raise SystemExit("Set EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN in .env")
    basic = base64.b64encode(f"{APP_ID}:{CERT_ID}".encode()).decode()
    headers = {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}
    scopes = " ".join([
        "https://api.ebay.com/oauth/api_scope/sell.account",
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
    ])
    data = {"grant_type":"refresh_token","refresh_token":REFRESH_TOKEN,"scope":scopes}
    r = requests.post(OAUTH_URL, headers=headers, data=data, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def trading_call(call_name: str, xml_body: str, token: str) -> ET.Element:
    headers = {
        "X-EBAY-API-CALL-NAME": call_name,
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPAT,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml; charset=utf-8",
    }
    for attempt in range(1, 6):
        r = requests.post(TRADING_URL, headers=headers, data=xml_body.encode("utf-8"), timeout=60)
        if r.status_code == 503:
            time.sleep(1.5 * attempt); continue
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ack = root.findtext("{urn:ebay:apis:eBLBaseComponents}Ack")
        if ack and ack.lower() == "success":
            return root
        # tolerate warnings; break on fatal errors
        if ack and ack.lower() in ("warning","successwithwarning"):
            return root
        # small backoff on flakiness
        time.sleep(1.5 * attempt)
        if attempt == 5:
            raise RuntimeError(f"{call_name} failed: HTTP {r.status_code}\n{r.text[:500]}")

def get_top_level_categories(token: str):
    # LevelLimit=1 from the *root* (-1) gives the top-level category list
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetCategoriesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <CategorySiteID>{SITE_ID}</CategorySiteID>
  <CategoryParent>-1</CategoryParent>
  <LevelLimit>1</LevelLimit>
  <ViewAllNodes>true</ViewAllNodes>
  <DetailLevel>ReturnAll</DetailLevel>
</GetCategoriesRequest>"""
    root = trading_call("GetCategories", body, token)
    cats = []
    for c in root.findall(".//{urn:ebay:apis:eBLBaseComponents}Category"):
        cid = c.findtext("{urn:ebay:apis:eBLBaseComponents}CategoryID")
        name = c.findtext("{urn:ebay:apis:eBLBaseComponents}CategoryName")
        if cid and name and cid != "-1":
            cats.append({"id": cid, "name": name})
    return cats

def get_subtree(token: str, parent_id: str, level_limit: int = 12):
    # Pull an entire subtree under a given parent
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetCategoriesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <CategorySiteID>{SITE_ID}</CategorySiteID>
  <CategoryParent>{parent_id}</CategoryParent>
  <LevelLimit>{level_limit}</LevelLimit>
  <ViewAllNodes>true</ViewAllNodes>
  <DetailLevel>ReturnAll</DetailLevel>
</GetCategoriesRequest>"""
    root = trading_call("GetCategories", body, token)
    results = []
    ns = "{urn:ebay:apis:eBLBaseComponents}"
    for c in root.findall(f".//{ns}Category"):
        cid = c.findtext(f"{ns}CategoryID")
        name = c.findtext(f"{ns}CategoryName")
        leaf = c.findtext(f"{ns}LeafCategory") == "true"
        parent = c.findtext(f"{ns}CategoryParentID")
        lvl = c.findtext(f"{ns}CategoryLevel")
        if cid and name and cid != parent_id:
            results.append({
                "id": cid,
                "name": name,
                "parentId": parent,
                "level": int(lvl) if lvl and lvl.isdigit() else None,
                "leaf": bool(leaf),
            })
    return results

def main():
    token = get_access_token()
    print("Token OK. Fetching top-level categories…")
    top = get_top_level_categories(token)
    print(f"Top-level count: {len(top)}")

    all_nodes = {}
    for t in top:
        pid = t["id"]
        print(f"Pulling subtree under {pid} — {t['name']}")
        chunk = get_subtree(token, pid)
        for n in chunk:
            all_nodes[n["id"]] = n
        time.sleep(0.3)  # be nice

    # Include the top-level categories, mark them as non-leaf
    for t in top:
        all_nodes[t["id"]] = {
            "id": t["id"], "name": t["name"], "parentId": "-1", "level": 1, "leaf": False
        }

    data = {
        "siteId": SITE_ID,
        "count": len(all_nodes),
        "categories": sorted(all_nodes.values(), key=lambda x: int(x["id"]))
    }
    out = "categories_ebay_gb_trading.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out} with {data['count']} categories")

if __name__ == "__main__":
    main()
