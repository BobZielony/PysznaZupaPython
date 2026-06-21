import asyncio
import json
import os
import random
import re
import aiohttp
import faiss
import pickle
import time
import numpy as np
import secrets
from sentence_transformers import SentenceTransformer
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from flask_wtf import CSRFProtect
from typing import OrderedDict

app = Flask(__name__)
# Klucz do chronienia danych użytkownika
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
csrf = CSRFProtect(app)

# Model wykorzystywany do semantycznego wyszukiwania definicji
model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# Zmienne używane do przechodzenia przez podstrony słowników, magiczne liczby w słownikach (pytonowych) używane są do przechodzenia po podstronach dla liter

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
    'a': 8820,
    'b': 10220,
    'c': 7980,
    'ć': 1,
    'd': 9660,
    'e': 3920,
    'f': 4480,
    'g': 6720,
    'h': 4060,
    'i': 2940,
    'j': 3220,
    'k': 16100,
    'l': 4900,
    'ł': 1540,
    'm': 11620,
    'n': 9380,
    'o': 8960,
    'ó': 1,
    'p': 28000,
    'r': 8960,
    's': 18900,
    'ś': 1540,
    't': 7840,
    'u': 3640,
    'w': 12880,
    'y': 1,
    'z': 9240,
    'ź': 1,
    'ż': 1400
}


@app.route("/")
async def index():
    '''
    Słowa i definicje są scrapeowane tylko jeśli nie jest już zapisany plik,
    tak samo z indexem dla modelu
    '''
    if not (os.path.isfile("data.json") and os.access("data.json", os.R_OK)):
        with open('data.json', 'w', encoding='utf-8') as f:
            words = await fetch_words()
            definitions = await fetch_definitions(words)
            headlines = {
                word: definition
                for word, definition in zip(words, definitions)
                if definition
                   # usuwanie "definicji" których nie da się nie pobierać ze stron
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
    return render_template("index.html", headlines=headlines)


@app.route("/haslo", methods=['GET', 'POST'])
def haslo():
    '''
    Podane przez użytkownika hasło jest compilowane do regexu,
    następnie w bazie wyszukiwane są wszystkie pasujące słowa
    '''
    headlinesToDisplayDict = None
    chosenPassword = None
    headlines = loadWords()
    if request.method == "POST":
        chosenPassword = request.form.get("word")
        regex = re.compile(chosenPassword)
        headlinesToDisplayList = [string for string in headlines if re.match(regex, string)]
        headlinesToDelete = []
        for headline in headlinesToDisplayList:
            if len(chosenPassword) != len(headline):
                headlinesToDelete.append(headline)
        headlinesToDisplayList = [x for x in headlinesToDisplayList if x not in headlinesToDelete]
        headlinesToDisplayList = list(OrderedDict.fromkeys(headlinesToDisplayList))
        headlinesToDisplayDict = {}
        for headline in headlinesToDisplayList:
            headlinesToDisplayDict.update({headline: headlines[headline]})
    return render_template('haslo.html', headlinesToDisplay=headlinesToDisplayDict,
                           chosenPassword=chosenPassword)


@app.route("/definicja", methods=['GET', 'POST'])
def definicja():
    '''
    Podana przez użytkownika definicja wyszukiwana jest w wygenerowanych wcześniej indeksach
    '''
    chosenDefinition = None
    results = None
    if request.method == "POST":
        chosenDefinition = request.form.get("definition")

        index = faiss.read_index(
            "crossword.index"
        )

        with open("crossword_data.pkl", "rb") as f:
            data = pickle.load(f)

        query_vector = model.encode(
            [chosenDefinition],
            normalize_embeddings=True
        ).astype("float32")

        distances, indices = index.search(
            query_vector,
            5
        )

        results = []
        for i, idx in enumerate(indices[0]):
            similiarity = float(distances[0][i])
            percent = max(0, similiarity) * 100
            results.append({
                "word": data["words"][idx],
                "definition": data["definitions"][idx],
                "similiarity": round(percent, 1)
            })
    return render_template('definicja.html', results=results,
                           chosenDefinition=chosenDefinition)


@app.route("/krzyzowka", methods=['GET', 'POST'])
def krzyzowka():
    '''
    Generowanie krzyzowki oraz sprawdzenie poprawnosci odpowiedzi wpisanych przez uzytkownika
    '''
    width = int(request.form.get('width', 15))
    height = int(request.form.get('height', 15))
    max_words = int(request.form.get('max_words', 8))
    width = max(5, min(width, 50))
    height = max(5, min(height, 50))
    max_words = max(1, min(max_words, 100))

    words_dict = loadWords()
    crossword = None
    user_grid = None
    message = None
    error = None

    if 'new_crossword' in request.form:
        for _ in range(5):
            crossword = crossword_backtrack(words_dict, width, height, max_words=max_words)
            if crossword is not None:
                break
        if crossword is None:
            error = "Nie udało się wygenerować krzyżówki. Spróbuj innych parametrów."
            return render_template('krzyzowka.html', error=error, crossword=None)
    elif request.method == 'POST' and request.form.get('crossword_data'):
        crossword = json.loads(request.form['crossword_data'])
        user_grid = [[None for _ in range(crossword['width'])] for _ in range(crossword['height'])]
        for r in range(crossword['height']):
            for c in range(crossword['width']):
                if crossword['grid'][r][c] is not None:
                    val = request.form.get(f'cell-{r}-{c}', '').upper()
                    if val:
                        user_grid[r][c] = val
        if request.form.get('solution_data'):
            correct_solution = json.loads(request.form['solution_data'])
            all_correct = True
            for r in range(crossword['height']):
                for c in range(crossword['width']):
                    if crossword['grid'][r][c] is not None:
                        user_val = user_grid[r][c] if user_grid[r][c] else ''
                        expected = correct_solution[r][c]
                        if user_val != expected:
                            all_correct = False
            message = "Gratulacje! Wszystkie hasła poprawne." if all_correct else "Niektóre litery są błędne."
    else:
        for _ in range(5):
            crossword = crossword_backtrack(words_dict, width, height, max_words=max_words)
            if crossword is not None:
                break
        if crossword is None:
            error = "Nie udało się wygenerować krzyżówki. Spróbuj innych parametrów."
            return render_template('krzyzowka.html', error=error, crossword=None)

    solution_json = json.dumps(crossword['solution'])
    crossword_json = json.dumps(crossword, ensure_ascii=False)

    return render_template('krzyzowka.html',
                           crossword=crossword,
                           crossword_json=crossword_json,
                           solution_json=solution_json,
                           user_grid=user_grid,
                           message=message)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36 "
    )
}

