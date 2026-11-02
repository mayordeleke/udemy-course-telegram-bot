import os
import json
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from html import escape

BASE_URL = "https://courson.xyz"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

POSTED_FILE = "posted_courses.json"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})


def load_posted_courses():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))

    return set()


def save_posted_courses(posted_courses):
    with open(POSTED_FILE, "w", encoding="utf-8") as file:
        json.dump(
            sorted(posted_courses),
            file,
            ensure_ascii=False,
            indent=2
        )


def get_latest_coupons(offset=0):
    response = session.post(
        f"{BASE_URL}/load-more-coupons",
        json={"filters": {}, "offset": offset},
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    return data.get("coupons", []), data.get("total_count", 0)


def get_course_details(coupon):
    slug = coupon.get("id_name")

    if not slug:
        return None

    claim_url = f"{BASE_URL}/claim/{slug}"

    response = session.get(claim_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    coupon_element = soup.find(id="couponCode")

    coupon_code = (
        coupon_element.get_text(strip=True)
        if coupon_element
        else coupon.get("coupon_code")
    )

    course_link = None

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        parsed = urlparse(href)

        if (
            parsed.netloc.lower() in {"udemy.com", "www.udemy.com"}
            and parsed.path.lower().startswith("/course/")
        ):
            course_link = href
            break

        for values in parse_qs(parsed.query).values():
            for value in values:
                decoded = unquote(value)
                destination = urlparse(decoded)

                if (
                    destination.netloc.lower()
                    in {"udemy.com", "www.udemy.com"}
                    and destination.path.lower().startswith("/course/")
                ):
                    course_link = decoded
                    break

            if course_link:
                break

        if course_link:
            break

    if not course_link:
        return None

    return {
        "title": coupon.get("title", "Unknown course"),
        "coupon_code": coupon_code,
        "course_link": course_link,
        "claim_page": claim_url,
        "remaining_uses": coupon.get("coupon_uses_remaining")
    }


def format_telegram_post(course):
    title = escape(course["title"])
    coupon_code = escape(course["coupon_code"] or "Not available")
    course_link = escape(course["course_link"], quote=True)

    return (
        "📚 <b>FREE UDEMY COURSE</b>\n\n"
        f"🎓 <b>{title}</b>\n\n"
        f"🎟️ Coupon Code: <code>{coupon_code}</code>\n\n"
        f'🔗 <a href="{course_link}">Claim Your Free Course</a>\n\n'
        "⚡ Hurry! Coupon availability is limited.\n\n"
        "<i>Coupon availability may change. Check the offer on Udemy.</i>"
    )


def publish_course(course, posted_courses):
    course_id = course["claim_page"]

    if course_id in posted_courses:
        print("Already published:", course["title"])
        return False

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": format_telegram_post(course),
            "parse_mode": "HTML"
        },
        timeout=30
    )

    result = response.json()

    if result.get("ok"):
        posted_courses.add(course_id)
        save_posted_courses(posted_courses)

        print("Published:", course["title"])
        return True

    print("Telegram error:", result.get("description"))
    return False


def main():
    posted_courses = load_posted_courses()

    all_coupons = []
    offset = 0

    print("Collecting coupons from Courson...")

    while True:
        coupons, total_count = get_latest_coupons(offset)

        if not coupons:
            break

        all_coupons.extend(coupons)
        offset += len(coupons)

        print(f"Collected {len(all_coupons)} coupons")

        if offset >= total_count:
            break

    print("Total collected:", len(all_coupons))

    published_count = 0
    seen_course_paths = set()

    for coupon in all_coupons:

        if coupon.get("status_label") != "Live":
            continue

        if int(coupon.get("coupon_uses_remaining") or 0) <= 0:
            continue

        try:
            course = get_course_details(coupon)

            if not course:
                continue

            course_path = urlparse(
                course["course_link"]
            ).path.rstrip("/")

            if course_path in seen_course_paths:
                continue

            seen_course_paths.add(course_path)

            if publish_course(course, posted_courses):
                published_count += 1

            time.sleep(2)

        except Exception as error:
            print("Error processing coupon:", error)

    print("Finished!")
    print("New courses published:", published_count)


if __name__ == "__main__":
    main()
