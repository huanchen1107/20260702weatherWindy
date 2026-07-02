import urllib.request
import urllib.parse
import json
import ssl
from backend.app import config

class AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Create standard redirect request
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        # Check hostnames
        orig_host = urllib.parse.urlparse(req.full_url).hostname
        new_host = urllib.parse.urlparse(newurl).hostname
        # If redirecting to a different host (e.g. S3), strip Authorization header
        if orig_host != new_host:
            for key in list(new_req.headers.keys()):
                if key.lower() == 'authorization':
                    del new_req.headers[key]
        return new_req

def fetch_raw_cwa_data() -> dict:
    """
    Fetches raw weather JSON from the CWA API endpoint.
    Sends CWA_API_TOKEN in HTTP Request headers.
    """
    if not config.CWA_API_TOKEN:
        raise ValueError("CWA_API_TOKEN is not configured in environment variables or .env file.")
        
    print(f"CWA Client: Fetching data from {config.CWA_DATA_URL}")
    req = urllib.request.Request(
        config.CWA_DATA_URL,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) WeatherVis/1.0',
            'Authorization': config.CWA_API_TOKEN
        }
    )
    
    # Disable SSL verification for environments with missing root certificates
    context = ssl._create_unverified_context()
    opener = urllib.request.build_opener(
        AuthStrippingRedirectHandler(),
        urllib.request.HTTPSHandler(context=context)
    )
    
    with opener.open(req) as response:
        content = response.read().decode('utf-8')
        return json.loads(content)
