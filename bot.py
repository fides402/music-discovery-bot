import os
import json
import re
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
SUGGESTED_FILE = "suggested.json"


def load_suggested():
    if os.path.exists(SUGGESTED_FILE):
        with open(SUGGESTED_FILE) as f:
            return json.load(f)
    return []


def save_suggested(lst):
    with open(SUGGESTED_FILE, "w") as f:
        json.dump(lst, f)


def get_youtube_link(query):
    try:
        yt = build("googleapiclient", "v3", developerKey=os.environ["YT_API_KEY"])
        res = yt.search().list(q=query, part="snippet", type="video", maxResults=1).execute()
        items = res.get("items", [])
        if items:
            return "https://www.youtube.com/watch?v=" + items[0]["id"]["videoId"]
    except Exception as e:
        logging.error("YT error: " + str(e))
    return None


def recommend_album(suggested_so_far):
    from tracks import TRACKS_CSV
    if suggested_so_far:
        suggested_str = "\n".join(suggested_so_far[-30:])
    else:
        suggested_str = "nessuno ancora"
    prompt = (
        "Sei un critico musicale con conoscenza enciclopedica di dischi rari e dimenticati.\n\n"
        "Lista brani preferiti dell utente (da Spotify):\n" + TRACKS_CSV + "\n\n"
        "Dischi gia suggeriti - NON riproporre:\n" + suggested_str + "\n\n"
        "Regole:\n"
        "- Suggerisci 1 solo disco RARO (non famoso, non ovvio, non mainstream)\n"
        "- Coerente con i gusti dell utente ma sorprendente e inaspettato\n"
        "- NON suggerire artisti gia presenti nella lista dei brani\n"
        "- Preferisci dischi con pochissimi ascoltatori su Spotify\n"
        "- Puoi spaziare tra: library music, jazz oscuro, soul dimenticato, bossa rara, prog minore, world music, cantautori sconosciuti, soundtrack oscure\n\n"
        'Rispondi SOLO con questo JSON (niente altro, nessun testo prima o dopo):\n'
        '{\n'
        '  "artist": "Nome Artista",\n'
        '  "album": "Nome Album",\n'
        '  "year": 1975,\n'
        '  "genre": "Genere",\n'
        '  "why": "2 righe in italiano su perche gli piacera",\n'
        '  "search_query": "Artist Album full album youtube"\n'
        '}'
    )
    res = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.92,
        max_tokens=400
    )
    content = res.choices[0].message.content.strip()
    match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cerco un disco per te...")
    suggested = load_suggested()
    rec = recommend_album(suggested)
    if rec:
        yt = get_youtube_link(rec["search_query"])
        suggested.append(rec["artist"] + " - " + rec["album"])
        save_suggested(suggested)
        yt_str = "\n\n" + str(yt) if yt else ""
        msg = (
            "🎵 *" + rec["album"] + "*\n"
            "👤 " + rec["artist"] + " (" + str(rec["year"]) + ")\n"
            "🎼 " + rec["genre"] + "\n\n"
            "_" + rec["why"] + "_" +
            yt_str
        )
    else:
        msg = "Errore nella generazione. Riprova!"
    await update.message.reply_text(msg, parse_mode="Markdown")


def main():
    token = os.environ["TELEGRAM_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("Bot avviato...")
    app.run_polling()


if __name__ == "__main__":
    main()
