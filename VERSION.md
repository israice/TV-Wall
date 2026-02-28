Dev (Windows) — python run.py
- APP_HOST по умолчанию 127.0.0.1 — слушает только localhost
- APP_PORT по умолчанию 8000
- Открывать в браузере: http://localhost:8000
Prod (Docker/Ubuntu) — docker compose up -d --build
- APP_HOST=0.0.0.0 задаётся через environment в docker-compose.yml
- Порт 80 снаружи → 8000 внутри контейнера


https://iran.liveuamap.com/
https://geo-front.com/map
https://www.tzevaadom.co.il/en/
https://rocketalert.live/


https://github.com/Free-TV/IPTV.git
https://iptv-org.github.io/iptv/index.m3u
https://iptv-org.github.io/iptv/countries/il.m3u
https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8
https://tvpass.org/playlist/m3u
https://raw.githubusercontent.com/MARIKO578/IPTV/master/playlist.m3u8
https://iptv-org.github.io/iptv/index.m3u
https://iptv-org.github.io/iptv/countries/il.m3u
https://iptv-org.github.io/iptv/countries/ru.m3u


# START
python run.py


# RECOVERY
git log --oneline -n 5

Copy-Item .env $env:TEMP\.env.backup
git reset --hard 80f714fc
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force
python run.py

# UPDATE
git add .
git commit -m "v0.0.18 - fixed HOT PAGE RELOAD"
git push
python run.py

# DEV LOG
v0.0.18 - added adsense connection
v0.0.19 - add https auto redirect
v0.0.20 - fix html for ads aprooving stage
v0.0.21 - add google ads

v0.0.22 - added API request handling
