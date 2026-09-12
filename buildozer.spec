[app]

# Назва застосунку (показується в списку застосунків Android) —
# може бути кирилицею, на відміну від package.name/package.domain нижче.
title = Мова

# package.name/package.domain формують ідентифікатор Android-застосунку
# (тут: org.mova.mova) — за вимогами Android/Java мають бути латиницею,
# нижнім регістром, без дефісів.
package.name = mova
package.domain = org.mova

# Корінь проєкту — увесь репозиторій (ядро/, main.py, тести/ тощо).
source.dir = .

# Які файли з source.dir пакувати в APK за розширенням.
# "мова" — на майбутнє, коли демо/приклади (*.мова) підключатимуться як
# файли-активи, а не як рядок просто в main.py.
source.include_exts = py,png,jpg,kv,atlas,мова

# Не тягнути в APK нічого зайвого: git-метадані, кеші тестів, байткод,
# готові білди Buildozer з попередніх запусків.
source.exclude_dirs = .git,.github,.pytest_cache,__pycache__,тести,приклади,.buildozer,bin
source.exclude_patterns = *.pyc,*.байт,*.spec.local

version = 0.1

# Мінімум: сам інтерпретатор — чистий stdlib Python, жодних сторонніх
# pip-пакетів йому не треба (див. ПЛАН_APK.md, розділ 0). Kivy — лише
# для UI-оболонки (main.py). Коли дійде до реального заліза (вібрація
# тощо, окреме завдання) — сюди додасться plyer/pyjnius.
requirements = python3,kivy

orientation = portrait
fullscreen = 0

# Дозволів поки що не потрібно — main.py не викликає жодної функції з
# ядро/пристрій.py (вібрація/камера/GPS тощо), лише компілятор і VM
# у симуляційному режимі. Розкоментувати в міру потреби, коли з'явиться
# реальна робота з пристроєм:
# android.permissions = VIBRATE,CAMERA,ACCESS_FINE_LOCATION

# Одна ABI — швидша й менша збірка для CI (детальніше — ПЛАН_APK.md,
# розділ 1.A, про розмір APK); за потреби розширити на кілька архітектур
# перед публікацією для реальних пристроїв.
android.archs = arm64-v8a

# Зафіксовано явно, а не автовибір найновішого: build-tools 37
# (автовибір за замовчуванням) падав у CI з "license is not accepted"
# для щойно вийшлого компонента, для якого ще не було кроку прийняття
# ліцензій. 34.0.0/API 34/NDK 25b — стабільна, давно обкатана комбінація.
android.build_tools_version = 34.0.0
android.api = 34
android.ndk = 25b

log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
