#!/usr/bin/env bash
# Телеграм-мониторинг заявок на сервере под общим пользователем apps — запуск от root.
#
#   cd /root/projects/telegram-groups-monitoring-avto && git fetch origin claude/brave-wright-nzny1k
#   git show origin/claude/brave-wright-nzny1k:deploy/setup-server.sh > /root/setup-tg.sh
#   bash /root/setup-tg.sh
#
# Пользователь apps — общий не-root пользователь для своих проектов на сервере (нет — создаётся);
# у этого проекта своя папка, служба tg-monitor и sudoers-файл. На GitHub сервер не ходит: deploy keys
# в организации запрещены, а ключ аккаунта на сервере — доступ ко всем репозиториям. Обновления —
# git push с машины разработчика прямо в копию на сервере (receive.denyCurrentBranch=updateInstead).
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
SVC=tg-monitor

step() { echo; echo "== $*"; }
as_u() { sudo -u "$U" -H bash -lc "$1"; }

[ "$(id -u)" = 0 ] || { echo "запускать от root"; exit 1; }
for c in git python3 rsync; do command -v $c >/dev/null || { echo "нет $c"; exit 1; }; done

step "0. Пользователь $U"
if ! id "$U" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "$U"
    passwd -l "$U" >/dev/null
fi
usermod -aG systemd-journal "$U"   # journalctl -u tg-monitor без sudo
install -d -m 700 -o "$U" -g "$U" "$H/.ssh"
# входить в apps можно теми же ключами, что и в root
[ -f "$H/.ssh/authorized_keys" ] || install -m 600 -o "$U" -g "$U" /root/.ssh/authorized_keys "$H/.ssh/authorized_keys"

step "1. Код (первый клон — ключом root; дальше обновления пушем с машины разработчика)"
if [ ! -d "$DIR/.git" ]; then
    git clone -q -b "$BRANCH" "git@github.com:$REPO_PATH" "$DIR"
fi
git -C "$DIR" remote remove origin 2>/dev/null || true   # без ключа на сервере origin не работает
chown -R "$U:$U" "$DIR"
# push в текущую ветку обновляет рабочую копию, если в ней нет локальных правок
as_u "git -C $DIR config receive.denyCurrentBranch updateInstead"

step "2. Секреты и данные из старой копии"
if [ ! -f "$DIR/.env" ]; then
    install -m 600 -o "$U" -g "$U" "$OLD/.env" "$DIR/.env"
    echo ".env перенесён (600, только $U)"
fi
if [ ! -d "$DIR/data" ]; then
    rsync -a "$OLD/data/" "$DIR/data/"
    chown -R "$U:$U" "$DIR/data"; chmod 700 "$DIR/data"
    echo "data/ перенесён (база групп и заявок, сессия)"
fi

step "3. Окружение Python"
if [ ! -x "$DIR/.venv/bin/python" ]; then
    as_u "cd $DIR && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt"
else
    as_u "cd $DIR && .venv/bin/pip install -q -r requirements.txt"
fi

step "4. Служба $SVC"
install -m 644 "$DIR/deploy/$SVC.service" "/etc/systemd/system/$SVC.service"
install -m 644 "$DIR/deploy/$SVC-failed.service" "/etc/systemd/system/$SVC-failed.service"
systemctl daemon-reload
systemctl enable "$SVC" >/dev/null
cat > "/etc/sudoers.d/$U-$SVC" <<EOF
# apps: служба телеграм-мониторинга (deploy/setup-server.sh)
$U ALL=(root) NOPASSWD: /usr/bin/systemctl start $SVC, /usr/bin/systemctl stop $SVC, /usr/bin/systemctl restart $SVC
EOF
chmod 440 "/etc/sudoers.d/$U-$SVC"
visudo -cf "/etc/sudoers.d/$U-$SVC" >/dev/null || { rm -f "/etc/sudoers.d/$U-$SVC"; echo "sudoers не прошёл проверку — удалён"; exit 1; }

step "5. Сессия аккаунта-читателя"
if systemctl is-active -q "$SVC"; then
    # Работающая служба — уже доказательство живой сессии (с мёртвой она выходит с кодом 2).
    # Проверять параллельно нельзя: вторая копия с тем же файлом сессии получает ошибку,
    # и проверка принимала её за «сессия недействительна» — и останавливала рабочую службу.
    systemctl restart "$SVC"
    sleep 5
    echo "служба работала — перезапущена с новым кодом: $(systemctl is-active $SVC)"
elif as_u "cd $DIR && .venv/bin/python -c '
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

step "6. Обновления"
echo "с машины разработчика:"
echo "   git remote add server $U@$(hostname -I | awk '{print $1}'):telegram-groups-monitoring-avto   # один раз"
echo "   git push server $BRANCH && ssh $U@$(hostname -I | awk '{print $1}') 'sudo systemctl restart $SVC'"
echo
echo "ГОТОВО. Состояние — /status в боте; журнал — journalctl -u $SVC -f"
