import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION ---
url_mosttechs = "https://mosttechs.com/coin-master-60-free-spin/"
url_reddit = "https://reddit.com"
filename = "scrapcoinmaster.json"

mois_en_to_num = {
    "january": "01", "januray": "01", "february": "02", "february ": "02", "march": "03", 
    "april": "04", "may": "05", "june": "06", "july": "07", "august": "08", 
    "september": "09", "october": "10", "november": "11", "december": "12"
}

now = datetime.now()
date_now_str = now.strftime("%d/%m/%Y @ %H:%M")
heure_actuelle_str = now.strftime("%H:%M")
limite_conservation = now - timedelta(days=5)

# --- 1B. INITIALISATION FIREBASE ---
firebase_key_raw = os.environ.get('FIREBASE_KEY')
if not firebase_key_raw:
    raise ValueError("Le secret FIREBASE_KEY est introuvable dans l'environnement.")

if not firebase_admin._apps:
    cred_json = json.loads(firebase_key_raw)
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. CHARGEMENT & NETTOYAGE DE L'HISTORIQUE ---
anciens_liens = {}
if os.path.exists(filename):
    try:
        with open(filename, mode="r", encoding="utf-8") as json_file:
            data_chargee = json.load(json_file)
            if isinstance(data_chargee, list):
                for item in data_chargee:
                    if "lienurl" in item:
                        try:
                            date_objet = datetime.strptime(item.get("date", ""), "%d/%m/%Y")
                            if date_objet >= limite_conservation:
                                anciens_liens[item["lienurl"]] = item
                        except:
                            anciens_liens[item["lienurl"]] = item
    except Exception as e:
        print(f"[Attention] Impossible de lire l'historique JSON : {e}")

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

liens_visites_session = set()
liens_bruts_collectes = [] # Contiendra des tuples (href, date_associee)

# =========================================================================
# --- SOURCE 1 (PRIORITÉ) : SCRAPING DES LIENS DIRECTS VIA FLUX REDDIT ---
# =========================================================================
print("[Source 1] Interrogation du flux officiel/communautaire Reddit...")
try:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    response_reddit = scraper.get(url_reddit, headers=headers, timeout=10)
    if response_reddit.status_code == 200:
        reddit_data = response_reddit.json()
        posts = reddit_data.get("data", {}).get("children", [])
        for post in posts:
            post_data = post.get("data", {})
            # Extraction du lien principal du post ou du texte si le lien y est imbriqué
            potential_urls = [post_data.get("url", "")]
            selftext = post_data.get("selftext", "")
            potential_urls.extend(re.findall(r'(https?://[^\s)]+)', selftext))
            
            for href in potential_urls:
                href = href.strip()
                # Filtrage selon vos mots-clés de confiance Coin Master
                keywords = ["coinmaster", "static-mat", "t.co", "bit.ly", "moonactive"]
                if any(key in href.lower() for key in keywords):
                    if not any(p in href.lower() for p in ["twitter.com", "facebook.com", "whatsapp", "pinterest", "reddit.com"]):
                        current_date_str = now.strftime("%d/%m/%Y") # Par défaut, date du jour pour la source directe
                        liens_bruts_collectes.append((href, current_date_str))
        print(f"[Source 1] {len(liens_bruts_collectes)} liens potentiels récupérés à la source.")
except Exception as e:
    print(f"[Source 1] [Erreur] Impossible d'interroger Reddit : {e}")

# =========================================================================
# --- SOURCE 2 (SECOURS) : SCRAPING COMPLÉMENTAIRE VIA MOSTECHS ---
# =========================================================================
print("[Source 2] Interrogation de Mosttechs en secours...")
try:
    response = scraper.get(url_mosttechs, timeout=15)
    status_code = response.status_code
    html_text = response.text
except Exception as e:
    status_code = 500
    html_text = ""
    print(f"[Source 2] [Erreur] Connexion impossible à Mosttechs : {e}")

