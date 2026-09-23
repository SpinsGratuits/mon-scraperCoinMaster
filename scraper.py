import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# CONFIGURATION : Changement radical de source vers un média tolérant et ouvert aux robots
TARGET_URL = "https://dexerto.fr" 
JSON_FILE = "scrapcoinmaster.json"

def load_existing_links():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Supprime définitivement la ligne de test "static.moonactive.net/test"
                    return [item for item in data if "test" not in item.get("lienurl", "")]
                return []
        except json.JSONDecodeError:
            return []
    return []

def save_links(links_list):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(links_list, f, ensure_ascii=False, indent=4)
    print(f"Sauvegarde réussie : {len(links_list)} liens en ligne.")

def clean_reward_text(text):
    text = text.strip()
    if not text:
        return "Tours Gratuits"
    # Nettoie les textes et standardise en français si possible
    text = re.sub(r'(?i)cliquez ici|collecter|ici|link', '', text)
    return re.sub(r'\s+', ' ', text).strip()[:100]

def scrape_coin_master_links():
    print(f"Connexion réseau vers : {TARGET_URL}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur d'accès : {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    existing_data = load_existing_links()
    existing_urls = {item['lienurl'] for item in existing_data if 'lienurl' in item}
    
    new_links_count = 0
    anchors = soup.find_all('a', href=True)
    
    print(f"Analyse approfondie de {len(anchors)} hyperliens détectés...")

    for anchor in anchors:
        url = anchor['href'].strip()
        
        # Filtre absolu : cherche les liens contenant les schémas de redirection de Coin Master
        if any(p in url.lower() for p in ["vikalp.imobi", "coinmaster.rewards", "moonactive", "coin-master.co"]):
            if url not in existing_urls:
                reward_label = clean_reward_text(anchor.get_text())
                
                # Si le texte sur le bouton est trop court, on récupère la phrase complète autour
                if len(reward_label) < 4 and anchor.parent:
                    reward_label = clean_reward_text(anchor.parent.get_text())

                link_entry = {
                    "reward": reward_label if reward_label else "Bonus Coin Master",
                    "lienurl": url,
                    "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": int(datetime.utcnow().timestamp())
                }
                
                existing_data.insert(0, link_entry)
                existing_urls.add(url)
                new_links_count += 1
                print(f"-> Succès extraction : {reward_label} -> {url}")

    if new_links_count > 0:
        save_links(existing_data[:100])
    else:
        # Si le fichier est vide suite au nettoyage du lien de test, on applique un tableau propre
        if len(existing_data) == 0:
            print("Aucun lien extrait pour l'instant. Base de données purgée.")
            save_links([])
        else:
            print("Aucune nouveauté sur le site lors de cette heure.")

if __name__ == "__main__":
    scrape_coin_master_links()
