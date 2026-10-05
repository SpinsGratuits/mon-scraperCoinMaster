import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging  # <-- AJOUT DE MESSAGING ICI

# --- 1. CONFIGURATION ---
url = "https://mosttechs.com/coin-master-60-free-spin/"
filename = "scrapcoinmaster.json"

mois_en_to_num = {
    "january": "01", "januray": "01", "february": "02", "february ": "02", "march": "03", 
    "april": "04", "may": "05", "june": "06", "july": "07", "august": "08", 
    "september": "09", "october": "10", "november": "11", "december": "12"
}

now = datetime.now()
date_now_str = now.strftime("%d/%m/%Y @ %H:%M")
heure_actuelle_str = now.strftime("%H:%M")
limite_conservation = now - timedelta(days=6)

# --- 1B. INITIALISATION FIREBASE ---
firebase_key_raw = os.environ.get('FIREBASE_KEY')
if not firebase_key_raw:
    raise ValueError("Le secret FIREBASE_KEY est introuvable dans l'environnement.")

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

# Client de contournement des protections Cloudflare
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

try:
    response = scraper.get(url, timeout=15)
    status_code = response.status_code
    html_text = response.text
except Exception as e:
    status_code = 500
    html_text = ""
    print(f"[Erreur] Connexion impossible : {e}")

if status_code == 200:
    soup = BeautifulSoup(html_text, "html.parser")
    json_data = []
    liens_visites_session = set()
    nouveaux_liens_detectes = 0  # <-- COMPTEUR POUR DECLENCHER LA NOTIFICATION
    
    entry_content = soup.find(class_="entry-content")
    if not entry_content:
        entry_content = soup
        
    # --- 3. PARCOURS CHRONOLOGIQUE DES BLOCS DE TEXTE ---
    current_date_str = now.strftime("%d/%m/%Y")
    
    for element in entry_content.find_all(["p", "ul", "ol", "strong"]):
        text = element.get_text().strip().lower()
        
        match_date = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', text)
        if match_date:
            jour = match_date.group(1).zfill(2)
            nom_mois = match_date.group(2)
            annee = match_date.group(3)
            
            num_mois = mois_en_to_num.get(nom_mois, "01")
            current_date_str = f"{jour}/{num_mois}/{annee}"
            continue  
            
        links = element.find_all("a", href=True)
        for link in links:
            href = link["href"].strip()
            
            if href.startswith("/") or "t.me" in href.lower() or "telegram.me" in href.lower():
                continue
            if any(p in href.lower() for p in ["twitter.com", "facebook.com", "whatsapp", "pinterest", "reddit.com"]):
                continue
                
            keywords = ["coinmaster", "static-mat", "t.co", "bit.ly"]
            if any(key in href.lower() for key in keywords):
                
                try:
                    date_objet = datetime.strptime(current_date_str, "%d/%m/%Y")
                    if date_objet < limite_conservation:
                        continue
                except:
                    pass
                
                if href in liens_visites_session:
                    continue
                liens_visites_session.add(href)
                
                type_recompense = "Spins et Coins"
                
                # =====================================================================
                # MODIFICATION ICI : GESTION DU BADGE NEW PENDANT 6 HEURES
                # =====================================================================
                if href in anciens_liens:
                    date_premier_scraping_str = anciens_liens[href].get("date_scraping", date_now_str)
                    badge_actuel = ""
                    
                    try:
                        date_premier_scraping = datetime.strptime(date_premier_scraping_str, "%d/%m/%Y @ %H:%M")
                        # Si le lien a moins de 6 heures, on garde le badge "NEW"
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
                    nouveaux_liens_detectes += 1  # <-- ON A TROUVÉ UN NOUVEAU LIEN !
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
                # =====================================================================

    if not json_data and anciens_liens:
        json_data = list(anciens_liens.values())

    # --- 4. TRI CHRONOLOGIQUE ---
    def extraire_cle_parution(item):
        try:
            return datetime.strptime(item.get("date", ""), "%d/%m/%Y").timestamp()
        except:
            return 0

    json_data.sort(key=extraire_cle_parution, reverse=True)

    # --- 5. ENREGISTREMENT LOCAL ---
    with open(filename, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=4, ensure_ascii=False)
        
    print(f"[Terminé] Fichier Coin Master {filename} mis à jour ({len(json_data)} liens valides).")

    # --- 6. EXPORTATION VERS FIREBASE FIRESTORE ---
    try:
        db.collection("coin_master").document("current_links").set({
            "links": json_data,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        print("[Firebase] Données synchronisées avec succès sur Firestore.")
    except Exception as e:
        print(f"[Firebase] [Erreur] Synchronisation impossible : {e}")

    # --- 7. ENVOI DE LA NOTIFICATION PUSH SI NOUVEAU LIEN DISPONIBLE ---
    if nouveaux_liens_detectes > 0:
        try:
            # Construction du message pour l'application FlutterFlow
            message_push = messaging.Message(
                notification=messaging.Notification(
                    title="Coin M. Nouveaux Spins ! 🎁",
                    body=f"De nouveaux liens viennent d'être ajoutés. Profitez de vos tours gratuits !"
                ),
                android=messaging.AndroidConfig(
                    priority='high',  # Force l'affichage sur écran en veille
                    notification=messaging.AndroidNotification(
                        sound='default',
                        click_action='FLUTTER_NOTIFICATION_CLICK'  # Ouvre l'app au clic
                    ),
                ),
                topic='alertes_github'  # Doit correspondre au nom défini dans la Custom Action FlutterFlow
            )
            
            # Envoi au topic
            response = messaging.send(message_push)
            print(f"[Push FCM] Notification envoyée avec succès ({nouveaux_liens_detectes} nouveau(x) lien(s)). ID: {response}")
        except Exception as e:
            print(f"[Push FCM] [Erreur] Échec de l'envoi de la notification : {e}")
    else:
        print("[Push FCM] Aucun nouveau lien détecté. Pas de notification envoyée.")
            
else:
    print(f"[Erreur] Échec d'accès réseau (Code {status_code}).")
