import requests
import random


def get_all_levels():
    BASE_URL = "https://api.demonlist.org/level/classic/list"
    response = requests.get(BASE_URL)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")

    data = response.json().get("data", [])
    if not data:
        print("No levels found.")

    return response.json().get("data", []).get("levels", [])


def get_level_info(id: int | None):
    url = f"https://api.demonlist.org/level/classic/get?id={id}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    data = response.json().get("data", [])
    if not data:
        print(f"No levels with the {id} ID.")
        return None

    return data

def get_random_level():
    all_levels = get_all_levels()
    return random.choice(all_levels).get("name")

def get_level_id_by_name(level_name: str):
    levels = get_all_levels()

    for level in levels:
        if level.get("name", "").lower() == level_name.lower():
            return level.get("id")

    return None