semaphore = asyncio.Semaphore(2)
semaphore2 = asyncio.Semaphore(5)


async def scrape(session, url):
    async with semaphore:
        try:
            async with session.get(url, headers=HEADERS, timeout=15) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for div in soup.find_all("div", {"class": "col-ms-6"}):
                    ul = div.find("ul")
                    for a in ul.findAll("li"):
                        headline = a.extract()
                        app.logger.info(headline)
                        headlines.append(headline.text.replace('\xa0', ' '))
                blacklist = ["Młodzieżowe Słowo Roku", "Księgarnia PWN", "Czytaj Więcej", "SJP", "*"
                    , "słownik języka polskiego sjp", "a", "b", "c", "ć", "d", "e", "f", "g",
                             "h", "i", "j", "k", "l", "ł", "m", "n", "o", "ó", "p", "r", "s", "ś", "t", "u", "w", "y",
                             "z", "ź", "ż"
                    , "najn.", "ndpl", "nnot", "nie osps", "nie wsjp", "nie sg.", "info", "lista", "komentarze",
                             "więcej", "\""]
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
        # results = list(dict.fromkeys(results))
        return results


async def fetch_definitions(words):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for word in words:
            tasks.append(scrape_definition(session, word))
        results = await asyncio.gather(*tasks)
    return results


async def scrape_definition(session, word):
    url = f"https://wordlist.eu/slowo/{word}"
    async with (semaphore2):
        try:
            async with session.get(
                    url,
                    headers=HEADERS,
                    timeout=10
            ) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                title = soup.find("dt", {"class": "h2"})
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


def loadWords():
    with open("data.json", 'r', encoding='utf-8') as f:
        jsonDict = json.load(f)
    return jsonDict


