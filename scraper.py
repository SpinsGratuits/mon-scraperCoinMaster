import json
from datetime import datetime
import cloudscraper  # Remplace requests pour contourner le blocage
from bs4 import BeautifulSoup
import re

# 1. URL du site cible
url = "https://gamewave.fr/coin-master/coin-master-tours-spins-et-pieces-gratuits/"

# Création d'un scraper qui imite un navigateur Chrome sur Windows
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

try:
    response = scraper.get(url)
    status_code = response.status_code
    html_text = response.text
except Exception as e:
    status_code = 500
    html_text = ""
    print(f"Erreur lors du contournement du blocage : {e}")

if status_code == 200:
    soup = BeautifulSoup(html_text, "html.parser")
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Liste qui contiendra nos dictionnaires d'objets JSON
    json_data = []
    
    # 2. Scanner TOUS les liens hypertextes de la page
    all_links = soup.find_all("a", href=True)
    
    for link in all_links:
        href = link["href"]
        
        # Cibler n'importe quel lien contenant rewards.coinmaster.com
        if "rewards.coinmaster.com" in href:
            # Récupérer le bloc de texte entourant le lien
            parent_text = link.find_parent().get_text(separator=" ").strip() if link.find_parent() else ""
            if len(parent_text) < 15 and link.find_parent().find_parent():
                parent_text = link.find_parent().find_parent().get_text(separator=" ").strip()
            
            clean_text = " ".join(parent_text.split())
            
            # Isoler la date (ex: 19/09/2026)
            date_match = re.search(r'\d{2}/\d{2}/\d{4}', clean_text)
            date_evenement = date_match.group(0) if date_match else "Aujourd'hui"
            
            # Déterminer la quantité de dés
            des_match = re.search(r'\d+\s*(?:Dés|dés|Rolls|rolls|lancers)', clean_text)
            quantite_des = des_match.group(0) if des_match else "tours (spins)"
            quantite_des = quantite_des.replace("Récupérer", "").strip()
            
            # Éviter les doublons (on vérifie la clé 'Lien Direct Récompense' dans les dictionnaires existants)
            if not any(item["lienurl"] == href for item in json_data):
                # Structure sous forme de dictionnaire clé: valeur
                json_data.append({
                    "date_scraping": date_now, "date": date_evenement, "quantite_des": quantite_des, "lienurl": href
                })

    # 3. Écriture du fichier JSON au lieu du CSV
    filename = "scrapcoinmaster.json"
    
    # Si aucun lien n'a été trouvé, on crée une structure d'erreur propre en JSON
    if not json_data:
        json_data.append({
            "Date Scraping": date_now,
            "Statut": "VIDE",
            "Message": "Aucun lien trouvé sur la page. Vérifiez manuellement le site."
        })
        print("Aucun lien extrait.")
    else:
        print(f"Succès total ! {len(json_data)} liens trouvés et sauvegardés malgré la protection.")

    # Écriture dans le fichier physique
    with open(filename, mode="w", encoding="utf-8") as json_file:
        # indent=4 : Crée des retours à la ligne propres (parfait pour les diffs GitHub)
        # ensure_ascii=False : Conserve les accents français (ex: "Quantité", "Evénement")
        json.dump(json_data, json_file, indent=4, ensure_ascii=False)
            
else:
    print(f"Erreur d'accès réseau (Code {status_code}). Le site bloque toujours.")


