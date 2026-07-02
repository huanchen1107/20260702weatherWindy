import urllib.request
import urllib.error
import urllib.parse
import json
import os
import ssl

url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0001-001?downloadType=WEB&format=JSON"

class AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Create redirect request using default behavior
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        # Parse hostnames to compare them
        orig_host = urllib.parse.urlparse(req.full_url).hostname
        new_host = urllib.parse.urlparse(newurl).hostname
        # If target host is different, strip Authorization header
        if orig_host != new_host:
            for key in list(new_req.headers.keys()):
                if key.lower() == 'authorization':
                    del new_req.headers[key]
        return new_req

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

try:
    load_env()
    token = os.environ.get("CWA_API_TOKEN")
    if not token:
        raise ValueError("CWA_API_TOKEN not found in environment or .env file.")

    print("Fetching data from CWA API using Authorization header and custom redirect handler...")
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Authorization': token
        }
    )
    
    # Setup opener with our custom redirect handler and SSL bypass
    context = ssl._create_unverified_context()
    opener = urllib.request.build_opener(
        AuthStrippingRedirectHandler(),
        urllib.request.HTTPSHandler(context=context)
    )
    
    with opener.open(req) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    print("Success!")
    print("Top-level keys in JSON:", list(data.keys()))
        
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    try:
        print("Response body:", e.read().decode('utf-8'))
    except Exception as read_err:
        print("Could not read response body:", read_err)
except Exception as e:
    print(f"Error: {e}")
