import asyncio
import json
import os
import re
import aiohttp
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect
from flask_wtf import FlaskForm, CSRFProtect
from urllib3.util import url
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from typing import OrderedDict
app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'
ascii_lowercase = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'
'''
ascii_lowercaseDict = {
    'a' : 82,
    'ą' : 1,
    'b' : 85,
    'c' : 82,
    'ć' : 2,
    'd' : 101,
    'e' : 42,
    'ę' : 1,
    'f' : 50,
    'g' : 63,
    'h' : 38,
    'i' : 34,
    'j' : 28,
    'k' : 161,
    'l' : 45,
    'ł' : 12,
    'm' : 100,
    'n' : 115,
    'ń' : 1,
    'o' : 122,
    'ó' : 1,
    'p' : 333,
    'r' : 103,
    's' : 185,
    'ś' : 16,
    't' : 76,
    'u' : 51,
    'w' : 145,
    'x' : 1,
    'y' : 1,
    'z' : 130,
    'ź' : 1,
    'ż' : 10
}

'''
ascii_lowercaseDict = {
    'a' : 8820,
    'b' : 10220,
    'c' : 7980,
    'ć' : 1,
    'd' : 9660,
    'e' : 3920,
    'f' : 4480,
    'g' : 6720,
    'h' : 4060,
    'i' : 2940,
    'j' : 3220,
    'k' : 16100,
    'l' : 4900,
    'ł' : 1540,
    'm' : 11620,
    'n' : 9380,
    'o' : 8960,
    'ó' : 1,
    'p' : 28000,
    'r' : 8960,
    's' : 18900,
    'ś' : 1540,
    't' : 7840,
    'u' : 3640,
    'w' : 12880,
    'y' : 1,
    'z' : 9240,
    'ź' : 1,
    'ż' : 1400
}

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

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
                   and not definition.startswith("- zob.")
                   and definition != "KOMENTARZE"
                   and definition != "brak definicji"
                   and definition != "POWIĄZANE HASŁA"
                   and definition != "-"
            }
            json.dump(headlines, f, ensure_ascii=False, indent=4)
    else:
        with open('data.json', 'r', encoding='utf-8') as f:
            headlines = json.load(f)
    if not (os.path.isfile("crossword.index") and os.access("crossword.index", os.R_OK)):
        await buildDatabase()
    return render_template("index.html", headlines = headlines)

@app.route("/haslo", methods=['GET', 'POST'])
def haslo():
    form = PasswordForm()
    if form.validate_on_submit():
        with open("wpisaneHaslo.txt", "w") as f:
            f.write(form.crosswordPassword.data)
        return redirect("/wpisaneHaslo")
    return render_template('haslo.html',form=form)

@app.route("/definicja", methods=['GET', 'POST'])
def definicja():
    form = DefinitionForm()
    if form.validate_on_submit():
        with open("wpisanaDefinicja.txt", "w") as f:
            f.write(form.crosswordPassword.data)
        return redirect("/wpisanaDefinicja")
    return render_template('definicja.html',form=form)

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
    return render_template('wpisaneHaslo.html',headlinesToDisplay = headlinesToDisplayDict,
                           chosenPassword = chosenPassword)

@app.route("/wpisanaDefinicja", methods=["GET","POST"])
def wpisanaDefinicja():
    with open("wpisanaDefinicja.txt") as f:
        chosenDefinition = f.read().lower()
    index = faiss.read_index(
        "crossword.index"
    )

    with open("crossword_data.pkl", "rb") as f:
        data = pickle.load(f)

    query_vector = model.encode(
        [chosenDefinition]
    ).astype("float32")

    distances, indices = index.search(
        query_vector,
        5
    )

    results = []
    for i, idx in enumerate(indices[0]):
        results.append({
            "word": data["words"][idx],
            "definition": data["definitions"][idx],
            "distance": float(distances[0][i])
        })
    return render_template('wpisanaDefinicja.html', results=results,
                           chosenDefinition=chosenDefinition)



class PasswordForm(FlaskForm):
    crosswordPassword = StringField('Hasło: ', validators=[DataRequired()])
    submit = SubmitField('Wyślij')

class DefinitionForm(FlaskForm):
    crosswordPassword = StringField('Definicja: ', validators=[DataRequired()])
    submit = SubmitField('Wyślij')

HEADERS = {
    "User-Agent":(
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36 "
    )
}

semaphore = asyncio.Semaphore(2)
semaphore2 = asyncio.Semaphore(5)

async def scrape(session,url):
    async with semaphore:
        try:
            async with session.get(url,headers=HEADERS,timeout=15) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for div in soup.find_all("div",{"class": "col-ms-6"}):
                    ul = div.find("ul")
                    for a in ul.findAll("li"):
                        headline = a.extract()
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
    async with (aiohttp.ClientSession() as session):
        for letter in ascii_lowercaseDict:
            counter = 0
            while counter <= ascii_lowercaseDict[letter]:
                url = f"https://wordlist.eu/slowa/na-litere,{letter}/{counter}"
                tasks.append(scrape(session, url))
                counter += 140
            '''for number in range(1,ascii_lowercaseDict[letter]+1):
                url = f"https://sjp.pwn.pl/sjp/lista/{letter};{number}"
                tasks.append(scrape(session,url))'''
        results = await asyncio.gather(*tasks)
        results = [
            x
            for x in results
            if x is not None
        ]
        results = [  # zamienić kilka list w jedna duza
            x
            for xs in results
            for x in xs
        ]
        results.sort()
        #results = list(dict.fromkeys(results))
        return results

async def fetch_definitions(words):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for word in words:
            tasks.append(scrape_definition(session,word))
        results = await asyncio.gather(*tasks)
    return results

async def scrape_definition(session,word):
    url = f"https://wordlist.eu/slowo/{word}"
    async with (semaphore2):
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
                title = soup.find("dt",{"class" : "h2" })
                if not title:
                    app.logger.info("brak definicji")
                    return "brak definicji"
                definition = title.find_next("dd").getText(strip=True)
                app.logger.info(definition)
                return definition
                '''title = soup.find("span", {"class":"tytul"})
                if not title:
                    return "brak definicji"
                definitionP = title.find_parent("div").find_parent("div").find_next("ol").find_next("li")
                for i in definitionP.findAll("i"):
                    i.replaceWith("  - %s " % i.string)
                if not definitionP:
                    return "brak definicji"
                definitionPText = definitionP.getText(strip=True
                                           ).replace("«","").replace("»"," ")
                definitionPTextHead,sep,tail = definitionPText.partition("•")
                app.logger.info(definitionPTextHead)
                return definitionPTextHead'''
        except asyncio.TimeoutError as e:
            app.logger.info(e)
            return None
        except aiohttp.ClientError as e:
            app.logger.info(e)
            return None
        except Exception as e:
            app.logger.info(e)

async def buildDatabase():
    with open('data.json', 'r', encoding='utf-8') as f:
        jsonik = json.load(f)
    words = list(jsonik.keys())
    definitions = list(jsonik.values())

    embeddings = model.encode(definitions, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    faiss.write_index(index, "crossword.index")

    with open("crossword_data.pkl", "wb") as f:
        pickle.dump(
            {
                "words": words,
                "definitions": definitions
            },
            f
        )
