import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36 "
    )
}

# ile requestów jednocześnie
semaphore = asyncio.Semaphore(22)


def load_words():
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    words = []

    for group in data:
        for word in group:

            word = word.strip().lower()

            if word and len(word) > 1:
                words.append(word)

    # usunięcie duplikatów
    words = list(dict.fromkeys(words))

    return words


import re

async def fetch_definition(session, word):

    if len(word) < 4:
        return None

    if not re.match(r"^[a-ząćęłńóśźż]+$", word):
        return None

    url = f"https://sjp.pl/{word}"

    async with semaphore:

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

                definition = None

                # wszystkie paragrafy
                paragraphs = soup.find_all("p")

                blacklist = [
                    "dopuszczalne w grach",
                    "scrabble",
                    "x/twitter",
                    "facebook",
                    "komentarze",
                    "dodaj komentarz",
                    "synonimy",
                    "odmiana",
                    "google",
                    "youtube",
                    "instagram",
                    "tiktok",
                    "napisane przez",
                    "forum"
                ]

                for p in paragraphs:

                    text = p.get_text(" ", strip=True)

                    if not text:
                        continue

                    text = re.sub(r"\s+", " ", text).strip()

                    text_lower = text.lower()

                    # blacklist
                    if any(b in text_lower for b in blacklist):
                        continue

                    # komentarze zwykle mają emotki/cytaty
                    if "??" in text or "xd" in text_lower:
                        continue

                    # odrzucenie cytatów użytkowników
                    if text.count('"') > 2:
                        continue

                    # długość
                    if len(text) < 20 or len(text) > 200:
                        continue

                    # definicje zwykle zaczynają się małą literą lub numerem
                    if not (
                        text[0].islower()
                        or text[0].isdigit()
                    ):
                        continue

                    # komentarze często mają wykrzykniki
                    if text.count("!") > 1:
                        continue

                    # definicje zwykle nie zawierają dialogu
                    bad_words = [
                        "musisz",
                        "nudny",
                        "malkontent",
                        "stwórca",
                        "nooo",
                        "zwłacha"
                    ]

                    if any(b in text_lower for b in bad_words):
                        continue

                    definition = text
                    break

                if not definition:
                    return None

                print(f"[OK] {word}")

                return {
                    "word": word,
                    "definition": definition
                }

        except Exception as e:

            print(f"[ERROR] {word}: {e}")

            return None


async def fetch_all_definitions(words):

    results = []

    async with aiohttp.ClientSession() as session:

        tasks = [
            fetch_definition(session, word)
            for word in words
        ]

        fetched = await asyncio.gather(*tasks)

        results = [r for r in fetched if r]

    return results


async def main():

    print("Wczytywanie słów...")

    words = load_words()

    print(f"Załadowano {len(words)} słów")

    print("Pobieranie definicji...")

    results = await fetch_all_definitions(words)

    print(f"Pobrano {len(results)} definicji")

    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=4
        )

    print("Zapisano words.json")


if __name__ == "__main__":
    asyncio.run(main())