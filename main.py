import os
import re
import json
import time
import html
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==========================================
# CONFIGURATION
# ==========================================

BASE_URL = "https://www.coursesoup.com/"
HISTORY_FILE = "coursesoup_posted.json"
DELAY_SECONDS = 2

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError(
        "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID."
    )

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0"
})


# ==========================================
# POSTING HISTORY
# ==========================================

def load_posted_courses():

    if not os.path.exists(HISTORY_FILE):
        return set()

    with open(HISTORY_FILE, "r", encoding="utf-8") as file:
        return set(json.load(file))


def save_posted_courses(posted_courses):

    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            sorted(posted_courses),
            file,
            ensure_ascii=False,
            indent=2
        )


# ==========================================
# DISCOVER COURSES
# ==========================================

def discover_courses():

    response = session.get(BASE_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    course_urls = {}

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if "/course/" in href:

            course_url = urljoin(BASE_URL, href)
            course_urls[course_url] = True

    return list(course_urls.keys())


# ==========================================
# EXTRACT COURSE INFORMATION
# ==========================================

def extract_course_details(course_url):

    response = session.get(course_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text(" ", strip=True)

    heading = soup.find("h1")

    if not heading:
        return None

    title = heading.get_text(" ", strip=True)

    description_tag = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    description = (
        description_tag.get("content", "").strip()
        if description_tag else ""
    )

    # Verify discount and coupon status

    is_discounted = "100% OFF" in page_text

    is_active = (
        "This coupon is live" in page_text
        and "Coupon active" in page_text
    )

    is_free = re.search(
        r"\bFree\b",
        page_text,
        re.IGNORECASE
    ) is not None

    # Extract coupon code

    coupon_match = re.search(
        r"Coupon code\s+([A-Za-z0-9_-]+)\s+Redemptions left",
        page_text,
        re.IGNORECASE
    )

    if not (
        is_discounted
        and is_active
        and is_free
        and coupon_match
    ):
        return None

    coupon_code = coupon_match.group(1)

    # Extract remaining redemptions

    redemption_match = re.search(
        r"Redemptions left\s*[≈~]?\s*(\d+)",
        page_text,
        re.IGNORECASE
    )

    redemptions = (
        redemption_match.group(1)
        if redemption_match else "Not specified"
    )

    # Extract expiry

    expiry_match = re.search(
        r"Expires in\s+(.+?)\s+Last verified",
        page_text,
        re.IGNORECASE
    )

    expiry = (
        expiry_match.group(1).strip()
        if expiry_match else "Check course page"
    )

    # Extract last verification time

    verified_match = re.search(
        r"Last verified\s+(.+?)(?:Get This Course Free|Affiliate link)",
        page_text,
        re.IGNORECASE
    )

    verified = (
        verified_match.group(1).strip()
        if verified_match else "Not specified"
    )

    return {
        "title": title,
        "description": description,
        "coupon": coupon_code,
        "redemptions": redemptions,
        "expiry": expiry,
        "verified": verified,
        "link": course_url
    }


# ==========================================
# FORMAT TELEGRAM MESSAGE
# ==========================================

def format_message(course):

    title = html.escape(course["title"])
    description = html.escape(course["description"])
    coupon = html.escape(course["coupon"])
    redemptions = html.escape(course["redemptions"])
    expiry = html.escape(course["expiry"])
    verified = html.escape(course["verified"])

    link = html.escape(
        course["link"],
        quote=True
    )

    message = (
        "🎓 <b>FREE UDEMY COURSE</b>\n\n"

        f"<b>{title}</b>\n\n"

        f"{description}\n\n"

        "🎟️ <b>Discount:</b> 100% OFF\n"

        f"🔑 <b>Coupon:</b> <code>{coupon}</code>\n"

        f"🔥 <b>Redemptions left:</b> {redemptions}\n"

        f"⏳ <b>Expires:</b> {expiry}\n"

        f"✅ <b>Last verified:</b> {verified}\n\n"

        f'🔗 <a href="{link}">ENROLL FOR FREE</a>\n\n'

        "<i>Coupon availability can change. "
        "Confirm that Udemy shows ₦0 or $0 before enrolling.</i>"
    )

    return message[:4000]


# ==========================================
# PUBLISH TO TELEGRAM
# ==========================================

def publish_course(course):

    telegram_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        json={
            "chat_id": CHAT_ID,
            "text": format_message(course),
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        },
        timeout=30
    )

    try:
        result = response.json()

    except ValueError:
        raise RuntimeError(
            f"Unexpected Telegram response: HTTP {response.status_code}"
        )

    if not result.get("ok"):

        raise RuntimeError(
            result.get(
                "description",
                f"Telegram error {response.status_code}"
            )
        )

    return True


# ==========================================
# MAIN UPDATE FUNCTION
# ==========================================

def update_bot():

    posted_courses = load_posted_courses()

    print("Checking Course Soup for new courses...\n")

    courses = discover_courses()

    print("Courses discovered:", len(courses))

    print("Previously published
