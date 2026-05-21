import asyncio
import json
import os
from typing import OrderedDict
import random
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
    headlinesToDelete = []
    for headline in headlinesToDisplay:
        if len(chosenPassword) != len(headline):
            headlinesToDelete.append(headline)
    headlinesToDisplay = [x for x in headlinesToDisplay if x not in headlinesToDelete]
    headlinesToDisplay = list(OrderedDict.fromkeys(headlinesToDisplay))
    return render_template('wpisaneHaslo.html',title='Wpisane Haslo',headlinesToDisplay = headlinesToDisplay,
                           chosenPassword = chosenPassword)

@app.route("/krzyzowka")
def krzyzowka():

    with open("words.json", encoding="utf-8") as f:
        words = json.load(f)

    sample = random.sample(words, 10)

    grid, placed = generate(sample)

    return render_template(
        "krzyzowka.html",
        grid=grid,
        placed=placed
    )

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
                for headline in soup.find_all("a"):
                    app.logger.info(headline)
                    headlines.append(headline.text.replace('\xa0', ' '))
                blacklist = ["Młodzieżowe Słowo Roku","Księgarnia PWN","Czytaj Więcej","SJP","*"
                             ,"słownik języka polskiego sjp","a","b","c","ć","d","e","f","g",
                             "h","i","j","k","l","ł","m","n","o","ó","p","r","s","ś","t","u","w","y","z","ź","ż"
                             ,"najn.","ndpl","nnot","nie osps","nie wsjp","nie sg.","info","lista","komentarze","więcej","\""]
                headlines = [h for h in headlines    if h not in blacklist]
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
            url = f"https://sjp.pl/sl/growe/?p={letter}"
            tasks.append(scrape2(session,url))
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r]
        return results


# ===================== NEW IMPORT / CONFIG =====================

MIN_WORD_LEN = 3
GRID_SIZE = 15


# ===================== GRID =====================

def create_grid():
    return [[" " for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


# ===================== NEW: VALIDATION =====================

def is_valid_position(grid, x, y):

    directions = [
        (1, 0), (-1, 0),
        (0, 1), (0, -1)
    ]

    for dx, dy in directions:
        nx, ny = x + dx, y + dy

        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:

            if grid[ny][nx] != " ":
                return False

    return True


# ===================== PLACE CHECK =====================

def can_place(grid, word, x, y, index, direction):

    # 1. zakres
    if direction == "h":
        start = x - index
        if start < 0 or start + len(word) > GRID_SIZE:
            return False
    else:
        start = y - index
        if start < 0 or start + len(word) > GRID_SIZE:
            return False

    # 2. sprawdzanie liter + sąsiedztwa
    for i, letter in enumerate(word):

        if direction == "h":
            nx, ny = start + i, y
        else:
            nx, ny = x, start + i

        cell = grid[ny][nx]

        # konflikt liter
        if cell != " " and cell != letter:
            return False

        # 🔥 KLUCZ: blokujemy „dotykanie bokiem”
        if cell == " ":

            # sprawdź czy NIE tworzy się boczne słowo
            if direction == "h":
                if (ny > 0 and grid[ny-1][nx] != " ") or \
                   (ny < GRID_SIZE-1 and grid[ny+1][nx] != " "):
                    return False

            if direction == "v":
                if (nx > 0 and grid[ny][nx-1] != " ") or \
                   (nx < GRID_SIZE-1 and grid[ny][nx+1] != " "):
                    return False

    return True


# ===================== PLACE WORD =====================

def place(grid, word, x, y, index, direction):

    if direction == "h":
        start = x - index
        for i, letter in enumerate(word):
            grid[y][start + i] = letter

    else:
        start = y - index
        for i, letter in enumerate(word):
            grid[start + i][x] = letter


# ===================== GENERATOR (UPGRADED) =====================

def generate(words):
    connected = False
    grid = create_grid()
    placed = []

    words = [w for w in words if len(w["word"]) >= MIN_WORD_LEN]
    words = sorted(words, key=lambda w: -len(w["word"]))

    # ===================== 1. pierwsze słowo =====================

    first = words[0]["word"]

    x = (GRID_SIZE - len(first)) // 2
    y = GRID_SIZE // 2

    for i, c in enumerate(first):
        grid[y][x + i] = c

    placed.append({
        **words[0],
        "x": x,
        "y": y,
        "dir": "h"
    })

    # ===================== 2. reszta słów =====================

    for w in words[1:]:

        word = w["word"]
        best_move = None

        # ===================== SZUKANIE PRZECIĘĆ =====================

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):

                cell = grid[y][x]
                if cell == " ":
                    continue

                for i, letter in enumerate(word):

                    if letter != cell:
                        continue

                    # ---------- poziomo ----------
                    start_x = x - i
                    start_y = y

                    if can_place(grid, word, start_x, start_y, i, "h"):
                        best_move = (start_x, start_y, i, "h")
                        break

                    # ---------- pionowo ----------
                    start_x = x
                    start_y = y - i

                    if can_place(grid, word, start_x, start_y, i, "v"):
                        best_move = (start_x, start_y, i, "v")
                        break

                if best_move:
                    break

            if best_move:
                break

        # ===================== WSTAW =====================

        if best_move:

            x, y, i, direction = best_move
            place(grid, word, x, y, i, direction)

            placed.append({
                **w,
                "x": x,
                "y": y,
                "dir": direction
            })

        # jeśli brak przecięcia → IGNORUJ (to normalne)
        else:
            continue

    return grid, placed

