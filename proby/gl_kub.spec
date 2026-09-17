# Buildozer для проби OpenGL (proby/gl_kub.py). Buildozer шукає лише
# buildozer.spec у поточній теці, тому workflow «Проби» копіює цей файл
# як buildozer.spec, а gl_kub.py — як main.py в окрему теку збірки.
# Налаштування збірки (p4a, NDK, API) — ті самі, що в головному
# buildozer.spec, щоб кеш SDK/NDK на раннері був спільний.

[app]
title = Проба GL
package.name = probagl
package.domain = org.mova
source.dir = .
source.include_exts = py
source.exclude_dirs = __pycache__,.buildozer,bin
version = 0.1
android.numeric_version = 1
requirements = python3,kivy==2.3.0
p4a.branch = v2024.01.21
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.build_tools_version = 34.0.0
android.api = 34
android.ndk = 25b
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
