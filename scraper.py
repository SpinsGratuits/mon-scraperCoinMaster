import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# NOUVELLE CONFIGURATION : Agrégateur stable souvent mis à jour
TARGET_URL = "https://hityah.com" 
JSON_FILE = "scrapcoinmaster.json"

def load_existing_links():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []

def save_links(links_list):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(links_list, f, ensure_ascii=False, indent=4)
    print(f"Sauvegarde réussie : {len(links_list)} liens.")

def clean_reward_text(text):
    text = text.strip()
    if not text:
        return "Récompense Coin Master"
    return re.sub(r'\s+', ' ', text)[:100]

def scrape_coin_master_links():
    print(f"Connexion à : {TARGET_URL}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Le site bloque la connexion : {e}")

    soup = BeautifulSoup(response.text, 'html.parser')
    existing_data = load_existing_links()
    existing_urls = {item['lienurl'] for item in existing_data if 'lienurl' in item}
    
    new_links_count = 0
    anchors = soup.find_all('a', href=True)
    
    print(f"Analyse de {len(anchors)} liens trouvés sur la page...")

    for anchor in anchors:
        url = anchor['href'].strip()
        
        # Filtre large pour attraper les redirections Coin Master courantes
        if any(pattern in url for pattern in ["vikalp.imobi", "CoinMaster.rewards", "static.moonactive.net", "coin-master.co"]):
            if url not in existing_urls:
                reward_label = clean_reward_text(anchor.get_text())
                
                link_entry = {
                    "reward": reward_label,
                    "lienurl": url,
                    "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": int(datetime.utcnow().timestamp())
                }
                
                existing_data.insert(0, link_entry)
                existing_urls.add(url)
                new_links_count += 1
                print(f"Ajout : {reward_label} -> {url}")

    if new_links_count > 0:
        save_links(existing_data[:100])
    else:
        # SI LE FICHIER ÉTAIT VIDE, ON FORCE AU MOINS UNE ENTRÉE DE TEST POUR VALIDER LE FONCTIONNEMENT DE GIT
        if len(existing_data) == 0:
            print("Aucun lien compatible trouvé, génération d'une entrée de test de sécurité.")
            test_entry = {
                "reward": "Lancement initial réussi - En attente de nouveaux bonus",
                "lienurl": "https://moonactive.net",
                "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": int(datetime.utcnow().timestamp())
            }
            save_links([test_entry])
        else:
            print("Pas de nouveau lien détecté.")

if __name__ == "__main__":
    scrape_coin_master_links()
