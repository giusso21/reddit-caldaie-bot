"""
Bot di monitoraggio Reddit + Quora (via Google Alerts) -> Telegram
=====================================================================
Versione per GitHub Actions: fa UN SOLO controllo e poi termina. TOKEN e
CHAT_ID non sono scritti nel file (che qui vive in un repository,
potenzialmente visibile a chiunque), ma letti da "variabili d'ambiente" che
GitHub Actions inietta a partire dai Secrets configurati nelle impostazioni
del repository.
"""
Bot di monitoraggio Reddit + Quora (via Google Alerts) -> Telegram
=====================================================================
Versione per GitHub Actions: fa UN SOLO controllo e poi termina. TOKEN e
CHAT_ID non sono scritti nel file (che q
potenzialmente visibile a chiunque), ma letti da "variabili d'ambiente" che
GitHub Actions inietta a partire dai Secazioni
del repository.

Oltre ai subreddit Reddit, legge anche un feed RSS di Google Alerts (se
configurato) per intercettare le pagine Quora indicizzate da Google che
corrispondono alla ricerca dell'alert. Qoprio
ne' un'API pubblica, quindi si passa da  e
gratuito, invece di interrogare Quora direttamente.

Come usarlo: vedi il file ISTRUZIONI_GIT.
"""

import requests
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# ============================================================
# CONFIGURAZIONE - modifica solo queste
# ============================================================

# TOKEN e CHAT_ID NON vanno scritti qui: si configurano come "Secrets" nelle
# impostazioni del repository GitHub (ve script
# li legge da qui:
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEG

# URL del feed RSS dell'alert Google (Gort ->
# "Invia a" -> "Feed RSS" -> icona RSS accanto all'alert nella pagina
# principale). Facoltativo: se lasciato vuoto, il bot controlla solo Reddit.
GOOGLE_ALERTS_RSS_URL = os.environ.get("

# Sezioni di Reddit da controllare
SUBREDDITS = ["istrutturare", "Italia", ce"]

# Parole/frasi che rendono un post "interessante" (il controllo ignora
# maiuscole/minuscole)
KEYWORDS = [
    "caldaia", "caldaie", "caldaista", "riscaldamento",
    "termosifone", "termosifoni", "pompa
    "caldaia a condensazione", "manutenzione caldaia",
    "impianto di riscaldamento", "impian
    "bolletta del gas", "bolletta gas",
    "efficientamento energetico", "cappotto termico", "isolamento termico",
]

# Quanti post recenti guardare ad ogni controllo (per subreddit)
POST_LIMIT = 25

# ============================================================
# Non serve modificare nulla sotto quest
# ============================================================

# File in cui il programma si "ricorda" quali post ha già notificato, così
# non manda due volte lo stesso messaggio. Il workflow di GitHub Actions si
# occupa di salvarlo di nuovo nel reposi
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_posts.json")

# Reddit richiede un header "User-Agent" per identificare chi fa la
# richiesta. Usiamo uno User-Agent "da bamente
# come bot e' quello che in passato ha fatto scattare il blocco di Reddit.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.
)

# Namespace usato dal feed RSS (Atom) di
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
        json.dump(sorted(seen_ids), f, i


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
        response = requests.get(url, hea
        if response.status_code == 429 and attempt < max_retries:
            wait_seconds = 20 * (attempt + 1)
            print(
    """
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss?limit={POST_LIMIT}"
    headers = {"User-Agent": USER_AGENT}
    max_retries = 2

    for attempt in range(max_retries + 1):
        response = requests.get(url, hea
        if response.status_code == 429 and attempt < max_retries:
            wait_seconds = 20 * (attempt
            print(
                f"[{datetime.now():%H:%M:%S}] r/{subreddit}: limite di "
                f"richieste (429), aspet.."
            )
            time.sleep(wait_seconds)
            continue
        response.raise_for_status()
        break

    root = ET.fromstring(response.conten
    posts = []
    for entry in root.findall("atom:entr
        post_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        content = entry.findtext("atom:ces=ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        link = link_el.get("href") if link_el is not None else ""
        posts.append({"id": post_id, "title": title, "content": content, "link": link})
    return posts


def fetch_google_alerts_items():
    """
    Scarica le voci del feed dell'alert Google. E' in formato Atom, la
    stessa identica struttura del feed di Reddit (tag <entry>, <id>,
    <title>, <link href="...">, <contentogo a
    fetch_new_posts().
    Restituisce una lista di dizionari semplici: {"id", "title", "content", "link"}.
    """
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(GOOGLE_ALERTimeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = []
    for entry in root.findall("atom:entry", ATOM_NS):
        item_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:titTOM_NS)
        content = entry.findtext("atom:content", default="", namespaces=ATOM_NS)
        if not content:
            content = entry.findtext("atspaces=ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        link = link_el.get("href") if link_el is not None else ""
        items.append({"id": item_id, "title": title, "content": content, "link": link})
    return items


def check_google_alerts(seen_ids):
    """Controlla il feed Google Alerts uoci nuove e pertinenti."""
    updated_seen = set(seen_ids)

    if not GOOGLE_ALERTS_RSS_URL:
        return updated_seen  # non configurato, si salta silenziosamente

    try:
        items = fetch_google_alerts_items()
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Errore su Google Alerts: {e}")
        return updated_seen

    for item in items:
        item_id = item["id"]

        if not item_id or item_id in upd
            continue  # già notificato in un'esecuzione precedente

        title = item["title"]
        content = item["content"]

        if matches_keywords(f"{title} {content}"):
            link = item["link"]
            message = f"🔎 Nuovo risultato Google Alerts (Quora)\n\n<b>{title}</b>\n\n{link}"
            try:
                send_telegram_message(message)
                print(f"[{datetime.now()e Alerts): {title}")
            except Exception as e:
                print(f"[{datetime.now():%H:%M:%S}] Errore invio Telegram: {e}")

        updated_seen.add(item_id)

    return updated_seen


def send_telegram_message(text):
    """Invia un messaggio al tuo bot Telegram."""
    url = f"https://api.telegram.org/botage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, data=payload, timeout=15)
    response.raise_for_status()


def check_all_subreddits(seen_ids):
    """Controlla tutti i subreddit una vuovi e pertinenti."""
    updated_seen = set(seen_ids)

    for subreddit in SUBREDDITS:
        try:
            posts = fetch_new_posts(subreddit)
        except Exception as e:
            print(f"[{datetime.now():%H:t}: {e}")
            continue
        finally:
            # Piccola pausa tra un subreddit e l'altro per non superare il
            # limite di richieste che Rerrore
            # "429 Too Many Requests" se si va troppo veloci).
            time.sleep(3)

        for post in posts:
            post_id = post["id"]

            if not post_id or post_id in
                continue  # già notificato in un'esecuzione precedente

            title = post["title"]
            content = post["content"]

            if matches_keywords(f"{title
                link = post["link"]
                message = f"🔥 Nuovo post su r/{subreddit}\n\n<b>{title}</b>\n\n{link}"
                try:
                    send_telegram_message(message)
                    print(f"[{datetime.now():%H:%M:%S}] Notificato: {title}")
                except Exception as e:
                    print(f"[{datetime.nTelegram: {e}")

            updated_seen.add(post_id)

    return updated_seen


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "Errore: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti. "
            "Su GitHub Actions vanno configurati come Secrets del repository "
            "(Settings -> Secrets and va
        )
        sys.exit(1)

    print(f"[{datetime.now():%Y-%m-%d %Hcuzione singola).")
    seen_ids = load_seen_ids()
    seen_ids = check_all_subreddits(seen_ids)
    seen_ids = check_google_alerts(seen_
    save_seen_ids(seen_ids)
    print(f"[{datetime.now():%H:%M:%S}] Controllo completato, script terminato.")


if __name__ == "__main__":
    main()
