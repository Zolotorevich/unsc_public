import telebot
from telebot.types import InputFile

import config

bot = telebot.TeleBot(config.telegram_bot_token)

def send_telegram_report(message, disable_sound=False):
    try:
        bot.send_message("323091598", message,
                         disable_notification=disable_sound, parse_mode="HTML")
    except:
        return False
    return True

def send_telegram_message(message, filename, disable_sound=True):
    try:
        # Check for production mode
        if config.production and config.prod_telegram_channel:
            channel = config.telegram_channel_prod
        else:
            channel = config.telegram_channel_test

        # Send message
        bot.send_document(channel, InputFile(filename), caption=message,
                          disable_notification=disable_sound, parse_mode="Markdown")
    except:
        # Report error
        send_telegram_report("FAIL: Can't send TG Message")
        return False
    return True