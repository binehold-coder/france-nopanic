"""User-facing strings in Ukrainian and Russian."""

from __future__ import annotations

T: dict[str, dict[str, str]] = {
    "choose_lang": {
        "uk": "Оберіть мову / Выберите язык / Choisissez la langue :",
        "ru": "Оберіть мову / Выберите язык / Choisissez la langue :",
        "fr": 'Оберіть мову / Выберите язык / Choisissez la langue :',
    },
    "welcome": {
        "uk": (
            "Вітаю! Я — «Франція без паніки» 🇫🇷🇺🇦\n\n"
            "Надішліть мені фото або PDF листа французькою (CAF, префектура, податкова, "
            "France Travail, банк, школа…) — і я поясню:\n"
            "📨 хто пише\n🧾 чого хочуть\n⏰ який термін\n✅ що робити по кроках\n\n"
            "Можна кілька фото одним повідомленням — це сторінки одного листа.\n"
            "Бланк CERFA теж можна — поясню, що писати в кожне поле.\n\n"
            "{free}"
        ),
        "ru": (
            "Привет! Я — «Франция без паники» 🇫🇷🇺🇦\n\n"
            "Пришлите мне фото или PDF письма на французском (CAF, префектура, налоговая, "
            "France Travail, банк, школа…) — и я объясню:\n"
            "📨 кто пишет\n🧾 чего хотят\n⏰ какой срок\n✅ что делать по шагам\n\n"
            "Можно несколько фото одним сообщением — это страницы одного письма.\n"
            "Бланк CERFA тоже можно — объясню, что писать в каждое поле.\n\n"
            "{free}"
        ),
        "fr": "Bonjour ! Je suis « France sans panique » 🇫🇷🇺🇦\n\nEnvoyez-moi une photo ou un PDF d'un courrier administratif (CAF, préfecture, impôts, France Travail, banque, école…) et je vous explique simplement :\n📨 qui écrit\n🧾 ce qu'on vous demande\n⏰ le délai\n✅ quoi faire, étape par étape\n\nPlusieurs photos dans un seul message = les pages d'un même courrier.\nUn formulaire CERFA aussi : j'explique quoi écrire dans chaque case.\n\n{free}",
    },
    "free_n": {
        "uk": "Безкоштовно: {n} листи. Уточнюючі питання по листу — без ліміту.",
        "ru": "Бесплатно: {n} письма. Уточняющие вопросы по письму — без лимита.",
        "fr": 'Gratuit : {n} courriers. Les questions sur un courrier déjà expliqué sont illimitées.',
    },
    "disclaimer": {
        "uk": (
            "ℹ️ Я пояснюю і перекладаю документ та даю загальну інформацію. Це не юридична "
            "консультація. У складних випадках (відмова, OQTF, суд, борги) — до юриста."
        ),
        "ru": (
            "ℹ️ Я объясняю и перевожу документ и даю общую информацию. Это не юридическая "
            "консультация. В сложных случаях (отказ, OQTF, суд, долги) — к юристу."
        ),
        "fr": "ℹ️ J'explique le document et donne des informations générales. Ce n'est pas un conseil juridique. Dans les cas sérieux (refus, OQTF, tribunal, dettes) — consultez un avocat.",
    },
    "privacy": {
        "uk": "🔒 Файли листів я не зберігаю: після розбору вони видаляються.",
        "ru": "🔒 Файлы писем я не храню: после разбора они удаляются.",
        "fr": "🔒 Je ne garde pas les fichiers : ils sont supprimés après l'analyse.",
    },
    "reading": {"uk": "⏳ Читаю лист… Це займе до хвилини.", "ru": "⏳ Читаю письмо… Это займёт до минуты.", "fr": "⏳ Je lis le courrier… Cela prend jusqu'à une minute."},
    "error": {
        "uk": "😕 Не вдалося розібрати лист. Спробуйте ще раз або надішліть чіткіше фото.",
        "ru": "😕 Не получилось разобрать письмо. Попробуйте ещё раз или пришлите более чёткое фото.",
        "fr": "😕 Je n'ai pas réussi à lire le courrier. Réessayez ou envoyez une photo plus nette.",
    },
    "not_ready": {
        "uk": "🔧 Бот ще налаштовується (немає ключа нейромережі). Спробуйте трохи згодом.",
        "ru": "🔧 Бот ещё настраивается (нет ключа нейросети). Попробуйте чуть позже.",
        "fr": '🔧 Le bot est en cours de configuration. Réessayez un peu plus tard.',
    },
    "closed": {
        "uk": "🔧 Бот «Франція без паніки» запускається найближчими днями. Слідкуйте за каналом @france_nopanic",
        "ru": "🔧 Бот «Франция без паники» запускается в ближайшие дни. Следите за каналом @france_nopanic",
        "fr": '🔧 Le bot « France sans panique » ouvre dans les prochains jours. Suivez la chaîne @france_nopanic',
    },
    "limit": {
        "uk": (
            "Безкоштовні листи закінчились ({n} з {n}). Платний доступ з'явиться найближчими днями — "
            "я повідомлю. Уточнюючі питання по вже розібраних листах працюють як і раніше."
        ),
        "ru": (
            "Бесплатные письма закончились ({n} из {n}). Платный доступ появится в ближайшие дни — "
            "я сообщу. Уточняющие вопросы по уже разобранным письмам работают как раньше."
        ),
        "fr": "Les courriers gratuits sont épuisés ({n} sur {n}). L'accès payant arrive dans les prochains jours — je vous préviendrai. Les questions sur les courriers déjà expliqués fonctionnent toujours.",
    },
    "left": {"uk": "Залишилось безкоштовних листів: {n}", "ru": "Осталось бесплатных писем: {n}", "fr": 'Courriers gratuits restants : {n}'},
    "bad_file": {
        "uk": "Я читаю фото (JPG/PNG) і PDF. Якщо це фото з iPhone у форматі HEIC — надішліть його як звичайне фото, не файлом.",
        "ru": "Я читаю фото (JPG/PNG) и PDF. Если это фото с iPhone в формате HEIC — пришлите его как обычное фото, не файлом.",
        "fr": 'Je lis les photos (JPG/PNG) et les PDF. Une photo iPhone en HEIC : envoyez-la comme photo, pas comme fichier.',
    },
    "too_big": {"uk": "Файл завеликий (максимум 20 МБ).", "ru": "Файл слишком большой (максимум 20 МБ).", "fr": 'Fichier trop lourd (20 Mo maximum).'},
    "too_many": {"uk": "Забагато сторінок за раз — максимум {n}.", "ru": "Слишком много страниц за раз — максимум {n}.", "fr": "Trop de pages d'un coup — {n} maximum."},
    "btn_reply": {"uk": "📝 Відповідь французькою", "ru": "📝 Ответ на французском", "fr": '📝 Réponse en français'},
    "btn_remind": {"uk": "⏰ Нагадати про термін", "ru": "⏰ Напомнить о сроке", "fr": '⏰ Me rappeler le délai'},
    "btn_ask": {"uk": "❓ Уточнити", "ru": "❓ Уточнить", "fr": '❓ Poser une question'},
    "writing_reply": {"uk": "✍️ Складаю відповідь…", "ru": "✍️ Составляю ответ…", "fr": '✍️ Je rédige la réponse…'},
    "reply_hint": {
        "uk": "Заповніть поля в [дужках] своїми даними. Перед відправкою перевірте все.",
        "ru": "Заполните поля в [скобках] своими данными. Перед отправкой всё проверьте.",
        "fr": "Remplacez les champs entre [crochets] par vos informations. Vérifiez tout avant l'envoi.",
    },
    "ask_hint": {
        "uk": "Напишіть питання по цьому листу звичайним повідомленням 👇",
        "ru": "Напишите вопрос по этому письму обычным сообщением 👇",
        "fr": 'Écrivez votre question sur ce courrier dans un message 👇',
    },
    "ask_date": {
        "uk": "У листі немає точної дати. Напишіть дату терміну у форматі ДД.ММ.РРРР (наприклад 15.12.2026).",
        "ru": "В письме нет точной даты. Напишите дату срока в формате ДД.ММ.ГГГГ (например 15.12.2026).",
        "fr": "Le courrier n'a pas de date précise. Écrivez la date limite au format JJ.MM.AAAA (par ex. 15.12.2026).",
    },
    "bad_date": {
        "uk": "Не зрозумів дату. Формат: ДД.ММ.РРРР, дата в майбутньому.",
        "ru": "Не понял дату. Формат: ДД.ММ.ГГГГ, дата в будущем.",
        "fr": "Je n'ai pas compris la date. Format : JJ.MM.AAAA, date à venir.",
    },
    "reminders_set": {
        "uk": "✅ Нагадаю: {days}. Термін — {deadline}.",
        "ru": "✅ Напомню: {days}. Срок — {deadline}.",
        "fr": '✅ Je vous le rappellerai : {days}. Date limite — {deadline}.',
    },
    "deadline_today": {
        "uk": "Термін — сьогодні ({deadline}). Нагадування вже не встигну поставити — дійте сьогодні.",
        "ru": "Срок — сегодня ({deadline}). Напоминание поставить уже не успею — действуйте сегодня.",
        "fr": "La date limite est aujourd'hui ({deadline}). Trop tard pour un rappel — agissez aujourd'hui.",
    },
    "deadline_past": {
        "uk": "Термін ({deadline}) вже минув. Зверніться в організацію якнайшвидше.",
        "ru": "Срок ({deadline}) уже прошёл. Свяжитесь с организацией как можно скорее.",
        "fr": "La date limite ({deadline}) est dépassée. Contactez l'organisme au plus vite.",
    },
    "reminder": {
        "uk": "⏰ Нагадування: до {deadline} — {what}.",
        "ru": "⏰ Напоминание: до {deadline} — {what}.",
        "fr": '⏰ Rappel : avant le {deadline} — {what}.',
    },
    "reminder_default_what": {"uk": "термін по вашому листу", "ru": "срок по вашему письму", "fr": 'le délai de votre courrier'},
    "send_letter": {
        "uk": "Надішліть фото або PDF листа — і я його поясню. Питання по листу можна ставити після розбору.",
        "ru": "Пришлите фото или PDF письма — и я его объясню. Вопросы по письму можно задавать после разбора.",
        "fr": "Envoyez une photo ou un PDF du courrier et je l'explique. Les questions viennent après l'explication.",
    },
    "lang_set": {"uk": "Мову змінено: українська 🇺🇦", "ru": "Язык изменён: русский", "fr": 'Langue : français 🇫🇷'},
    "btn_change_lang": {"uk": "🌐 Змінити мову", "ru": "🌐 Сменить язык", "fr": "🌐 Changer de langue"},
}


def t(key: str, lang: str | None, **kw: object) -> str:
    table = T[key]
    text = table.get(lang or "uk") or table["uk"]
    return text.format(**kw) if kw else text


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Split on paragraph/line boundaries so no part exceeds Telegram's 4096-char limit."""
    parts: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        parts.append(rest)
    return parts
