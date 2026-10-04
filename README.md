# telegram-groups-monitoring-avto
Telegram-бот для автоматического поиска заявок

https://freelance.ru/task/view/10539

Нужен разработчик Telegram-бота для автоматического мониторинга профильных Telegram-групп.

Задача: бот должен отслеживать выбранные мной группы/каналы по СПб и ЛО, анализировать новые сообщения и находить потенциальные заявки:

🚛 «нужен самосвал»
🚛 «нужны машины»
🚛 «вывоз грунта/боя»
🟢 «продам вторичный щебень/бой»
🔵 «куплю вторичный щебень/бой»

При обнаружении подходящей заявки бот отправляет мне уведомление в личный Telegram с:
— текстом объявления;
— категорией;
— датой/временем;
— ссылкой на оригинальное сообщение;
— кнопками «Интересно / Не интересно».

---

## Запуск

1. Скопируйте `.env.example` в `.env` и заполните:
   - `API_ID`, `API_HASH` — https://my.telegram.org → API development tools (аккаунт, который будет читать группы);
   - `BOT_TOKEN` — @BotFather → `/mybots` → API Token;
   - `OWNER_ID` — ваш ID из @userinfobot.
2. Локально:
   ```bash
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements-dev.txt
   python -m app.main
   ```
   При первом запуске Telethon спросит номер телефона и код входа — сессия сохранится в `data/`.
3. На сервере — служба systemd под общим пользователем `apps` (не root): `deploy/setup-server.sh`
   (запуск от root, повторный безопасен; что делает — в шапке скрипта). Затем один раз вход аккаунта,
   который читает группы:
   ```bash
   sudo -u apps -H bash -c 'cd ~/telegram-groups-monitoring-avto && .venv/bin/python -m app.login'
   systemctl restart tg-monitor
   ```
   **Обновление кода** — пушем с машины разработчика прямо на сервер (deploy keys в организации запрещены,
   а ключ аккаунта на сервере давал бы доступ ко всем репозиториям):
   ```bash
   git remote add server apps@<сервер>:telegram-groups-monitoring-avto   # один раз
   git push server claude/brave-wright-nzny1k && ssh apps@<сервер> 'sudo systemctl restart tg-monitor'
   ```
   Сервис сам никогда не спрашивает телефон: если сессия слетела, бот пишет владельцу и служба
   останавливается (код 2, без перезапусков) — нужен повторный `app.login`.
4. Напишите боту `/start`, добавьте группы: `/add @username` или `/add https://t.me/+invite`.

Команды: `/status`, `/chats`, `/add`, `/remove <id>`, `/stats`, `/pause`, `/resume`.

**Работает ли?** При каждом запуске бот пишет «✅ Мониторинг запущен». `/status` — аккаунт, число групп,
время запуска, когда последний раз приходило сообщение из Telegram, число заявок. Журнал службы:
`journalctl -u tg-monitor -f`.

## Тесты

```bash
pytest -s
```
`tests/data/messages.csv` — размеченные примеры сообщений (`text,expected`; пустое `expected` = не заявка).
Каждую найденную ошибку классификации добавляйте сюда, затем правьте словари в `app/classifier.py`.
