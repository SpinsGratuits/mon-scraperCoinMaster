import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# CONFIGURATION : Source alternative optimisée anti-blocage robot
TARGET_URL = "https://allclash.com" 
JSON_FILE = "scrapcoinmaster.json"

def load_existing_links():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Nettoyage automatique de l'ancienne entrée de test si elle existe
                    return [item for item in data if "static.moonactive.net/test" not in item.get("lienurl", "")]
                return []
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
    # Traduit ou nettoie les textes basiques
    text = text.replace("Collect Here", "Collecter").replace("Collect", "Collecter")
    return re.sub(r'\s+', ' ', text)[:100]

def scrape_coin_master_links():
    print(f"Connexion sécurisée à : {TARGET_URL}")
    
    # Simulation d'un navigateur résidentiel pour éviter la détection robot
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur d'accès à la cible : {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    existing_data = load_existing_links()
    existing_urls = {item['lienurl'] for item in existing_data if 'lienurl' in item}
    
    new_links_count = 0
    anchors = soup.find_all('a', href=True)
    
    print(f"Analyse de {len(anchors)} liens bruts sur la page...")

    for anchor in anchors:
        url = anchor['href'].strip()
        
        # Filtre absolu Coin Master (inclut les redirections et raccourcisseurs d'URL du jeu)
        if any(p in url.lower() for p in ["vikalp.imobi", "coinmaster.rewards", "moonactive", "coin-master.co", "static.moonactive"]):
            if url not in existing_urls:
                # Récupère le texte de la récompense (souvent "25 spins" ou la date du jour)
                reward_label = clean_reward_text(anchor.get_text())
                
                # Si le lien est juste une image ou un mot court, on prend le texte de la ligne entière
                if len(reward_label) < 4 and anchor.parent:
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
                print(f"Nouveau lien capturé : {reward_label} -> {url}")

    if new_links_count > 0:
        save_links(existing_data[:100])
    else:
        # Si le fichier est vide (car épuré du test), on remet une structure propre
        if len(existing_data) == 0:
            print("Aucun nouveau lien sur cette source pour l'instant. Structure validée.")
            save_links([])
        else:
            print("Pas de nouveauté lors de ce passage.")

if __name__ == "__main__":
    scrape_coin_master_links()