if status_code == 200:
    soup = BeautifulSoup(html_text, "html.parser")
    entry_content = soup.find(class_="entry-content")
    if not entry_content:
        entry_content = soup
        
    current_date_str = now.strftime("%d/%m/%Y")
    
    for element in entry_content.find_all(["p", "ul", "ol", "strong"]):
        text = element.get_text().strip().lower()
        
        match_date = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', text)
        if match_date:
            jour = match_date.group(1).zfill(2)
            nom_mois = match_date.group(2).strip()
            annee = match_date.group(3)
            num_mois = mois_en_to_num.get(nom_mois, "01")
            current_date_str = f"{jour}/{num_mois}/{annee}"
            continue  

        try:
            date_section = datetime.strptime(current_date_str, "%d/%m/%Y")
            if date_section < limite_conservation:
                continue
        except:
            pass
        
        links = element.find_all("a", href=True)
        for link in links:
            href = link["href"].strip()
            
            if href.startswith("/") or "t.me" in href.lower() or "telegram.me" in href.lower():
                continue
            if any(p in href.lower() for p in ["twitter.com", "facebook.com", "whatsapp", "pinterest", "reddit.com"]):
                continue
                
            keywords = ["coinmaster", "static-mat", "t.co", "bit.ly", "moonactive"]
            if any(key in href.lower() for key in keywords):
                liens_bruts_collectes.append((href, current_date_str))
                
# =========================================================================
# --- TRITEMENT UNIQUÉ DES LIENS COLLECTÉS & DÉTECTION DES NOUVEAUTÉS ---
# =========================================================================
json_data = []
nouveaux_liens_detectes = 0  

for href, current_date_str in liens_bruts_collectes:
    if href in liens_visites_session:
        continue
    liens_visites_session.add(href)
    
    type_recompense = "Spins et Coins"
    
    if href in anciens_liens:
        date_premier_scraping_str = anciens_liens[href].get("date_scraping", date_now_str)
        badge_actuel = ""
        
        try:
            date_premier_scraping = datetime.strptime(date_premier_scraping_str, "%d/%m/%Y @ %H:%M")
            if now - date_premier_scraping < timedelta(hours=6):
                badge_actuel = "NEW"
        except:
            badge_actuel = anciens_liens[href].get("badge", "")

        json_data.append({
            "date_scraping": date_premier_scraping_str, 
            "date_scraping1": anciens_liens[href].get("date_scraping1", f"{current_date_str} @ {heure_actuelle_str}"),
            "date": current_date_str,  
            "heure": anciens_liens[href].get("heure", "00:00"),
            "recompense": anciens_liens[href].get("recompense", type_recompense), 
            "lienurl": href,
            "badge": badge_actuel
        })
    else:
        nouveaux_liens_detectes += 1
        date_scraping1_combinee = f"{current_date_str} @ {heure_actuelle_str}"
        json_data.append({
            "date_scraping": date_now_str, 
            "date_scraping1": date_scraping1_combinee,
            "date": current_date_str,  
            "heure": heure_actuelle_str,
            "recompense": type_recompense, 
            "lienurl": href,
            "badge": "NEW" 
        })

# Sauvegarde de secours si l'extraction réseau globale a échoué
if not json_data and anciens_liens:
    json_data = list(anciens_liens.values())

def extraire_cle_parution(item):
    try:
        return datetime.strptime(item.get("date", ""), "%d/%m/%Y").timestamp()
    except:
        return 0

json_data.sort(key=extraire_cle_parution, reverse=True)

with open(filename, mode="w", encoding="utf-8") as json_file:
    json.dump(json_data, json_file, indent=4, ensure_ascii=False)
    
print(f"[Terminé] Base Coin Master synchronisée ({len(json_data)} liens au total).")
print(f"[Diagnostic] Nombre de nouveaux liens détectés lors de ce traitement : {nouveaux_liens_detectes}")

# --- 7. EXPORTATION NOTIFICATION & ENVOI PUSH DIRECT ---
if nouveaux_liens_detectes > 0:
    try:
        from firebase_admin import messaging
        
        db.collection("notifications").add({
            "title": "🐷 Coin Reward ! 🎁",
            "body": "New free spins have just been added !",
            "nom_du_jeu": "coin_master",
            "created_at": firestore.SERVER_TIMESTAMP
        })
        print("[Firebase] Enregistrement d'historique créé pour Coin Master.")

        message = messaging.Message(
            notification=messaging.Notification(
                title="🐷 Coin Reward ! 🎁",
                body="New free spins have just been added !"
            ),
            topic="coin_master"
        )
        
        response = messaging.send(message)
        print(f"[Firebase Push] Notification Coin Master propulsée avec succès ! (ID: {response})")
        
    except Exception as e:
        print(f"[Firebase] [Erreur] Impossible d'envoyer l'alerte push direct Coin Master : {e}")
