import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION ---
# URL configurée spécifiquement pour la page Coin Master de Mosttechs
url = "https://mosttechs.com/coin-master-60-free-spin/"
filename = "scrapcoinmaster.json"  # Nom du fichier adapté pour différencier de Piggy Go

# Dictionnaire de traduction des mois pour la conversion en vraies dates Python
mois_en_to_num = {
    "january": "01", "januray": "01", "february": "02", "february ": "02", "march": "03", 
    "april": "04", "may": "05", "june": "06", "july": "07", "august": "08", 
    "september": "09", "october": "10", "november": "11", "december": "12"
}

# --- 2. CHARGEMENT DE L'HISTORIQUE ---
anciens_liens = {}
if os.path.exists(filename):
    try:
        with open(filename, mode="r", encoding="utf-8") as json_file:
            data_chargee = json.load(json_file)
            if isinstance(data_chargee, list):
                for item in data_chargee:
                    if "lienurl" in item:
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
    
    now = datetime.now()
    date_now_str = now.strftime("%d/%m/%Y @ %H:%M")
    heure_actuelle_str = now.strftime("%H:%M")
    
    # Seuil limite : suppression du fichier de ce qui est vieux de plus de 6 jours
    limite_conservation = now - timedelta(days=6)
    
    json_data = []
    
    # Isolement du contenu principal pour ignorer les menus et barres latérales
    entry_content = soup.find(class_="entry-content")
    if not entry_content:
        entry_content = soup
        
    # 3. PARCOURS CHRONOLOGIQUE DES BLOCS DE TEXTE
    current_date_str = now.strftime("%d/%m/%Y")  # Valeur par défaut
    
    for element in entry_content.find_all(["p", "ul", "ol", "strong"]):
        text = element.get_text().strip().lower()
        
        # Détection d'une ligne de date (Ex: "26 september 2026")
        match_date = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', text)
        if match_date:
            jour = match_date.group(1).zfill(2)
            nom_mois = match_date.group(2)
            annee = match_date.group(3)
            
            num_mois = mois_en_to_num.get(nom_mois, "01")
            current_date_str = f"{jour}/{num_mois}/{annee}"
            continue  # Date enregistrée, on passe à la recherche des liens sous celle-ci
            
        # Extraction des liens hypertextes présents dans le bloc courant
        links = element.find_all("a", href=True)
        for link in links:
            href = link["href"].strip()
            
            # Filtres sanitaires (Exclusion des partages sociaux et liens internes Telegram)
            if href.startswith("/") or "t.me" in href.lower() or "telegram.me" in href.lower():
                continue
            if any(p in href.lower() for p in ["twitter.com", "facebook.com", "whatsapp", "pinterest", "reddit.com"]):
                continue
                
            # Validation des mots-clés typiques des domaines de récompense Coin Master
            # (Coin Master utilise principalement des liens vers son domaine officiel ou raccourcis spécifiques)
            keywords = ["coinmaster", "static-mat", "t.co", "bit.ly"]
            if any(key in href.lower() for key in keywords):
                
                # Vérification de la limite de conservation des 6 jours
                try:
                    date_objet = datetime.strptime(current_date_str, "%d/%m/%Y")
                    if date_objet < limite_conservation:
                        continue  # Lien expiré par rapport au calendrier, ignoré
                except:
                    pass
                
                # Éviter les doublons lors de la session de crawl courante
                if any(item["lienurl"] == href for item in json_data):
                    continue
                
                type_recompense = "Spins et Coins"
                
                # --- STRATÉGIE DE RECONSTITUTION ET CONSERVATION STRICTE ---
                if href in anciens_liens:
                    # ANCIEN LIEN : On conserve STRICTEMENT l'historique initial sans modifier date_scraping1
                    json_data.append({
                        "date_scraping": anciens_liens[href].get("date_scraping", date_now_str), 
                        "date_scraping1": anciens_liens[href].get("date_scraping1", f"{current_date_str} @ {heure_actuelle_str}"),
                        "date": current_date_str,  
                        "heure": anciens_liens[href].get("heure", "00:00"),
                        "recompense": anciens_liens[href].get("recompense", type_recompense), 
                        "lienurl": href,
                        "badge": "" 
                    })
                else:
                    # NOUVEAU LIEN : On crée date_scraping1 avec la date du site et l'heure actuelle du robot
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

    # Si le site distant échoue à renvoyer des données, sauvegarde de l'historique sain nettoyé
    if not json_data and anciens_liens:
        json_data = list(anciens_liens.values())

    # --- 4. TRI CHRONOLOGIQUE PAR DATE DE PARUTION DU SITE (Le plus récent en haut) ---
    def extraire_cle_parution(item):
        try:
            date_part = datetime.strptime(item.get("date", ""), "%d/%m/%Y")
            return date_part.timestamp()
        except:
            return 0

    # Classement décroissant pour placer les liens de parution du jour tout en haut de la liste
    json_data.sort(key=extraire_cle_parution, reverse=True)

    # --- 5. ENREGISTREMENT DU FICHIER JSON ---
    with open(filename, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=4, ensure_ascii=False)
        
    print(f"[Terminé] Fichier Coin Master {filename} mis à jour ({len(json_data)} liens classés chronologiquement). Anciennes valeurs préservées.")
            
else:
    print(f"[Erreur] Échec d'accès réseau (Code {status_code}).")
