[app]

# Назва застосунку (показується в списку застосунків Android) —
# може бути кирилицею, на відміну від package.name/package.domain нижче.
title = Мова

# package.name/package.domain формують ідентифікатор Android-застосунку
# (тут: org.mova.mova) — за вимогами Android/Java мають бути латиницею,
# нижнім регістром, без дефісів.
package.name = mova
package.domain = org.mova

# Корінь проєкту — увесь репозиторій (yadro/, main.py, тести/ тощо).
source.dir = .

# Які файли з source.dir пакувати в APK за розширенням.
# "мова" — на майбутнє, коли демо/приклади (*.мова) підключатимуться як
# файли-активи, а не як рядок просто в main.py.
source.include_exts = py,png,jpg,kv,atlas,мова,bin

# Не тягнути в APK нічого зайвого: git-метадані, кеші тестів, байткод,
# готові білди Buildozer з попередніх запусків.
source.exclude_dirs = .git,.github,.pytest_cache,__pycache__,тести,приклади,застосунки,.buildozer,bin,tools
source.exclude_patterns = *.pyc,*.байт,*.spec.local

# Версія — з yadro/versiya.py (єдине джерело; там ВЕРСІЯ = "…")
version.regex = ВЕРСІЯ = "([^"]+)"
version.filename = %(source.dir)s/yadro/versiya.py
# versionCode: має зростати з кожною версією (інакше Android не перезапише
# старий застосунок). Літерал = yadro.versiya.ЧИСЛОВА_ВЕРСІЯ (1.3 -> 10300);
# workflow підставляє його перед збіркою, тест стежить за збігом.
android.numeric_version = 10400

# Мінімум: сам інтерпретатор — чистий stdlib Python, жодних сторонніх
# pip-пакетів йому не треба (див. ПЛАН_APK.md, розділ 0). Kivy — лише
# для UI-оболонки (main.py). Коли дійде до реального заліза (вібрація
# тощо, окреме завдання) — сюди додасться plyer/pyjnius.
#
# kivy==2.3.0 зафіксовано разом із p4a.branch нижче — без пінів
# найновіший python-for-android сам підтягує найновішу гілку p4a і з
# нею найновіший Python (зараз 3.14), а той тягне *.whl, зібрані під
# cp314 — pip їх відхиляє на етапі "Installing Python modules with pip"
# ("... is not a supported wheel on this platform").
requirements = python3,kivy==2.3.0,pygments

# Зафіксовано конкретний реліз python-for-android (замість гілки
# develop за замовчуванням) — v2024.01.21 ще збирає Python 3.11, а не
# 3.14.
p4a.branch = v2024.01.21

orientation = portrait
fullscreen = 0

# Дозволів поки що не потрібно — main.py не викликає жодної функції з
# yadro/prystriy.py (вібрація/камера/GPS тощо), лише компілятор і VM
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
# ліцензій.
android.build_tools_version = 34.0.0
android.api = 34
# p4a.branch = v2024.01.21 вище вимагає NDK >= 25 ("The minimum
# supported NDK version is 25" / "Recommended android's NDK version by
# p4a is: 25b" — з логу збірки; попередня спроба поставити 23b була
# хибним припущенням, не підтвердженим реальним білдом).
android.ndk = 25b

# ---- зв'язок з платами по USB (yadro/plata.py, етап 1: пульт) ----
# usb-serial-for-android (CH340, CP2102, FTDI, CDC-ACM) — з jitpack
android.gradle_dependencies = com.github.mik3y:usb-serial-for-android:3.7.0
android.add_gradle_repositories = maven { url 'https://jitpack.io' }
# intent-filter USB_DEVICE_ATTACHED + device_filter.xml + uses-feature usb.host
android.manifest.intent_filters = android/intent_filters.xml
android.add_resources = android/xml:xml
android.extra_manifest_xml = android/extra_manifest.xml
android.permissions = INTERNET

log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
