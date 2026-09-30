import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup

--- 1. CONFIGURATION ---
url = "https://mosttechs.com/coin-master-60-free-spin/"
filename = "scrapcoinmaster.json"

mois_en_to_num = {
"january": "01", "januray": "01", "february": "02", "february ": "02", "march": "03",
"april": "04", "may": "05", "june": "06", "july": "07", "august": "08",
"september": "09", "october": "10", "november": "11", "december": "12"
}

--- 2. CHARGEMENT DE L'HISTORIQUE ---
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

limite_conservation = now - timedelta(days=6)

json_data = []

entry_content = soup.find(class_="entry-content")
if not entry_content:
entry_content = soup

# 3. PARCOURS CHRONOLOGIQUE DES BLOCS DE TEXTE
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

if any(item["lienurl"] == href for item in json_data):
continue

type_recompense = "Spins et Coins"

if href in anciens_liens:
# On nettoie temporairement une éventuelle ancienne numérotation (ex: "1- ")
# pour pouvoir recalculer correctement la base propre.
ancienne_date_scraping1 = anciens_liens[href].get("date_scraping1", f"{current_date_str} @ {heure_actuelle_str}")
ancienne_date_scraping1_nettoye = re.sub(r'^\d+-\s*', '', ancienne_date_scraping1)

json_data.append({
"date_scraping": anciens_liens[href].get("date_scraping", date_now_str),
"date_scraping1": ancienne_date_scraping1_nettoye, # Base propre sans numéro
"date": current_date_str,
 "heure": anciens_liens[href].get("heure", "00:00"),
"recompense": anciens_liens[href].get("recompense", type_recompense),
"lienurl": href,
"badge": ""
})
else:
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

if not json_data and anciens_liens:
json_data = list(anciens_liens.values())

# --- 3.1 POST-NUMÉROTATION DES DOUBLONS DE DATE_SCRAPING1 ---
# Étape A : Compter le nombre d'occurrences pour chaque date_scraping1
compteur_global = {}
for item in json_data:
cle_date = item["date_scraping1"]
compteur_global[cle_date] = compteur_global.get(cle_date, 0) + 1

# Étape B : Appliquer la numérotation "X- " uniquement si la date apparaît plusieurs fois
# (On parcourt à l'envers ou dans l'ordre du crawl pour attribuer les numéros de 1 à N)
suivi_index = {}
for item in reversed(json_data): # Inversé pour que le premier lien trouvé sur le site ait le numéro 1
cle_date = item["date_scraping1"]

if compteur_global[cle_date] > 1:
suivi_index[cle_date] = suivi_index.get(cle_date, 0) + 1
# Ajout du "1- ", "2- ", etc., devant la date
item["date_scraping1"] = f"{suivi_index[cle_date]}- {cle_date}"

# --- 4. TRI CHRONOLOGIQUE PAR DATE DE PARUTION DU SITE ---
def extraire_cle_parution(item):
try:
date_part = datetime.strptime(item.get("date", ""), "%d/%m/%Y")
return date_part.timestamp()
except:
return 0

json_data.sort(key=extraire_cle_parution, reverse=True)

# --- 5. ENREGISTREMENT DU FICHIER JSON ---
with open(filename, mode="w", encoding="utf-8") as json_file:
json.dump(json_data, json_file, indent=4, ensure_ascii=False)

print(f"[Terminé] Fichier Coin Master {filename} mis à jour ({len(json_data)} liens classés chronologiquement). Anciennes valeurs préservées.")

else:
print(f"[Erreur] Échec d'accès réseau (Code {status_code}).")
