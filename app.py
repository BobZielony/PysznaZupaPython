from dominate.svg import title
from flask import Flask, render_template, redirect, url_for, session
import sys

from flask_wtf import FlaskForm, CSRFProtect
from flask import flash
from werkzeug.debug.tbtools import HEADER
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
import requests
from bs4 import BeautifulSoup
import json
import io
import os
import asyncio
import aiohttp
app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'
ascii_lowercase = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'

csrf = CSRFProtect(app)

@app.route("/")
async def index():
    headlines = await fetch_all()
    if not (os.path.isfile("data.json") and os.access("data.json", os.R_OK)):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(headlines, f, ensure_ascii=False, indent=4)
    return render_template("index.html",title="Strona główna", headlines = headlines)

@app.route("/haslo", methods=['GET', 'POST'])
def haslo():
    form = PasswordForm()
    if form.validate_on_submit():
        flash('Wybrane hasło: {}'.format(form.crosswordPassword.data))
        return redirect("/wpisaneHaslo")
    return render_template('haslo.html', title='Haslo',form=form)

@app.route("/wpisaneHaslo", methods=['GET', 'POST'])
def wpisaneHaslo():
    return render_template('wpisaneHaslo.html',title='Wpisane Haslo')

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


semaphore = asyncio.Semaphore(10)
HEADERS = {
    "User-Agent":(
        "Mozilla/5.0"
        "(Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36"
        "Chrome/122.0 Safari/537.36"
    )
}
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
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError:
            return None


async def fetch_all():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for letter in ascii_lowercase:
            for number in range(1, 50):
                url = f"https://sjp.pwn.pl/sjp/lista/{letter};{number}"
                tasks.append(scrape2(session,url))
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r]
        return results

wordList = {
    "tung" : "Indonezyjski z pałką",
    "polska" : "Państwo unitarne w Europie Środkowej, położone między Morzem Bałtyckim na północy a Sudetami i Karpatami na południu",
    "błażej" : "Imię męskie pochodzenia łacińskiego. Wywodzi się od słowa „blaesus” - oznaczającego „seplenić”."
 }


