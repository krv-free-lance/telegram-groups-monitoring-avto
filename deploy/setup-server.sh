#!/usr/bin/env bash
# Телеграм-мониторинг заявок на сервере под общим пользователем apps — запуск от root.
#
#   cd /root/projects/telegram-groups-monitoring-avto && git fetch origin claude/brave-wright-nzny1k
#   git show origin/claude/brave-wright-nzny1k:deploy/setup-server.sh > /root/setup-tg.sh
#   bash /root/setup-tg.sh
#
# Пользователь apps — общий для своих проектов на сервере (ставит deploy/setup-apps.sh проекта
# bcs-trading-bot); у этого проекта своя папка, служба tg-monitor, sudoers-файл и deploy key.
# Повторный запуск безопасен. Старая копия /root/projects/telegram-groups-monitoring-avto не трогается.
#
# После скрипта один раз — вход аккаунта, который читает группы (спросит телефон и код из Telegram):
#   sudo -u apps -H bash -c 'cd ~/telegram-groups-monitoring-avto && .venv/bin/python -m app.login'
#   systemctl restart tg-monitor
set -euo pipefail

U=apps
H=/home/$U
OLD=${OLD:-/root/projects/telegram-groups-monitoring-avto}
DIR=$H/telegram-groups-monitoring-avto
BRANCH=claude/brave-wright-nzny1k
REPO_PATH=krv-free-lance/telegram-groups-monitoring-avto.git
# deploy key привязан к одному репозиторию; у apps их несколько — нужный выбирается по Host в ~/.ssh/config
GH_ALIAS=github-tgmon
SVC=tg-monitor

step() { echo; echo "== $*"; }
as_u() { sudo -u "$U" -H bash -lc "$1"; }

[ "$(id -u)" = 0 ] || { echo "запускать от root"; exit 1; }
id "$U" >/dev/null 2>&1 || { echo "нет пользователя $U: сначала deploy/setup-apps.sh проекта bcs-trading-bot"; exit 1; }
for c in git python3 rsync; do command -v $c >/dev/null || { echo "нет $c"; exit 1; }; done

step "1. Deploy key для этого репозитория"
if [ ! -f "$H/.ssh/id_ed25519_tgmon" ]; then
    as_u "ssh-keygen -q -t ed25519 -N '' -C '$U@$(hostname) tg-monitor' -f ~/.ssh/id_ed25519_tgmon"
fi
if ! grep -q "^Host $GH_ALIAS\$" "$H/.ssh/config" 2>/dev/null; then
    cat >> "$H/.ssh/config" <<EOF

# telegram-groups-monitoring-avto: свой deploy key (deploy/setup-server.sh)
Host $GH_ALIAS
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_tgmon
    IdentitiesOnly yes
EOF
    chown "$U:$U" "$H/.ssh/config"; chmod 600 "$H/.ssh/config"
fi
as_u "ssh-keyscan -t ed25519 github.com 2>/dev/null >> ~/.ssh/known_hosts; sort -u -o ~/.ssh/known_hosts ~/.ssh/known_hosts"

step "2. Код (клон ключом root, дальше — владелец $U, origin через свой ключ)"
if [ ! -d "$DIR/.git" ]; then
    git clone -q -b "$BRANCH" "git@github.com:$REPO_PATH" "$DIR"
    git -C "$DIR" remote set-url origin "git@$GH_ALIAS:$REPO_PATH"
fi
chown -R "$U:$U" "$DIR"

step "3. Секреты и данные из старой копии"
if [ ! -f "$DIR/.env" ]; then
    install -m 600 -o "$U" -g "$U" "$OLD/.env" "$DIR/.env"
    echo ".env перенесён (600, только $U)"
fi
if [ ! -d "$DIR/data" ]; then
    rsync -a "$OLD/data/" "$DIR/data/"
    chown -R "$U:$U" "$DIR/data"; chmod 700 "$DIR/data"
    echo "data/ перенесён (база групп и заявок, сессия)"
fi

step "4. Окружение Python"
if [ ! -x "$DIR/.venv/bin/python" ]; then
    as_u "cd $DIR && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt"
else
    as_u "cd $DIR && .venv/bin/pip install -q -r requirements.txt"
fi

step "5. Служба $SVC"
install -m 644 "$DIR/deploy/$SVC.service" "/etc/systemd/system/$SVC.service"
systemctl daemon-reload
systemctl enable "$SVC" >/dev/null
cat > "/etc/sudoers.d/$U-$SVC" <<EOF
# apps: служба телеграм-мониторинга (deploy/setup-server.sh)
$U ALL=(root) NOPASSWD: /usr/bin/systemctl start $SVC, /usr/bin/systemctl stop $SVC, /usr/bin/systemctl restart $SVC
EOF
chmod 440 "/etc/sudoers.d/$U-$SVC"
visudo -cf "/etc/sudoers.d/$U-$SVC" >/dev/null || { rm -f "/etc/sudoers.d/$U-$SVC"; echo "sudoers не прошёл проверку — удалён"; exit 1; }

step "6. Сессия аккаунта-читателя"
if as_u "cd $DIR && .venv/bin/python -c '
import asyncio, sys
from telethon import TelegramClient
from app.config import Settings
from app.proxy import telethon_proxy_kwargs
async def ok():
    s = Settings()
    c = TelegramClient(str(s.session_path), s.api_id, s.api_hash, **telethon_proxy_kwargs(s.proxy_url, s.mtproxy))
    await c.connect()
    try:
        return await c.is_user_authorized()
    finally:
        await c.disconnect()
sys.exit(0 if asyncio.run(ok()) else 1)
'"; then
    systemctl restart "$SVC"
    sleep 5
    echo "сессия действует, $SVC: $(systemctl is-active $SVC) — в боте должно прийти «Мониторинг запущен»"
else
    systemctl stop "$SVC" 2>/dev/null || true
    echo "!! Сессия недействительна — войдите (спросит телефон и код из Telegram), затем запустите службу:"
    echo "   sudo -u $U -H bash -c 'cd ~/telegram-groups-monitoring-avto && .venv/bin/python -m app.login'"
    echo "   systemctl restart $SVC"
fi

step "7. GitHub"
if as_u "ssh -o BatchMode=yes -T git@$GH_ALIAS" 2>&1 | grep -q "successfully authenticated"; then
    echo "ключ работает: git pull в $DIR — через свой deploy key"
else
    echo "!! Добавьте ключ как deploy key (только чтение достаточно):"
    echo "   github.com/${REPO_PATH%.git} → Settings → Deploy keys → Add deploy key"
    echo
    cat "$H/.ssh/id_ed25519_tgmon.pub"
fi
echo
echo "ГОТОВО. Состояние — /status в боте; журнал — journalctl -u $SVC -f"
