from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os.path
import traceback
import requests
import json, time
from pytz import timezone
from datetime import datetime, timedelta


def composeMessage(dates):

    messageText = ""
    oldDaysDump = {}
    send = False

    try:

        with open('days.txt', 'r') as daysFile:
            oldDaysDump = json.load(daysFile)

        for date in dates.keys():
            if (date not in oldDaysDump.keys()):
                send = True
            else:
                if dates[date] != oldDaysDump[date]:
                    send = True    
                oldDaysDump.pop(date)

        if not oldDaysDump == {}:
            send = True

        if dates == {}:
            os.remove("days.txt")

    except FileNotFoundError:

        if not dates == {}:
            send = True

    if send:
        if dates == {}:
            messageText += "Нет свободных дат"
        else:    
            messageText += "Изменились свободные для записи даты:\n"

            for date in dates:
                messageText += date.split(' ', 1)[-1][:-9] + " — " + str(dates[date]) + " carrera\\(s\\)" + "\n"

            messageText = messageText + \
                "Записаться — [тут](https://www.clubargentinodekart.com.ar/alquiler-de-karting/)\n" + \
                "Инфа о записи и картодромах — [тут](https://k1rovreporting.notion.site/d12ba14c633a46bf806cbf8c4ae0626a)"

    with open('days.txt', 'w') as daysFile:
        json.dump(dates, daysFile)

    return messageText


def sendMessage(messageText, token, chat_id, silence):

    sendMethod = "sendMessage"
    deleteMethod = "deleteMessage"
    updateMethod = "editMessageText"
    sendUrl = f"https://api.telegram.org/bot{token}/{sendMethod}"
    updateUrl = f"https://api.telegram.org/bot{token}/{updateMethod}"
    deleteUrl = f"https://api.telegram.org/bot{token}/{deleteMethod}"
    timeZone = timezone('America/Argentina/Buenos_Aires')
    updateMessage = False
    lastMessage = {}

    if messageText != "":

        try:

            with open('lastMessage.txt', 'r') as lastMessageFile:
                lastMessage = json.load(lastMessageFile)
                today = datetime.now(timeZone).date()
                if lastMessage['ok']:
                    if datetime.fromtimestamp(lastMessage['result']['date'], timezone('America/Argentina/Buenos_Aires')).date() == today:
                        updateMessage = True
                    else:
                        data = {
                            'chat_id': chat_id,
                            'message_id': lastMessage['result']['message_id'],
                        }
                        request = requests.post(deleteUrl, data=data)
                        os.remove("lastMessage.txt")

        except FileNotFoundError:

            pass

        if updateMessage:
            data = {
                'chat_id': chat_id,
                'message_id': lastMessage['result']['message_id'],
                'text': messageText,
                'parse_mode': "MarkdownV2",
            }
            request = requests.post(updateUrl, data=data)
        else:
            data = {
                'chat_id': chat_id,
                'text': messageText,
                'disable_notification': silence,
                'parse_mode': "MarkdownV2",
            }
            request = requests.post(sendUrl, data=data)
            response = json.loads(request.content.decode('utf8'))

            with open('lastMessage.txt', 'w') as lastMessageFile:
                json.dump(response, lastMessageFile)


def parseHours(freeDates,dates):

    for freeDate in freeDates:
        freeDateHTML = freeDate.get_attribute('outerHTML')
        soup = BeautifulSoup(freeDateHTML, 'html.parser')
        elements = soup.findAll('div', {"class":"circlegreen ng-binding"})
        freeDate.click()
        WebDriverWait(driver, 30, poll_frequency=1).until(EC.visibility_of_element_located(
        (By.CLASS_NAME, 'close')), 'Timed out waiting for calendar')
        hours = driver.find_elements(By.CLASS_NAME, 'cturno')
        driver.find_element(By.CLASS_NAME, 'close').click()
        WebDriverWait(driver, 30, poll_frequency=1).until(EC.invisibility_of_element_located(
        (By.CLASS_NAME, 'close')), 'Timed out waiting for calendar')
        for element in elements:
            if len(hours) == 0:
                dates.pop(element['title'])
            else:
                dates[element['title']] = len(hours)


def handleException(handledException):

    with open('error.log', 'a+') as errorLogFile:
        errorLogFile.write("//////////////////////\n"+str(datetime.now())+"\n"+str(handledException))
    sendMessage("Error:\n"+traceback.format_exc(), config["token"], config["errorChatID"],False)
    os.remove("days.txt")
    exit(1)


try:

    with open('bot.config.json', 'r') as configFile:
        config = json.load(configFile)

except FileNotFoundError:

    print("Config file not found")
    exit()

# Settings to never touch
url = "https://www.turnonet.com/2010-club-argentino-de-karting-ac"
timeZone = timezone('America/Argentina/Buenos_Aires')
now = datetime.now(timeZone)
dates = {}
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
driver = webdriver.Chrome(
    ChromeDriverManager(version=config['driverVersion']).install(), chrome_options=chrome_options)

# checking if we are allowed to send message
if now.hour < config["sleepBefore"] or now.hour >= config["sleepAfter"]:
    exit()

# getting current month page
driver.get(url)
WebDriverWait(driver, 30, poll_frequency=1).until(EC.invisibility_of_element_located(
    (By.ID, "prevloader")), 'Timed out waiting for calendar')

# choose service type "ALQUILER DE CARTING" from dropdown menu
select = Select(driver.find_element(By.NAME, 'service'))
select.select_by_value("4942")

# parse current month page
freeDatesCurrentMonth = driver.find_elements(By.CLASS_NAME, 'cal_dia')

try:

    parseHours(freeDatesCurrentMonth,dates)

except Exception as e:

    handleException(e)

# getting next month page
driver.find_element(By.CLASS_NAME, 'arrow-next').click()
WebDriverWait(driver, 30, poll_frequency=1).until(EC.invisibility_of_element_located(
    (By.ID, "prevloader")), 'Timed out waiting for calendar')
time.sleep(3)

# parse next month page
freeDatesNextMonth = driver.find_elements(By.CLASS_NAME, 'cal_dia')

try:

    parseHours(freeDatesNextMonth,dates)

except Exception as e:

    handleException(e)

sendMessage(composeMessage(dates), config["token"], config["chatID"], config["silence"])
