import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# CONFIGURATION CIBLE
TARGET_URL = "https://hityah.com" 
JSON_FILE = "scrapcoinmaster.json"

def load_existing_links():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Si le fichier contient notre lien de test, on l'efface pour laisser place aux vrais liens
                if isinstance(data, list) and len(data) == 1 and "test" in data[0].get("lienurl", ""):
                    return []
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur de connexion : {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    existing_data = load_existing_links()
    existing_urls = {item['lienurl'] for item in existing_data if 'lienurl' in item}
    
    new_links_count = 0

    # Analyse de tous les liens de la page
    for anchor in soup.find_all('a', href=True):
        url = anchor['href'].strip()
        
        # Filtre étendu pour intercepter absolument toutes les formes de liens de récompenses
        if any(p in url.lower() for p in ["vikalp.imobi", "coinmaster.rewards", "moonactive", "coin-master.co", "static.moonactive"]):
            if url not in existing_urls:
                reward_label = clean_reward_text(anchor.get_text())
                
                # Si le texte du lien est vide ou trop générique (ex: "Collect"), on cherche le texte autour
                if len(reward_label) < 3 and anchor.parent:
                    reward_label = clean_reward_text(anchor.parent.get_text())

                link_entry = {
                    "reward": reward_label,
                    "lienurl": url,
                    "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": int(datetime.utcnow().timestamp())
                }
                
                existing_data.insert(0, link_entry)
                existing_urls.add(url)
                new_links_count += 1
                print(f"Nouveau lien trouvé : {reward_label} -> {url}")

    if new_links_count > 0:
        save_links(existing_data[:100])
    else:
        # Si aucun lien n'est trouvé et que la liste est vide, on garde une trace d'activité
        if len(existing_data) == 0:
            print("Aucun lien détecté sur cette structure. En attente de la prochaine mise à jour du site.")
            backup_entry = {
                "reward": "En attente de nouveaux liens",
                "lienurl": "https://moonactive.net",
                "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": int(datetime.utcnow().timestamp())
            }
            save_links([backup_entry])
        else:
            print("Pas de nouveau lien détecté lors de ce passage.")

if __name__ == "__main__":
    scrape_coin_master_links()
