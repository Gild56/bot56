import requests
import random
import os
import json
import typing as t


def get_all_levels():
    BASE_URL = "https://api.demonlist.org/levels/classic"
    LEVELS: list[dict[str, t.Any]] = []
    AFTER = None

    params = {"limit": 2000}
    if AFTER:
        params["after"] = AFTER

    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")

    data = response.json().get("data", [])
    if not data:
        print("No levels found.")

    LEVELS.extend(data)

    return LEVELS


def get_level_info(id: int | None):
    url = f"https://api.demonlist.org/levels/classic?id={id}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    data = response.json().get("data", [])
    if not data:
        print(f"No levels with the {id} ID.")
        return None

    level = data[0]
    return level

def get_random_level():
    path = "src/images"
    folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
    return random.choice(folders)

def get_level_id_by_name(level_name: str):
    file_path="src/demonlist_levels.json"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            levels = json.load(f)
    except FileNotFoundError:
        print("Le fichier JSON n'a pas été trouvé.")
        return None
    except json.JSONDecodeError:
        print("Erreur lors de la lecture du JSON.")
        return None

    for level in levels:
        if level.get("name", "").lower() == level_name.lower():
            return level.get("id")

    return None