async def buildDatabase():
    jsonik = loadWords()

    words = list(jsonik.keys())
    definitions = list(jsonik.values())

    embeddings = model.encode(definitions, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
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


def crossword_backtrack(words_dict, width, height, max_words=None, time_limit=5):
    if max_words is None:
        max_words = min(len(words_dict), (width * height) // 3)
    else:
        max_words = min(max_words, len(words_dict))

    start_time = time.time()

    items = list(words_dict.items())
    random.shuffle(items)
    items.sort(key=lambda x: len(x[0]), reverse=True)
    words_list = [(w.upper(), d) for w, d in items]

    best_placed = []
    best_grid = None
    attempts = 15

    for _ in range(attempts):
        if time.time() - start_time > time_limit:
            break

        grid = [[None for _ in range(width)] for _ in range(height)]
        placed = []

        def can_place(word, r, c, dr, dc):
            if dr == 0:
                if c < 0 or c + len(word) > width: return False
                if c > 0 and grid[r][c - 1] is not None: return False
                if c + len(word) < width and grid[r][c + len(word)] is not None: return False
            else:
                if r < 0 or r + len(word) > height: return False
                if r > 0 and grid[r - 1][c] is not None: return False
                if r + len(word) < height and grid[r + len(word)][c] is not None: return False
            for i, ch in enumerate(word):
                nr, nc = r + i * dr, c + i * dc
                cell = grid[nr][nc]
                if cell is not None and cell != ch: return False
                if cell is not None: continue
                if dr == 0:
                    if nr > 0 and grid[nr - 1][nc] is not None: return False
                    if nr < height - 1 and grid[nr + 1][nc] is not None: return False
                else:
                    if nc > 0 and grid[nr][nc - 1] is not None: return False
                    if nc < width - 1 and grid[nr][nc + 1] is not None: return False
            return True

        def place_word(word, r, c, dr, dc, defin):
            direction = 'across' if dr == 0 else 'down'
            placed.append((word, defin, direction, r, c))
            for i, ch in enumerate(word):
                nr, nc = r + i * dr, c + i * dc
                grid[nr][nc] = ch

        # Pierwsze słowo
        first_word, first_def = random.choice(words_list)
        if len(first_word) > width:
            suitable = [(w, d) for w, d in words_list if len(w) <= width]
            if not suitable: continue
            first_word, first_def = random.choice(suitable)
        start_r = height // 2
        start_c = (width - len(first_word)) // 2
        place_word(first_word, start_r, start_c, 0, 1, first_def)

        # Przecięcia
        changed = True
        while changed and len(placed) < max_words:
            if time.time() - start_time > time_limit:
                break
            changed = False
            unused = [(w, d) for w, d in words_list if w not in [pw[0] for pw in placed]]
            random.shuffle(unused)
            for word, defin in unused:
                if len(placed) >= max_words or time.time() - start_time > time_limit:
                    break
                placed_copy = placed[:]
                random.shuffle(placed_copy)
                placed_success = False
                for pw, pdef, pdir, pr, pc in placed_copy:
                    i_indices = list(range(len(word)))
                    random.shuffle(i_indices)
                    for i in i_indices:
                        j_indices = list(range(len(pw)))
                        random.shuffle(j_indices)
                        for j in j_indices:
                            if word[i] == pw[j]:
                                if pdir == 'across':
                                    new_r = pr - i
                                    new_c = pc + j
                                    dr, dc = 1, 0
                                else:
                                    new_r = pr + j
                                    new_c = pc - i
                                    dr, dc = 0, 1
                                if can_place(word, new_r, new_c, dr, dc):
                                    place_word(word, new_r, new_c, dr, dc, defin)
                                    placed_success = True
                                    changed = True
                                    break
                        if placed_success: break
                    if placed_success: break

        # Wypełnianie luk
        if time.time() - start_time < time_limit:
            unused = [(w, d) for w, d in words_list if w not in [pw[0] for pw in placed]]
            unused.sort(key=lambda x: len(x[0]))
            for word, defin in unused:
                if len(placed) >= max_words or time.time() - start_time > time_limit:
                    break
                placed_here = False
                for r in range(height):
                    for c in range(width):
                        if grid[r][c] is None and can_place(word, r, c, 0, 1):
                            place_word(word, r, c, 0, 1, defin)
                            placed_here = True
                            break
                        if grid[r][c] is None and can_place(word, r, c, 1, 0):
                            place_word(word, r, c, 1, 0, defin)
                            placed_here = True
                            break
                    if placed_here:
                        break

        if len(placed) > len(best_placed):
            best_placed = placed[:]
            best_grid = [[grid[r][c] for c in range(width)] for r in range(height)]
            if len(best_placed) >= max_words:
                break

    if not best_placed:
        return None

    placed = best_placed
    grid = best_grid

    # Numerowanie i podpowiedzi
    numbered_cells = {}
    cell_numbers = [[0 for _ in range(width)] for _ in range(height)]
    across_clues = {}
    down_clues = {}
    number = 0
    for word, defin, direction, r, c in placed:
        if (r, c) not in numbered_cells:
            number += 1
            numbered_cells[(r, c)] = number
            cell_numbers[r][c] = number
        else:
            cell_numbers[r][c] = numbered_cells[(r, c)]
        num = cell_numbers[r][c]
        if direction == 'across':
            across_clues[num] = defin
        else:
            down_clues[num] = defin

    solution = [[grid[r][c] for c in range(width)] for r in range(height)]

    tooltips = {}
    for num in set(across_clues.keys()) | set(down_clues.keys()):
        texts = []
        if num in across_clues:
            texts.append(f"Poziomo: {across_clues[num]}")
        if num in down_clues:
            texts.append(f"Pionowo: {down_clues[num]}")
        tooltips[num] = " | ".join(texts)

    word_starts = [[{
        'across': False,
        'down': False
    } for _ in range(width)] for _ in range(height)]

    for word, defin, direction, r, c in placed:
        if direction == 'across':
            word_starts[r][c]['across'] = True
        else:
            word_starts[r][c]['down'] = True

    return {
        'grid': grid,
        'solution': solution,
        'cell_numbers': cell_numbers,
        'width': width,
        'height': height,
        'across_clues': across_clues,
        'down_clues': down_clues,
        'word_starts': word_starts,
        'tooltips': tooltips
    }
