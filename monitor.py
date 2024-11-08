import requests
from urllib.parse import urlparse

def is_site_up(url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False

def is_ssl_valid(url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        response = requests.get(url, verify=True, timeout=10)
        return True
    except requests.exceptions.SSLError:
        return False
    except requests.exceptions.RequestException:
        # If there's a different kind of error, we still want to check SSL
        try:
            parsed = urlparse(url)
            response = requests.get(f"https://{parsed.netloc}", verify=True, timeout=10)
            return True
        except:
            return False
