import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# CONFIGURATION
TARGET_URL = "https://coinmasterfreespins.net" 
JSON_FILE = "scrapcoinmaster.json"

def load_existing_links():
    """Charge les liens déjà enregistrés pour éviter les doublons."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            print("Fichier JSON corrompu, réinitialisation.")
            return []
    return []

def save_links(links_list):
    """Sauvegarde la liste mise à jour dans le fichier JSON avec un formatage propre."""
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(links_list, f, ensure_ascii=False, indent=4)
    print(f"Base de données JSON mise à jour avec succès ({len(links_list)} liens au total).")

def clean_reward_text(text):
    """Nettoie le texte entourant le lien pour deviner la récompense (ex: '25 Spins')."""
    text = text.strip()
    if not text:
        return "Récompense Coin Master"
    return re.sub(r'\s+', ' ', text)[:100]

def scrape_coin_master_links():
    print(f"Démarrage du scraping sur : {TARGET_URL}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur lors de la récupération de la page : {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    existing_data = load_existing_links()
    
    # Si le fichier est vide, on désactive temporairement le blocage pour tout aspirer la première fois
    is_first_run = len(existing_data) == 0
    existing_urls = {item['lienurl'] for item in existing_data if 'lienurl' in item}
    
    new_links_count = 0

    # Recherche de toutes les balises de liens (<a>)
    for anchor in soup.find_all('a', href=True):
        url = anchor['href'].strip()
        
        # FILTRAGE : Recherche des patterns d'URL officiels de récompense Coin Master
        if "vikalp.imobi" in url or "CoinMaster.rewards" in url or "static.moonactive.net" in url:
            
            # Si c'est le premier lancement OU si le lien n'existe pas encore
            if is_first_run or (url not in existing_urls):
                reward_label = clean_reward_text(anchor.get_text())
                
                link_entry = {
                    "reward": reward_label,
                    "lienurl": url,
                    "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": int(datetime.utcnow().timestamp())
                }
                
                existing_data.append(link_entry)
                existing_urls.add(url)
                new_links_count += 1
                print(f"Lien détecté : {reward_label} -> {url}")

    if new_links_count > 0:
        print(f"{new_links_count} liens enregistrés.")
        # Garde les 100 derniers liens max
        save_links(existing_data[-100:])
    else:
        print("Aucun lien détecté lors de ce passage.")

if __name__ == "__main__":
    scrape_coin_master_links()
