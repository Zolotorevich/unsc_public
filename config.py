import os

# RSS feed
RSS_feed_url = "https://undocs.org/rss/scdocs.xml"

# RSS maximum age
feed_max_age_sec = 12 * 60 * 60

# PDF folder
PDF_dir = os.path.abspath(os.path.dirname(__file__)) + "/pdf/"

# Selenium download timeout
download_timeout_sec = 60

# Telegram bot
telegram_bot_token = "SECRET"
telegram_channel_prod = "@unsc_mail"

# Max symbols for description in Telegram message
telegram_description_maxchar = 750

# Debug mode
production = False
selenium = False
un_RSS_feed = True
prod_telegram_channel = False
test_RSS_feed_url = "https://zolotorevich.com/dev/unsc_mail/scdocs.xml"
telegram_channel_test = "@zrdevru"