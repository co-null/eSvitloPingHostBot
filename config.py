SETTINGS_FILE = 'user_settings.json'
STATES_FILE = 'user_states.json'
SCHEDULE_FILE='blackout_schedule.json'
LOG_FILE = 'errors.log'
TZ = 'Europe/Kiev'
LISTENER_URL = 'http://35.192.99.228:5000/send?chat_id='
LOCAL_URL = 'http://127.0.0.1:5000/send?chat_id='
ALIVE='alive'
OFF='not reachable'
SCHEDULE_PING=1
SCHEDULE_LISTEN=1
SCHEDULE_GATHER_SCHEDULE=60
SCHEDULE_SET_NOTIFICATION=30
SCHEDULE_SEND_NOTIFICATION=3
YASNO_URL = 'https://api.yasno.com.ua/api/v1/pages/home/schedule-turn-off-electricity'
DTEK_CHANNEL_ID = '@dtek_ua'
isPostOK="F"
msg_greeting="Вітаю! Налаштуйте бот для перевірки доступності IP адреси кожну хвилину (для старту моніторингу адреса має бути доступна), або ввімкніть режим прослуховування. Є можливість публікації повідомлень у канал (для цього попередньо додайте бот в канал)"
msg_comeback="З поверненням!"
msg_error="Виникла помилка, перезапустіть бота"
msg_mainmnu="Головне меню"
msg_setip="Будь ласка, введіть IP (v4) адресу для моніторингу (за необхідності порт можна вказати через двокрапку), або знак '-' (дефіс), щоб видалити вказану раніше:"
msg_setlabel="Будь ласка введіть назву адреси для моніторингу, або знак '-' (дефіс), щоб видалити вказану раніше:"
msg_setchannel="Будь ласка введіть ID каналу для публікації (для приватних - числовий ІД), або знак '-' (дефіс), щоб видалити вказану раніше:"
msg_setcity="Є можливість підлючити графік відключень від Yasno чи ДТЕК. Наразі доступні міста:"
msg_setcitybottom="Введіть назву міста, або знак " + "'-'" + " (дефіс), щоб скасувати"
msg_setgroup="Будь ласка, введіть групу, до якої належить ваш будинок для отримання графіків відключень,\n або " + "'-'" + ", щоб скасувати"
msg_reminder_no_schedule="Для активації нагадувань необхідно підлючити графік відключень електроенергії\nНагадування спрацьовують приблизно за 15 хв. до планового відключення (не в сірій зоні).\nНагадування припиняють надсилатися, якщо останню добу відключень не було"
msg_reminder_turnon="Нагадування спрацьовуватимуть приблизно за 15 хв. до планового відключення (не в сірій зоні).\nНагадування припиняють надсилатися, якщо останню добу відключень не було"
msg_reminder_on="Нагадування ввімкнено\n"
msg_reminder_off="Нагадування вимкнено\n"
msg_settings="Поточні налаштування:"
msg_noip='IP адреса не вказана. Будь ласка, використайте "Вказати IP адресу для моніторингу"'
msg_ippingon="Пінг IP адреси ввімкнено\n"
msg_ippingondetailed="Буде активовано моніторинг по IP адресі (слухача ввімкнено не буде, вимкайте слухача окремо тільки після налаштування зі своєї сторони)"
msg_ippingoff="Пінг IP адреси вимкнено\n"
msg_listeneron="Режим слухача ввімкнено\n" 
msg_listeneroff="Режим слухача вимкнено\n"
msg_boton="Публікація в бот ввімкнена\n"
msg_botoff="Публікація в бот вимкнена\n"
msg_channelon="Публікація в канал ввімкнена\n"
msg_channeloff="Публікація в канал вимкнена\n"
msg_stopped="Моніторинг зупинено"
msg_notset="Моніторинг не налаштовано"
msg_postbot="Публікація в бот ввімкнена"
msg_postchannel="Публікація в канал ввімкнена"
msg_nopostbot="Публікація в бот вимкнена"
msg_nopostchannel="Публікація в канал вимкнена"
msg_nochannel="Канал не вказано"
msg_alive="💡Електрохарчування *є*!"
msg_blackout="🔦 Немає світла!"