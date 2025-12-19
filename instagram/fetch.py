import time
import random
import requests
import threading
from instagram.parse import parse_reels_from_json

# ==========================
# GLOBAL RATE LIMITER
# ==========================
MAX_REQUESTS_PER_HOUR = 150
SECONDS_PER_HOUR = 3600

_request_times = []
_lock = threading.Lock()

def rate_limit():
    with _lock:
        now = time.time()

        # Remove old requests
        while _request_times and now - _request_times[0] > SECONDS_PER_HOUR:
            _request_times.pop(0)

        if len(_request_times) >= MAX_REQUESTS_PER_HOUR:
            sleep_for = SECONDS_PER_HOUR - (now - _request_times[0]) + random.uniform(5, 15)
            print(f"⏳ Rate limit reached, sleeping {sleep_for:.1f}s")
            time.sleep(sleep_for)

        _request_times.append(time.time())


# ==========================
# SESSION
# ==========================
SESSION = requests.Session()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Mobile Safari/537.36 "
        "Instagram 312.0.0.33.111 Android"
    ),
    "Accept": "application/json",
    "X-IG-App-ID": "936619743392459",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# ==========================
# FETCH
# ==========================
def fetch_reels(username: str):
    rate_limit()

    # Human-like jitter BEFORE request
    time.sleep(random.uniform(1.2, 3.8))

    url = (
        "https://www.instagram.com/api/v1/users/"
        f"web_profile_info/?username={username}"
    )

    try:
        res = SESSION.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException:
        print(f"⚠️ Network error @{username}")
        return []

    # --------------------------
    # HARD FAIL CONDITIONS
    # --------------------------
    if res.status_code in (401, 403, 429):
        print(f"🚫 BLOCKED by Instagram ({res.status_code}). Cooling down.")
        time.sleep(random.uniform(900, 1800))  # 15–30 min
        return []

    if res.status_code != 200:
        print(f"⚠️ Failed @{username} ({res.status_code})")
        return []

    try:
        data = res.json()
    except Exception:
        print("⚠️ Invalid JSON — likely soft block")
        time.sleep(random.uniform(300, 600))
        return []

    # Random idle pause AFTER successful fetch
    if random.random() < 0.12:
        idle = random.uniform(20, 60)
        print(f"😴 Idle pause {idle:.1f}s")
        time.sleep(idle)

    return parse_reels_from_json(data)
