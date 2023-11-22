import os
import time

import fitz
from selenium import webdriver

import config
from telegramBot import send_telegram_report


# Parent class for documents
class UNDoc:
    def __init__(self, serial, filename):
        self.serial = serial  # S/2023/418
        self.filename = filename  # /fullpath/pdf/S-2023-418.pdf

    # Open PDF, update number of pages and return {title, text, footer}
    def process_PDF(self,
                   text_rectangle=(0, 220, 10000, 720),
                   title_rectangle=(0, 220, 10000, 400)):
        title = ""
        text = ""

        with fitz.open(self.filename) as doc:

            # Get first page text
            page = doc[0]
            text = page.get_text("text", clip=text_rectangle, sort=True)

            # Get title if needed
            if title_rectangle:
                # Get text blocks, find and glue title
                blocks = page.get_text("dict",
                                       flags=11,
                                       clip=title_rectangle,
                                       sort=True)["blocks"]
                for b in blocks:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            stop_words = "I. Введение" in s["text"] or not s["text"].strip()
                            if (s["flags"] == 20 or s["flags"] == 21) and not stop_words:
                                title += s["text"].strip() + " "

            # Generate number of pages
            page_count = str(doc.page_count)
            last_page_digit = page_count[-1:]
            if last_page_digit == "1" and doc.page_count != "11":
                page_count += " страница"
            elif last_page_digit in ["2", "3", "4"] and not (12 <= doc.page_count <= 14):
                page_count += " страницы"
            else:
                page_count += " страниц"

        # Delete double new lines and spaces in text
        text = optimize_text(text)

        # Delete title from text if needed
        if title_rectangle:
            text = text[text.find(title) + len(title):].strip()

        # Generate footer
        footer = "\n\n*" + self.serial + ", " + page_count + "*"

        # Return title and first page text
        return {"title": title.strip(), "text": text, "footer": footer}

# Letter or other type
class UNLetter(UNDoc):
    def description(self):
        # Get title and text from super
        document = UNDoc.process_PDF(self)

        # Generate message title
        title = "*" + document["title"] + "*\n\n"

        # Generate description
        description = trim_paragraphs(document["text"], 2)

        # Return "message text"
        return title + trim_if_needed(description) + document["footer"]

# Resolution
class UNResolution(UNDoc):
    def description(self):
        # Get message raw title, text and footer from super
        document = UNDoc.process_PDF(self)

        # Generate message title
        title = "*" + document["title"] + "*\n\n"

        # Generate description
        description = trim_paragraphs(document["text"], 2,
                                     document['text'].find("Совет Безопасности,") + 21)

        # Return "message text"
        return title + "Совет безопасности,\n\n" + trim_if_needed(description) + document["footer"]

# Draft Resolution
class UNDraftResolution(UNDoc):
    def description(self):
        # Get title and text from super
        document = UNDoc.process_PDF(self)

        # Generate message title
        title = "*Проект резолюции, автор: " + document["title"][:-18] + "*\n\n"

        # Generate description
        description = trim_paragraphs(document["text"], 2,
                                     document['text'].find("Совет Безопасности,") + 21)

        # Return "message text"
        return title + "Совет безопасности,\n\n" + trim_if_needed(description) + document["footer"]

# Transcript
class UNTranscript(UNDoc):
    def description(self):
        # Get text from super
        text_rect = (0, 480, 10000, 600)
        document = UNDoc.process_PDF(self, text_rect, False)

        # Generate message title
        meeting_number = self.serial[self.serial.find(".") + 1:]

        if "resumption" in meeting_number.lower():
            title = "*Стенограмма заседания №" + meeting_number[:-15] + " (продолжение)*\n\n"
        else:
            title = "*Стенограмма заседания №" + meeting_number + "*\n\n"

        # Find agenda
        agenda = document["text"][document["text"].find("Повестка дня") + 12:]

        # Find common agenda themes
        common_themes = ['Угрозы международному миру и безопасности',
                         'Поддержание международного мира и безопасности']
        for theme in common_themes:
            if theme in agenda:
                agenda = theme + "\n\n" + agenda[agenda.find(theme) + len(theme):].strip()

        # Check for letters
        if "Письмо" in agenda:
            agenda = agenda[:agenda.find("Письмо")].strip() + "\n\n" + agenda[agenda.find("Письмо"):].strip()

        # Return "message text"
        return title + "Повестка дня: " + trim_if_needed(agenda) + document["footer"]

# Report
class UNReport(UNDoc):
    def description(self):
        # Get title and text from super
        title_rect = (0, 220, 10000, 400)
        report_rect = (0, 220, 10000, 720)
        document = UNDoc.process_PDF(self, report_rect, title_rect)

        # Generate message title
        separate_index = document["title"].find("Доклад")

        title = "*" + document["title"][separate_index:] + " «" + document["title"][:separate_index - 1] + "»*\n\n"

        # Trim itroduction
        introduction_start = document["text"].find("I. Введение")
        introduction_start = document["text"].find("1.", introduction_start)
        introduction_end = document["text"].find("II.")

        introduction = document["text"][introduction_start + 2:introduction_end]

        # Trim two paragraphs from introduction
        description = trim_paragraphs(introduction.strip(), 2)

        # Return "message text"
        return title + trim_if_needed(description) + document["footer"]

# Council work report
class UNCouncilWorkReport(UNDoc):
    def description(self):
        # Get title and text from super
        document = UNDoc.process_PDF(self, title_rectangle=False)

        # Return "message text"
        return "*Краткий отчёт Генерального секретаря о работе Совета Безопасности*" + document["footer"]

