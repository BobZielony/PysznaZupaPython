from dominate.svg import title
from flask import Flask, render_template, redirect, url_for
import sys

from flask_wtf import FlaskForm, CSRFProtect
from flask import flash
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
import requests
from bs4 import BeautifulSoup
import json
import io
import os
app = Flask(__name__)
app.secret_key = 'tO$&!|0wkamvVia0?n$NqIRVWOG'
ascii_lowercase = 'abcdefghijklmnopqrstuvwxyz'

csrf = CSRFProtect(app)

@app.route("/")
def index():
    headlines = []
    for letter in ascii_lowercase:
        for number in range(1,2):
            text = "https://sjp.pwn.pl/sjp/lista/{letter};{number}"
            response = scrape(text.format(letter = letter,number = number))
            if not response:
                break
            else:
                headlines.append(response)
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

wordList = {
    "tung" : "Indonezyjski z pałką",
    "polska" : "Państwo unitarne w Europie Środkowej, położone między Morzem Bałtyckim na północy a Sudetami i Karpatami na południu",
    "błażej" : "Imię męskie pochodzenia łacińskiego. Wywodzi się od słowa „blaesus” - oznaczającego „seplenić”."
 }


