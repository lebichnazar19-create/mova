"""Публікація файлів у GitHub без git — через REST API (Git Data API):
blob-и -> дерево -> коміт -> зсув гілки. Один виклик = один коміт з усіма
файлами. Потрібен лише stdlib (urllib) і токен із правом на репозиторій.

Токен читається з налаштувань застосунку (налаштування.json у теці
застосунку) і ніколи не потрапляє у вивід чи повідомлення про помилки.
"""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

ФАЙЛ_НАЛАШТУВАНЬ = "налаштування.json"
РЕПО_ТИПОВЕ = "lebichnazar19-create/mova"
ГІЛКА_ТИПОВА = "main"
API = "https://api.github.com"


class ПомилкаПублікації(Exception):
    pass


# ---- налаштування (токен і репозиторій) --------------------------------------

def прочитати_налаштування(тека):
    """{"токен": ..., "репо": ..., "гілка": ...}; відсутні поля — типові/порожні."""
    дані = {}
    try:
        ф = Path(тека) / ФАЙЛ_НАЛАШТУВАНЬ
        if ф.is_file():
            дані = json.loads(ф.read_text(encoding="utf-8")) or {}
    except Exception:
        дані = {}
    return {
        "токен": (дані.get("токен") or "").strip(),
        "репо": (дані.get("репо") or РЕПО_ТИПОВЕ).strip(),
        "гілка": (дані.get("гілка") or ГІЛКА_ТИПОВА).strip(),
    }


def зберегти_налаштування(тека, **зміни):
    поточні = прочитати_налаштування(тека)
    for к, з in зміни.items():
        if з is not None:
            поточні[к] = з.strip()
    Path(тека).mkdir(parents=True, exist_ok=True)
    (Path(тека) / ФАЙЛ_НАЛАШТУВАНЬ).write_text(
        json.dumps(поточні, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return поточні


def замаскувати(токен):
    """Для показу в налаштуваннях: лише перші 4 символи."""
    if not токен:
        return "(не задано)"
    return токен[:4] + "…" + "·" * 6


# ---- API -------------------------------------------------------------------------

def _запит(токен, метод, шлях, дані=None, відкрити=urllib.request.urlopen):
    тіло = json.dumps(дані).encode("utf-8") if дані is not None else None
    запит = urllib.request.Request(
        API + шлях, data=тіло, method=метод,
        headers={
            "Authorization": "token " + токен,
            "Accept": "application/vnd.github+json",
            "User-Agent": "mova-app",
            "Content-Type": "application/json",
        },
    )
    try:
        with відкрити(запит, timeout=60) as відповідь:
            return json.loads(відповідь.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            повідомлення = json.loads(e.read().decode("utf-8")).get("message", "")
        except Exception:
            повідомлення = ""
        if e.code == 401:
            raise ПомилкаПублікації("GitHub відхилив токен (401). Перевір токен у «Налаштування».")
        if e.code == 404:
            raise ПомилкаПублікації(
                f"GitHub не знайшов {шлях} (404): перевір назву репозиторію і права токена (repo)."
            )
        raise ПомилкаПублікації(f"GitHub відповів {e.code} на {метод} {шлях}: {повідомлення}")
    except urllib.error.URLError as e:
        raise ПомилкаПублікації(f"Немає з'єднання з GitHub: {e.reason}")


def опублікувати(токен, репо, файли, повідомлення, гілка=ГІЛКА_ТИПОВА, відкрити=urllib.request.urlopen):
    """Один коміт із файлами {шлях_у_репо: str|bytes} у гілку. Повертає sha коміту."""
    if not токен:
        raise ПомилкаПублікації("Токен GitHub не задано — відкрий «Налаштування».")
    if not репо or "/" not in репо:
        raise ПомилкаПублікації("Репозиторій має бути у вигляді «власник/назва».")
    база = f"/repos/{репо}"
    ref = _запит(токен, "GET", f"{база}/git/ref/heads/{гілка}", відкрити=відкрити)
    батько = ref["object"]["sha"]
    коміт_батька = _запит(токен, "GET", f"{база}/git/commits/{батько}", відкрити=відкрити)
    дерево_бази = коміт_батька["tree"]["sha"]

    елементи = []
    for шлях, вміст in файли.items():
        байти = вміст if isinstance(вміст, bytes) else вміст.encode("utf-8")
        blob = _запит(токен, "POST", f"{база}/git/blobs",
                      {"content": base64.b64encode(байти).decode("ascii"), "encoding": "base64"},
                      відкрити=відкрити)
        елементи.append({"path": шлях, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    дерево = _запит(токен, "POST", f"{база}/git/trees",
                    {"base_tree": дерево_бази, "tree": елементи}, відкрити=відкрити)
    коміт = _запит(токен, "POST", f"{база}/git/commits",
                   {"message": повідомлення, "tree": дерево["sha"], "parents": [батько]}, відкрити=відкрити)
    _запит(токен, "PATCH", f"{база}/git/refs/heads/{гілка}", {"sha": коміт["sha"]}, відкрити=відкрити)
    return коміт["sha"]