# Generate and return UN Docs objects in [list]
def generateUNDocs(feed):

    # Start Selenium
    browser = selenium_start()

    # Generate UNDocs objects
    list_Of_Docs = []
    downloaded_files = [""]
    for feed_item in feed.entries:

        # Get serial number
        serial = feed_item.title

        # Check if it's agenda and skip iteration
        if "AGENDA" in serial:
            continue

        # Add 'ru/' to url for russian version
        url = feed_item.link[:19] + "ru/" + feed_item.link[19:]

        # Generate filename
        serial_number = serial.replace("/", "-").replace(".", "-").replace(" (", "-")
        filename = f'{config.PDF_dir}{serial_number}.pdf'

        # Download PDF
        if not selenium_download(browser, url, filename, downloaded_files[-1]):
            send_telegram_report(f'ERROR: Timeout for downloading {serial_number} FROM {url}')
            continue

        # Create object
        if "PV" in serial:
            newDoc = UNTranscript(serial, filename)
        elif "RES" in serial:
            newDoc = UNResolution(serial, filename)
        elif "DRAFT RESOLUTION" in feed_item.description:
            newDoc = UNDraftResolution(serial, filename)
        elif "REPORT" in feed_item.description:
            newDoc = UNReport(serial, filename)
        elif "SUMMARY STATEMENT BY THE SECRETARY-GENERAL OF MATTERS" in feed_item.description:
            newDoc = UNCouncilWorkReport(serial, filename)
        else:
            newDoc = UNLetter(serial, filename)

        # Store object
        list_Of_Docs.append(newDoc)

    if config.selenium:
        # Wait a few seconds just in case browser still renaming files
        time.sleep(5)

        # Stop Selenium
        browser.quit()

    if list_Of_Docs:
        return list_Of_Docs

    return False

# Start Selenium
def selenium_start():

    # Check for dev mode
    if not config.selenium:
        return True

    # Prepare driver
    options = webdriver.ChromeOptions()
    profile = {"plugins.plugins_list": [{"enabled": False,
                                         "name": "Chrome PDF Viewer"}],
                                         "download.default_directory": config.PDF_dir,
                                         "download.extensions_to_open": "",
                                         "plugins.always_open_pdf_externally": True}
    options.add_experimental_option("prefs", profile)
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument('--user-agent="Mozilla/5.0"')

    # Start driver
    driver = webdriver.Chrome(options=options)

    # Open dowloads tab
    driver.get("chrome://downloads")

    # Open empty tab
    driver.execute_script("window.open()")

    return driver

def selenium_download(driver, url, filename, previousDownloadedFile):

    # Check for dev mode
    if not config.selenium:
        return True

    # Switch to working tab and open URL
    driver.switch_to.window(driver.window_handles[-1])
    driver.get(url)

    # Switch to downloads tab
    driver.switch_to.window(driver.window_handles[0])

    # Calc timeout
    timeout = time.time() + config.download_timeout_sec

    # Wait for dowload start and complete
    while True:
        try:
            # Get last downloaded filename
            last_downloaded = driver.execute_script("return document.querySelector('downloads-manager').shadowRoot.querySelectorAll('#downloadsList downloads-item')[0].shadowRoot.querySelector('div#content  #file-link').text")

            # Check if it's new
            if last_downloaded != previousDownloadedFile:
                # Get downloaded percentage of last file
                download_percentage = driver.execute_script(
                    "return document.querySelector('downloads-manager').shadowRoot.querySelectorAll('#downloadsList downloads-item')[0].shadowRoot.querySelector('#progress').value")

                # If done, rename file
                if download_percentage == 100:
                    downloaded_filename = driver.execute_script("return document.querySelector('downloads-manager').shadowRoot.querySelectorAll('#downloadsList downloads-item')[0].shadowRoot.querySelector('div#content  #file-link').text")

                    os.rename(config.PDF_dir + downloaded_filename, filename)

                    return True
        except:
            pass

        time.sleep(1)
        if time.time() > timeout:
            # Failed to download
            return False

# Delete double new lines and spaces
def optimize_text(text):

    # Replace new lines with ¶
    optimized_text = text.replace("\n \n","¶").replace("-\n","").replace("\n","")

    # Delete double new lines
    while " ¶ ¶" in optimized_text:
        optimized_text = optimized_text.replace(" ¶ ¶", "¶")

    # Replace ¶ with new line
    optimized_text = optimized_text.replace("¶", "\n\n")

    # Delete double spaces
    while "  " in optimized_text:
        optimized_text = optimized_text.replace("  ", " ")

    return optimized_text.strip()

# Return paragraphs from text
def trim_paragraphs(text, numberOfParagraphs, startPoint=0):

    result = ""

    # Find first paragraph
    end_point = text.find("\n", startPoint)

    # Check it text have one paragraph
    if end_point < 0:
        return text.strip()

    # Find other paragraphs if any
    while end_point >= 0 and numberOfParagraphs >= 1:
        result += text[startPoint:end_point] + "\n"

        startPoint = end_point + 1

        end_point = text.find("\n", startPoint + 1)

        numberOfParagraphs -= 1

    return result.strip()

# Trim text if it's too long for Telegram OR add "..." in the end instead of "," or ":"
def trim_if_needed(text):
    text = text.strip()

    if len(text) > config.telegram_description_maxchar:
        return text[:config.telegram_description_maxchar] + "..."

    if text[-1] == "," or text[-1] == ":":
        return text[:-1] + "..."

    return text