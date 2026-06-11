import asyncio
import json
import os
import random
import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import re
from collections import OrderedDict

app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'

ascii_lowercase = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'
csrf = CSRFProtect(app)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/122.0 Safari/537.36"
    )
}

semaphore = asyncio.Semaphore(2)

MIN_WORD_LEN = 3
GRID_SIZE = 15


# ===================== FLASK =====================

@app.route("/")
async def index():
    if not (os.path.isfile("data.json") and os.access("data.json", os.R_OK)):
        with open('data.json', 'w', encoding='utf-8') as f:
            headlines = await fetch_all()
            json.dump(headlines, f, ensure_ascii=False, indent=4)
    else:
        with open('data.json', 'r', encoding='utf-8') as f:
            headlines = json.load(f)

    return render_template("index.html", headlines=headlines)


@app.route("/haslo", methods=['GET', 'POST'])
def haslo():
    form = PasswordForm()
    if form.validate_on_submit():
        with open("wpisaneHaslo.txt", "w") as f:
            f.write(form.crosswordPassword.data)
        return redirect("/wpisaneHaslo")
    return render_template('haslo.html', form=form)


@app.route("/wpisaneHaslo")
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

    headlinesToDisplay = [h for h in headlines if re.match(regex, h)]

    headlinesToDisplay = [
        x for x in headlinesToDisplay
        if len(x) == len(chosenPassword)
    ]

    headlinesToDisplay = list(OrderedDict.fromkeys(headlinesToDisplay))

    return render_template(
        'wpisaneHaslo.html',
        headlinesToDisplay=headlinesToDisplay,
        chosenPassword=chosenPassword
    )


@app.route("/krzyzowka")
def krzyzowka():
    with open("words.json", encoding="utf-8") as f:
        words = json.load(f)

    sample = random.sample(words, min(10, len(words)))
    grid, placed = generate(sample)

    return render_template("krzyzowka.html", grid=grid, placed=placed)


# ===================== FORM =====================

class PasswordForm(FlaskForm):
    crosswordPassword = StringField('Hasło:', validators=[DataRequired()])
    submit = SubmitField('Wyślij')


# ===================== SCRAPING =====================

def scrape(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    headlines = []
    for h in soup.find_all("span", class_="text-almost-black underline-offset-8"):
        headlines.append(h.text.replace('\xa0', ' '))

    return headlines


async def scrape2(session, url):
    async with semaphore:
        await asyncio.sleep(1)

        try:
            async with session.get(url, headers=HEADERS, timeout=15) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                headlines = []
                for a in soup.find_all("a"):
                    headlines.append(a.text.replace('\xa0', ' '))

                blacklist = {
                    "Młodzieżowe Słowo Roku", "Księgarnia PWN", "Czytaj Więcej"
                }

                headlines = [h for h in headlines if h not in blacklist]

                return headlines or None

        except:
            return None


async def fetch_all():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for letter in ascii_lowercase:
            url = f"https://sjp.pl/sl/growe/?p={letter}"
            tasks.append(scrape2(session, url))

        results = await asyncio.gather(*tasks)
        return [r for r in results if r]


# ===================== GRID =====================

def create_grid():
    return [[" " for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def can_place(grid, word, x, y, index, direction):

    if direction == "h":
        start = x - index
        if start < 0 or start + len(word) > GRID_SIZE:
            return False
    else:
        start = y - index
        if start < 0 or start + len(word) > GRID_SIZE:
            return False

    for i, letter in enumerate(word):

        if direction == "h":
            nx, ny = start + i, y
        else:
            nx, ny = x, start + i

        cell = grid[ny][nx]

        if cell != " " and cell != letter:
            return False

        # blokowanie stykania bokiem TYLKO gdy brak crossing
        if cell == " ":

            if direction == "h":
                if ny > 0 and grid[ny - 1][nx] != " ":
                    return False
                if ny < GRID_SIZE - 1 and grid[ny + 1][nx] != " ":
                    return False

            if direction == "v":
                if nx > 0 and grid[ny][nx - 1] != " ":
                    return False
                if nx < GRID_SIZE - 1 and grid[ny][nx + 1] != " ":
                    return False

    return True


def generate(words):

    grid = create_grid()
    placed = []

    words = [w for w in words if len(w["word"]) >= MIN_WORD_LEN]
    words = sorted(words, key=lambda w: -len(w["word"]))

    if not words:
        return grid, placed

    # pierwsze słowo
    first = words[0]["word"]
    x = (GRID_SIZE - len(first)) // 2
    y = GRID_SIZE // 2

    for i, c in enumerate(first):
        grid[y][x + i] = c

    placed.append({**words[0], "x": x, "y": y, "dir": "h"})

    # reszta
    for w in words[1:]:

        word = w["word"]
        best_move = None

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):

                cell = grid[y][x]
                if cell == " ":
                    continue

                for i, letter in enumerate(word):

                    if letter != cell:
                        continue

                    # horizontal
                    sx, sy = x - i, y
                    if can_place(grid, word, sx, sy, i, "h"):
                        best_move = (sx, sy, i, "h")
                        break

                    # vertical
                    sx, sy = x, y - i
                    if can_place(grid, word, sx, sy, i, "v"):
                        best_move = (sx, sy, i, "v")
                        break

                if best_move:
                    break
            if best_move:
                break

        if best_move:
            x, y, i, direction = best_move

            if direction == "h":
                start = x - i
                for j, c in enumerate(word):
                    grid[y][start + j] = c
            else:
                start = y - i
                for j, c in enumerate(word):
                    grid[start + j][x] = c

            placed.append({**w, "x": x, "y": y, "dir": direction})

    return grid, placed
