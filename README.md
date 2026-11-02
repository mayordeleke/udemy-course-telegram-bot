# # Courson Udemy Coupon Bot 🤖

An automated Python bot that collects free Udemy course coupon offers from Courson.xyz and publishes them to a Telegram channel.

## 🚀 Features

- Collects the latest coupon offers from Courson.xyz.
- Extracts Udemy course links and coupon codes.
- Filters available coupon offers.
- Publishes courses automatically to Telegram.
- Prevents duplicate posts.
- Runs automatically using GitHub Actions.

## 🛠️ Technologies

- Python
- Requests
- BeautifulSoup
- Telegram Bot API
- GitHub Actions

## ⚙️ How It Works

1. Fetches coupon offers from Courson.xyz.
2. Filters active coupons with remaining uses.
3. Extracts course information and Udemy links.
4. Checks whether a course has already been published.
5. Sends new offers to the configured Telegram channel.

## 🔐 Environment Variables

The following GitHub Secrets are required:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Never expose your bot token publicly.

## ⏰ Automation

GitHub Actions runs the bot automatically every six hours.

## ⚠️ Disclaimer

Coupon availability may change. A coupon marked as active may expire or become unavailable before redemption.

This project is intended for educational purposes.
