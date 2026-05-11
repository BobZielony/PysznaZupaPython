import asyncio
import json
import os

import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect
from flask import flash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import re

app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'
ascii_lowercase = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'

csrf = CSRFProtect(app)

@app.route("/")
async def index():
    if not (os.path.isfile("data.json") and os.access("data.json", os.R_OK)):
        with open('data.json', 'w', encoding='utf-8') as f:
            headlines = await fetch_all()
            json.dump(headlines, f, ensure_ascii=False, indent=4)
    else:
        with open('data.json', 'r', encoding='utf-8') as f:
            headlines = json.load(f)
    return render_template("index.html",title="Strona główna", headlines = headlines)

@app.route("/haslo", methods=['GET', 'POST'])
def haslo():
    form = PasswordForm()
    if form.validate_on_submit():
        with open("wpisaneHaslo.txt", "w") as f:
            f.write(form.crosswordPassword.data)
        return redirect("/wpisaneHaslo")
    return render_template('haslo.html', title='Haslo',form=form)

@app.route("/wpisaneHaslo", methods=['GET', 'POST'])
def wpisaneHaslo():
    with open("wpisaneHaslo.txt") as f:
        chosenPassword = f.read().lower()
    with open('data.json', 'r', encoding='utf-8') as f:
        fromJson = json.load(f)
    headlines = []
    for jsonik in fromJson:
        for headline in jsonik:
            headlines.append(headline)
    regex = re.compile(chosenPassword)
    headlinesToDisplay = [string for string in headlines if re.match(regex,string)]
    return render_template('wpisaneHaslo.html',title='Wpisane Haslo',headlinesToDisplay = headlinesToDisplay,
                           chosenPassword = chosenPassword)

class PasswordForm(FlaskForm):
    crosswordPassword = StringField('Hasło: ', validators=[DataRequired()])
    submit = SubmitField('Wyślij')

def scrape(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    headlines = []
    for headline in soup.find_all("span", class_="text-almost-black underline-offset-8"):
        headlines.append(headline.text.replace('\xa0',' '))
    if "Młodzieżowe Słowo Roku" in headlines:
        headlines.remove("Młodzieżowe Słowo Roku")
    if "Księgarnia PWN" in headlines:
        headlines.remove("Księgarnia PWN")
    if "Czytaj Więcej" in headlines:
        headlines.remove("Czytaj Więcej")
    return headlines

HEADERS = {
    "User-Agent":(
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36 "
    )
}

semaphore = asyncio.Semaphore(2)

async def scrape2(session,url):
    async with semaphore:
        await asyncio.sleep(1)
        try:
            async with session.get(url,headers=HEADERS,timeout=15) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for headline in soup.find_all("span", class_="text-almost-black underline-offset-8"):
                    app.logger.info(headline)
                    headlines.append(headline.text.replace('\xa0', ' '))
                blacklist = ["Młodzieżowe Słowo Roku","Księgarnia PWN","Czytaj Więcej"]
                headlines = [h for h in headlines if h not in blacklist]
                if not headlines:
                    return None
                return headlines
        except asyncio.TimeoutError as e:
            app.logger.info(e)
            return None
        except aiohttp.ClientError as e:
            app.logger.info(e)
            return None
        except Exception as e:
            app.logger.info(e)
            return None


async def fetch_all():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for letter in ascii_lowercase:
            for number in range(1, 3):
                url = f"https://sjp.pwn.pl/sjp/lista/{letter};{number}"
                tasks.append(scrape2(session,url))
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r]
        return results



