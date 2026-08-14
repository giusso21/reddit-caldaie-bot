"""
Bot di monitoraggio Reddit -> Telegram (versione per GitHub Actions)
=====================================================================
Identica nella logica a bot_pythonanywhere.py: fa UN SOLO controllo e poi
termina. La differenza e' che TOKEN e CHAT_ID non sono scritti nel file (che
qui vive in un repository, potenzialmente visibile a chiunque), ma letti da
"variabili d'ambiente" che GitHub Actions inietta a partire dai Secrets
configurati nelle impostazioni del repository.

Come usarlo: vedi il file ISTRUZIONI_GITHUB.txt nella stessa cartella.
"""

import requests
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# ============================================================
# CONFIGURAZIONE - modifica solo queste righe (tranne TOKEN/CHAT_ID)
# ============================================================

# TOKEN e CHAT_ID NON vanno scritti qui: si configurano come "Secrets" nelle
# impostazioni del repository GitHub (vedi ISTRUZIONI_GITHUB.txt). Lo script
# li legge da qui:
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Sezioni di Reddit da controllare
SUBREDDITS = ["istrutturare", "Italia", "italy", "ItaliaPersonalFinance"]

# Parole/frasi che rendono un post "interessante" (il controllo ignora
# maiuscole/minuscole)
KEYWORDS = [
    "caldaia", "caldaie", "caldaista", "riscaldamento",
    "termosifone", "termosifoni", "pompa di calore",
    "caldaia a condensazione", "manutenzione caldaia",
    "impianto di riscaldamento", "impianti di riscaldamento",
    "bolletta del gas", "bolletta gas",
    "efficientamento energetico", "cappotto termico", "isolamento termico",
]

# Quanti post recenti guardare ad ogni controllo (per subreddit)
POST_LIMIT = 25

# ============================================================
# Non serve modificare nulla sotto questa riga
# ============================================================

# File in cui il programma si "ricorda" quali post ha già notificato, così
# non manda due volte lo stesso messaggio. Il workflow di GitHub Actions si
# occupa di salvarlo di nuovo nel repository dopo ogni esecuzione.
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_posts.json")

# Reddit richiede un header "User-Agent" per identificare chi fa la
# richiesta. Usiamo uno User-Agent "da browser": dichiararsi esplicitamente
# come bot e' quello che in passato ha fatto scattare il blocco di Reddit.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Namespace usato dal feed RSS (Atom) di Reddit.
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def load_seen_ids():
    """Legge dal disco l'elenco dei post già notificati in passato."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen_ids):
    """Salva su disco l'elenco aggiornato dei post già notificati."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_ids), f, indent=2)


def matches_keywords(text):
    """Vero se il testo contiene almeno una delle parole chiave."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS)


def fetch_new_posts(subreddit):
    """
    Scarica gli ultimi post pubblicati in un subreddit leggendo il feed RSS
    (Atom) pubblico di Reddit.
    Restituisce una lista di dizionari semplici: {"id", "title", "content", "link"}.

    Se Reddit risponde "429 Too Many Requests" (limite temporaneo di
    richieste), aspetta un po' e riprova fino a 2 volte prima di arrendersi.
    """
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss?limit={POST_LIMIT}"
    headers = {"User-Agent": USER_AGENT}
    max_retries = 2

    for attempt in range(max_retries + 1):
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 429 and attempt < max_retries:
            wait_seconds = 20 * (attempt + 1)
            print(
                f"[{datetime.now():%H:%M:%S}] r/{subreddit}: limite di "
                f"richieste (429), aspetto {wait_seconds}s e riprovo..."
            )
            time.sleep(wait_seconds)
            continue
        response.raise_for_status()
        break

    root = ET.fromstring(response.content)
    posts = []
    for entry in root.findall("atom:entry", ATOM_NS):
        post_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        content = entry.findtext("atom:content", default="", namespaces=ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        link = link_el.get("href") if link_el is not None else ""
        posts.append({"id": post_id, "title": title, "content": content, "link": link})
    return posts


def send_telegram_message(text):
    """Invia un messaggio al tuo bot Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, data=payload, timeout=15)
    response.raise_for_status()


def check_all_subreddits(seen_ids):
    """Controlla tutti i subreddit una volta sola e notifica i post nuovi e pertinenti."""
    updated_seen = set(seen_ids)

    for subreddit in SUBREDDITS:
        try:
            posts = fetch_new_posts(subreddit)
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] Errore su r/{subreddit}: {e}")
            continue
        finally:
            # Piccola pausa tra un subreddit e l'altro per non superare il
            # limite di richieste che Reddit tollera in poco tempo (errore
            # "429 Too Many Requests" se si va troppo veloci).
            time.sleep(3)

        for post in posts:
            post_id = post["id"]

            if not post_id or post_id in updated_seen:
                continue  # già notificato in un'esecuzione precedente

            title = post["title"]
            content = post["content"]

            if matches_keywords(f"{title} {content}"):
                link = post["link"]
                message = f"🔥 Nuovo post su r/{subreddit}\n\n<b>{title}</b>\n\n{link}"
                try:
                    send_telegram_message(message)
                    print(f"[{datetime.now():%H:%M:%S}] Notificato: {title}")
                except Exception as e:
                    print(f"[{datetime.now():%H:%M:%S}] Errore invio Telegram: {e}")

            updated_seen.add(post_id)

    return updated_seen


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "Errore: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti. "
            "Su GitHub Actions vanno configurati come Secrets del repository "
            "(Settings -> Secrets and variables -> Actions)."
        )
        sys.exit(1)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Avvio controllo (esecuzione singola).")
    seen_ids = load_seen_ids()
    seen_ids = check_all_subreddits(seen_ids)
    save_seen_ids(seen_ids)
    print(f"[{datetime.now():%H:%M:%S}] Controllo completato, script terminato.")


if __name__ == "__main__":
    main()
