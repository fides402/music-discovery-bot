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
                                  return f"https://www.youtube.com/watch?v={items[0]['id']['videoId']}"
          except Exception as e:
                    logging.error(f"YT error: {e}")
                return None

def recommend_album(suggested_so_far):
      from tracks import TRACKS_CSV
    suggested_str = "\n".join(suggested_so_far[-30:]) if suggested_so_far else "nessuno ancora"
    prompt = f"""Sei un critico musicale con conoscenza enciclopedica di dischi rari e dimenticati.

    Lista brani preferiti dell utente (da Spotify):
    {TRACKS_CSV}

    Dischi gia suggeriti - NON riproporre:
    {suggested_str}

    Regole:
    - Suggerisci 1 solo disco RARO (non famoso, non ovvio, non mainstream)
    - Coerente con i gusti dell utente ma sorprendente e inaspettato
    - NON suggerire artisti gia presenti nella lista dei brani
    - Preferisci dischi con pochissimi ascoltatori su Spotify
    - Puoi spaziare tra: library music, jazz oscuro, soul dimenticato, bossa rara, prog minore, world music, cantautori sconosciuti, soundtrack oscure

    Rispondi SOLO con questo JSON (niente altro, nessun testo prima o dopo):
    {{
      "artist": "Nome Artista",
        "album": "Nome Album",
          "year": 1975,
            "genre": "Genere",
              "why": "2 righe in italiano su perche gli piacera",
                "search_query": "Artist Album full album youtube"
}}"""

    res = groq_client.chat.completions.create(
              model="llama-3.3-70b-versatile",
              messages=[{"role": "user", "content": prompt}],
              temperature=0.92,
              max_tokens=400
    )
    content = res.choices[0].message.content.strip()
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
              return json.loads(match.group())
          return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
      await update.message.reply_text("Cerco un disco per te...")
    suggested = load_suggested()
    rec = recommend_album(suggested)
    if rec:
              yt = get_youtube_link(rec["search_query"])
              suggested.append(f"{rec['artist']} - {rec['album']}")
              save_suggested(suggested)
              yt_str = f"\n\n▶️ {yt}" if yt else ""
              msg = (
                  f"🎵 *{rec['album']}*\n"
                  f"👤 {rec['artist']} \\({rec['year']}\\)\n"
                  f"🎼 {rec['genre']}\n\n"
                  f"_{rec['why']}_"
                  f"{yt_str}"
              )
    else:
        msg = "Errore nella generazione\\. Riprova!"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

def main():
      token = os.environ["TELEGRAM_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
      main()
