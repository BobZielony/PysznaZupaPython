## Główne informacje
- Program wykorzystuje technikę Web Scrapingu do pozyskiwania słów oraz definicji ze słowników internetowych oraz bazy danych leksykalno-semantycznych.
- Pobrane dane są zapisywane lokalnie w pliku data.json.
- Definicje są przetwarzane przez model językowy, który zamienia tekst na reprezentacje wektorowe.
- Program ogranicza liczbę jednoczesnych połączeń z serwerem źródłowym, aby zapobiec jego przeciążeniu.
- Pierwsze uruchomienie programu zajmuje dłużej gdyż buduje indeksy modelu.

## Użyte technologie
- beautifulsoup4
- paraphrase-multilingual-MiniLM-L12-v2, Hugging Face
- FAISS
- Flask

## Funkcje
Lista funkcjonalności:
- Wyszukiwarka słów z brakującymi literami.
- Wyszukiwarka słów na podstawie definicji.
- Generator krzyzówek z możliwoscią modyfikacji parametrów.

## Wyszukiwarka słów
Umożliwia wyszukiwanie słów na podstawie znanych liter i długości hasła.

**Przykład:**

k....a

**Wynik:**

- kanapa
- karata


## Wyszukiwarka definicji

Użytkownik wpisuje definicję lub opis poszukiwanego słowa.

**Przykład:**

japoński miecz

**Program:**

1. Zamienia definicję na wektor liczbowy.
2. Porównuje go z bazą definicji.
3. Wyświetla najbardziej podobne wyniki wraz z procentem podobieństwa.

**Wynik:**

- wakizashi
    - krótki miecz japoński noszony przez samurajów , stopień podobieństwa: 92.9
-bokken 
    - japoński drewniany miecz do ćwiczeń wschodnich sztuk walki, zwykle o kształcie katany, stopień podobieństwa: 88.8
-katana
    - długi, lekko zakrzywiony, jednosieczny miecz japoński z ozdobną rękojeścią , stopień podobieństwa: 88.2


## Generator krzyżówek

Generator pozwala tworzyć krzyżówki na podstawie parametrów podanych przez użytkownika:

- Szerokość planszy.
- Wysokość planszy.
- Maksymalna liczba słów.

Generator szuka takiego umieszczenia słów które zapełni jak najwięcej planszy,
w krzyżówce działa:
- Automatyczne przechodzenie kursora
- Sprawdzanie odpowiedzi
- Drukowanie krzyżówki
- Podświetlanie podpowiedzi po najechaniu na liczbe

## Instalacja programu

1. Sklonowanie repozytorium
2. Instalacja wymaganych bibliotek
3. Zainstalowanie biblioteki flask w wersji asynchronicznej
4. Włączenie aplikacji

## Status projektu
Projekt jest skończony, posiadamy wszystkie zaplanowane funkcjonalności

## Źródła danych
- [Słownik języka polskiego PWN](https://sjp.pwn.pl/)
- [Słownik SJP.PL - Słownik języka polskiego, słownik do gier](https://sjp.pl/)
- [WordList.eu internetowa baza wyrazów języka polskiego](https://wordlist.eu/)
- [Słowosieć relacyjny słownik semantyczny](http://plwordnet.pwr.wroc.pl/wordnet/)

## Twórcy
Created by [@BobZielony][@ank4p][@gibaspl]