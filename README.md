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
3. На сервере (Docker):
   ```bash
   docker compose run --rm bot   # первый раз: ввести телефон и код, затем Ctrl+C
   docker compose up -d
   ```
4. Напишите боту `/start`, добавьте группы: `/add @username` или `/add https://t.me/+invite`.

Команды: `/chats`, `/add`, `/remove <id>`, `/stats`, `/pause`, `/resume`.

## Тесты

```bash
pytest -s
```
`tests/data/messages.csv` — размеченные примеры сообщений (`text,expected`; пустое `expected` = не заявка).
Каждую найденную ошибку классификации добавляйте сюда, затем правьте словари в `app/classifier.py`.
