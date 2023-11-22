import os
import time

import feedparser

import config
from telegramBot import send_telegram_message, send_telegram_report
from unDocs import generateUNDocs

# Report start
send_telegram_report("ENGAGE", True)

# Read RSS feed
if config.un_RSS_feed:
    UNSC_feed = feedparser.parse(config.RSS_feed_url)
else:
    UNSC_feed = feedparser.parse(config.test_RSS_feed_url)

# Check if RSS received
try:
    getattr(UNSC_feed, "status")
except AttributeError:
    send_telegram_report("FATAL: RSS unavailable")
    exit()

# Check if RSS too old
if time.time() - time.mktime(UNSC_feed.updated_parsed) > config.feed_max_age_sec:
    send_telegram_report("CHECK: RSS old", True)

    # Terminate on production, continue on dev
    if config.production:
        exit()

# Generate unDocs objects
list_of_docs = generateUNDocs(UNSC_feed)

# Check if at least one object exist
if not list_of_docs:
    send_telegram_report("CHECK: No documents to download", True)
    exit()

# Send messages to Telegram
first_message = True
for document in list_of_docs:
    disable_sound = True

    # Check for first message and enable sound notification
    if first_message:
        disable_sound = False
        first_message = False

    # Send message
    send_telegram_message(document.description(), document.filename, disable_sound)

# Delete PDF files
if config.production:
    for file in os.scandir(config.PDF_dir):
        os.remove(file.path)