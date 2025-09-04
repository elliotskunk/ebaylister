import base64, requests

CLIENT_ID = "TobiasKu-ellioton-PRD-cd444012e-0af8aae4"
CLIENT_SECRET = "PRD-d444012e2c12-9c50-4384-86c4-37d0"
RUNAME = "Tobias_Kunz-TobiasKu-elliot-qjidzeE"   # e.g. TobiasKunz-TobiasKu-elliot-PRD-123456
CODE = "v^1.1#i^1#p^3#f^0#I^3#r^1#t^Ul41XzI6QjM5NjA4QkI1NkRENTdGNkJFQUU1MTE4NDg3QjlCQkNfMF8xI0VeMjYw"

b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
resp = requests.post(
    "https://api.ebay.com/identity/v1/oauth2/token",
    headers={
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "authorization_code",
        "code": CODE,
        "redirect_uri": RUNAME,
    },
)
print(resp.json())
