import asyncio
import json
import os
from typing import OrderedDict
from unittest import result
from wsgiref import headers

import aiohttp
import requests
from asgiref import timeout
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect
from flask import flash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import re

app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'
ascii_lowercase = 'a'#ąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'

csrf = CSRFProtect(app)

@app.route("/")
async def index():
    if not (os.path.isfile("data.json") and os.access("data.json", os.R_OK)):
        with open('data.json', 'w', encoding='utf-8') as f:
            words = await fetch_words()
            definitions = await fetch_definitions(words)
            headlines = {
                word: definition
                for word, definition in zip(words, definitions)
                if definition
                   and not definition.startswith("→")
                   and definition != "KOMENTARZE"
            }
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
        headlines =  json.load(f)
    regex = re.compile(chosenPassword)
    headlinesToDisplayList = [string for string in headlines if re.match(regex,string)]
    headlinesToDelete = []
    for headline in headlinesToDisplayList:
        if len(chosenPassword) != len(headline):
            headlinesToDelete.append(headline)
    headlinesToDisplayList = [x for x in headlinesToDisplayList if x not in headlinesToDelete]
    headlinesToDisplayList = list(OrderedDict.fromkeys(headlinesToDisplayList))
    headlinesToDisplayDict = {}
    for headline in headlinesToDisplayList:
        headlinesToDisplayDict.update({headline:headlines[headline]})
    return render_template('wpisaneHaslo.html',title='Wpisane Haslo',headlinesToDisplay = headlinesToDisplayDict,
                           chosenPassword = chosenPassword)

class PasswordForm(FlaskForm):
    crosswordPassword = StringField('Hasło: ', validators=[DataRequired()])
    submit = SubmitField('Wyślij')


HEADERS = {
    "User-Agent":(
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36 "
    )
}

semaphore = asyncio.Semaphore(15)
semaphore2 = asyncio.Semaphore(15)

async def scrape(session,url):
    async with semaphore:
        try:
            async with session.get(url,headers=HEADERS,timeout=15) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for headline in soup.find_all("a"):
                    app.logger.info(headline)
                    headlines.append(headline.text.replace('\xa0', ' '))
                blacklist = ["Młodzieżowe Słowo Roku","Księgarnia PWN","Czytaj Więcej","SJP","*"
                             ,"słownik języka polskiego sjp","a","b","c","ć","d","e","f","g",
                             "h","i","j","k","l","ł","m","n","o","ó","p","r","s","ś","t","u","w","y","z","ź","ż"
                             ,"najn.","ndpl","nnot","nie osps","nie wsjp","nie sg.","info","lista","komentarze","więcej","\""]
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


async def fetch_words():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for letter in ascii_lowercase:
            url = f"https://sjp.pl/sl/growe/?p={letter}&l=7"
            tasks.append(scrape(session,url))
        results = await asyncio.gather(*tasks)
        results = [ #zamienić kilka list w jedna duza
            x
            for xs in results
            for x in xs
        ]
        results = list(dict.fromkeys(results))
        return results

async def fetch_definitions(words):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for word in words:
            tasks.append(scrape_definition(session,word))
        results = await asyncio.gather(*tasks)
    return results

async def scrape_definition(session,word):
    url = f"https://sjp.pl/{word}"
    async with semaphore2:
        try:
            async with session.get(
                url,
                headers = HEADERS,
                timeout = 10
            ) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html,"html.parser")
                meaning = soup.find("b", string=lambda s: s and "znaczenie" in s.lower())
                if not meaning:
                    return "brak definicji"
                definitionP = meaning.find_parent("p").find_next("p")
                if not definitionP:
                    return "brak definicji"
                app.logger.info(definitionP.getText(strip=True))
                return definitionP.getText(strip=True)
        except Exception as e:
            app.logger.info(e)



