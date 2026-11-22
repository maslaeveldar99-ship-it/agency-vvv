import asyncio
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from bs4 import BeautifulSoup
from telethon import TelegramClient, events

# =====================================================================
# 1. НАСТРОЙКИ АГЕНТСТВА
# =====================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "9228127508:AAG_0AyqSORqNgy31_ttW9usHxCYVzU64ks")
ADMIN_ID = 6096550279  # Твой числовой Telegram ID
CONTACT_USERNAME = "@prodzera"

# Категории, где в карточку добавляется @username заказчика для прямой связи
DIRECT_CONTACT_CATEGORIES = {"БРЕНДЕРЫ", "ПРОДЮСИРОВАНИЕ"}

# Ключи Telethon с my.telegram.org (нужны для автоматического чтения чатов)
API_ID: Optional[int] = 36867192
API_HASH: Optional[str] = "a08b4badc8dc32918d012f054c940bc3"

SESSION_NAME = "monitor_session"
STATE_FILE = "orders_state.json"

DEFAULT_MONITOR_CHATS = [
    "https://t.me/frilancru",
    "https://t.me/birjafreelance",
    "https://t.me/jobospherechat",
    "https://t.me/jir_chat",
    "https://t.me/freelanc_rabota",
    "https://t.me/rabotavakansij",
    "https://t.me/freelancce",
    "https://t.me/designwork_vacansii",
    "https://t.me/frilanser_vacansii",
    "https://t.me/naudalenkebro",
    "https://t.me/proffreelancee_chat",
    "https://t.me/udafrii",
    "https://t.me/careerspace",
    "https://t.me/zdemcv",
    "https://t.me/distantsiya",
    "https://t.me/designbirzha",
    "https://t.me/designhunters",
]

# =====================================================================
# 2. САЙТЫ И ПЛАТФОРМЫ + ИНДИВИДУАЛЬНЫЕ ПРАВИЛА ПОИСКА ПОД КАЖДЫЙ
# =====================================================================

DEFAULT_SITE_SEARCH_QUERIES = [
    "монтаж видео shorts reels youtube",
    "разработка сайта лендинг верстка",
    "телеграм бот автоворонка парсер",
    "мобильное приложение ios android mini app",
    "продюсирование запуск эксперта",
    "брендинг логотип айдентика",
    "дизайн figma баннеры карточки",
    "арбитраж трафика залив лиды",
    "ведение канала контент сценарии",
    "оплата крипта usdt ton кошелек",
]

WEB_SOURCES_CONFIG: list[dict] = [
    {
        "name": "Upwork",
        "url": "https://www.upwork.com/nx/search/jobs/?q=video%20editor%20website%20telegram%20bot",
        "queries": ["video", "editor", "shorts", "reels", "website", "web", "bot", "app", "design", "brand", "crypto", "usdt"],
    },
    {
        "name": "FL.ru",
        "url": "https://www.fl.ru/projects/",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "Kwork",
        "url": "https://kwork.ru/projects",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "Fiverr",
        "url": "https://www.fiverr.com/categories/video-animation",
        "queries": ["video", "editing", "shorts", "reels", "website", "bot", "app", "branding", "logo", "design"],
    },
    {
        "name": "Habr Freelance",
        "url": "https://freelance.habr.com/tasks",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "Freelance.ru",
        "url": "https://freelance.ru/projects/",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "Weblancer",
        "url": "https://www.weblancer.net/jobs/",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "YouDo",
        "url": "https://youdo.com/tasks",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "hh.ru","url": "https://hh.ru/search/vacancy?text=монтаж+видео+сайт+бот+дизайн",
        "queries": DEFAULT_SITE_SEARCH_QUERIES,
    },
    {
        "name": "RemoteOK",
        "url": "https://remoteok.com/remote-dev-jobs",
        "queries": ["video", "editor", "web", "website", "bot", "app", "mobile", "design", "brand", "marketing", "crypto"],
    },
    {
        "name": "WeWorkRemotely",
        "url": "https://weworkremotely.com/remote-jobs.rss",
        "queries": ["video", "editor", "web", "website", "bot", "app", "design", "brand", "marketing", "growth"],
    },
    {
        "name": "WorkingNomads",
        "url": "https://www.workingnomads.com/jobs",
        "queries": ["video", "editor", "web", "bot", "app", "design", "brand", "marketing", "content"],
    },
]

WEB_POLL_INTERVAL_SEC = 180

# =====================================================================
# 3. МАРШРУТИЗАЦИЯ ПО КАТЕГОРИЯМ И ТОПИКАМ
# =====================================================================

DEFAULT_CHAT_ID = -1004449873442
DEFAULT_THREAD_ID = 307

ROUTES = {
    "КОНТЕНТ ВИДЕО (SHORTS / LONG)": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "САЙТ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "ТГ-БОТ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "ПРИЛОЖЕНИЕ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "ПРОДЮСИРОВАНИЕ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "БРЕНДЕРЫ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "ДИЗАЙН": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "АРБИТРАЖ": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
    "КОНТЕНТ (ВЕДЕНИЕ / УЛУЧШЕНИЕ)": {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID},
}

# =====================================================================
# 4. РАСШИРЕННЫЕ СЛОВАРИ РАСПОЗНАВАНИЯ
# =====================================================================

CATEGORY_KEYWORDS = {
    "КОНТЕНТ ВИДЕО (SHORTS / LONG)": [
        "монтаж", "монтажер", "монтажёр", "смонтировать", "видео", "видеоролик",
        "ролик", "ролики", "shorts", "шортс", "reels", "рилс", "рилсы",
        "tiktok", "тикток", "tt", "youtube", "ютуб", "yt", "нарезки",
        "нарезчик", "склейка", "цветокор", "цветокоррекция", "саунддизайн",
        "звук к видео", "субтитры", "motion", "моушн", "анимация", "видеограф",
        "рилсмейкер", "шортсмейкер", "съемка", "съёмка", "футаж", "превью",
        "видеомонтаж", "монтаж видео", "монтаж роликов", "монтаж рилс", "монтаж шортс",
        "video", "video editor", "editing", "reels", "shorts", "tiktok", "youtube",
    ],
    "САЙТ": [
        "сайт", "сайты", "лендинг", "landing", "верстка", "вёрстка", "сверстать",
        "веб", "веб-разработка", "web", "интернет-магазин", "магазин на сайте",
        "тильда", "tilda", "wordpress", "wp", "webflow", "wix", "react", "next",
        "frontend", "фронтенд", "backend", "бэкенд", "full stack", "fullstack",
        "домен", "хостинг", "редизайн сайта", "сайт под ключ", "визитка", "сайта",
        "website", "web developer", "landing page", "ecommerce", "e-commerce",
    ],
    "ТГ-БОТ": [
        "тг бот", "тг-бот", "tg бот", "tg-бот", "бот в тг", "бот для тг",
        "телеграм бот", "telegram bot", "бот в телеграм", "бот для телеграм",
        "автоворонка", "воронка в тг", "рассылка в тг", "парсер", "парсинг",
        "юзербот", "userbot", "aiogram", "telethon", "pyrogram", "python бот",
        "бот заявок", "бот оплат", "бот модерации", "инвайтер", "чекер", "бота",
        "telegram", "bot", "chatbot", "automation",
    ],
    "ПРИЛОЖЕНИЕ": [
        "приложение", "приложения", "мобильное приложение", "приложуха",
        "app", "ios", "android", "apk", "ipa", "flutter", "react native","kotlin", "swift", "mini app", "telegram mini app", "tma", "webview",
        "десктоп приложение", "софт", "программа", "утилита", "приложения",
        "mobile app", "application", "cross-platform",
    ],
    "ПРОДЮСИРОВАНИЕ": [
        "продюсер", "продюсирование", "продюссер", "запуск", "запуски",
        "запустить эксперта", "эксперт", "блогер", "наставничество", "курс",
        "инфопродукт", "инфобиз", "воронка продаж", "прогрев", "монетизация",
        "упаковка эксперта", "масштабирование", "партнерство", "партнёрство",
        "launch", "producer", "creator", "monetization", "funnel",
    ],
    "БРЕНДЕРЫ": [
        "бренд", "брендинг", "логотип", "лого", "айдентика", "identity",
        "фирменный стиль", "фирстиль", "упаковка бренда", "брендбук",
        "гайдлайн", "нейминг", "имя бренда", "слоган", "концепция бренда",
        "brand", "branding", "logo", "brand identity", "visual identity",
    ],
    "ДИЗАЙН": [
        "дизайн", "дизайнер", "ui", "ux", "ui/ux", "figma", "фигма",
        "баннер", "баннеры", "креатив", "креативы", "инфографика",
        "карточки товара", "wb", "ozon", "озон", "обложка", "оформление",
        "аватарка", "макет", "вектор", "photoshop", "фотошоп", "illustrator",
        "design", "designer", "thumbnail", "banner",
    ],
    "АРБИТРАЖ": [
        "арбитраж", "трафик", "залив", "залить трафик", "лить трафик",
        "fb", "facebook", "фб", "google ads", "гугл адс", "tiktok ads",
        "убт", "условно бесплатный трафик", "крео", "лиды", "сплит",
        "конверсии", "оффер", "связка", "байер", "медиабайер", "посевы",
        "traffic", "media buyer", "ads", "lead generation", "leads",
    ],
    "КОНТЕНТ (ВЕДЕНИЕ / УЛУЧШЕНИЕ)": [
        "ведение канала", "ведение аккаунта", "ведение соцсетей", "контент",
        "контент-менеджер", "контент план", "контент-план", "сценарист",
        "сценарии", "копирайтер", "копирайтинг", "посты", "тексты",
        "оформление канала", "улучшить канал", "прокачать канал", "smm", "смм",
        "content", "copywriter", "scriptwriter", "social media",
    ],
}

DEMAND_RE = re.compile(
    r"(нуж\w*|ищ\w*|требу\w*|заказ\w*|сдела\w*|разработ\w*|созда\w*|настро\w*|"
    r"зали\w*|смонтир\w*|упаков\w*|оформ\w*|продвин\w*|запуст\w*|напис\w*|"
    r"кто\s+сделает|кто\s+сможет|кто\s+умеет|кто\s+возьм\w*|кто\s+занима\w*|"
    r"посоветуйте|подскажите|ищу\s+человека|ищу\s+спец\w*|ищу\s+команд\w*|"
    r"ищу\s+исполн\w*|ищу\s+подряд\w*|ищу\s+мастер\w*|задача|задачи|"
    r"бюджет|оплат\w*|прайс|ставка|гонорар|срок\w*|дедлайн|тз|услуг\w*|"
    r"looking\s+for|need\s+a|hire|freelance|project|budget|task|job)",
    re.IGNORECASE,
)

CRYPTO_RE = re.compile(
    r"(крипт\w*|криптокошел\w*|кошел\w*|usdt|ton|btc|bitcoin|eth|ethereum|"
    r"sol|solana|trc20|erc20|bep20|оплат\w*\s+в\s+крипт\w*|на\s+кошел\w*|crypto|wallet)",
    re.IGNORECASE,
)

TG_USER_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")
TG_LINK_RE = re.compile(r"https?://(?:t\.me|telegram\.me)/([A-Za-z0-9_+/]{3,64})", re.IGNORECASE)
IG_LINK_RE = re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]{2,32})/?", re.IGNORECASE)
IG_MENTION_RE = re.compile(r"(?:инст\w*|inst\w*|instagram)\s*[:\-]?\s*@?([A-Za-z0-9._]{2,32})", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WA_LINK_RE = re.compile(r"https?://wa\.me/(\d{7,15})", re.IGNORECASE)
DM_HINT_RE = re.compile(
    r"(?:\bв\s*лс\b|\bв\s*личку\b|\bв\s*личных\s+сообщениях\b|\bв\s*личные\s+сообщения\b|"
    r"\bпишите\s+в\s*лс\b|\bпиши\s+в\s*лс\b|\bпишите\s+в\s*личку\b|\bпиши\s+в\s*личку\b|"
    r"\bв\s*директ\b|\bв\s*direct\b|\bв\s*dm\b|\bв\s*личные\b)",
    re.IGNORECASE,
)

BUDGET_RE = re.compile(
    r"(?:бюджет|оплата|прайс|до|budget)?\s*[:\-]?\s*(\d{1,3}(?:[ \u00a0]?\d{3})*(?:[.,]\d{1,2})?)\s*(\$|usd|usdt|руб\w*|₽|р\b|ton|€|eur)?",
    re.IGNORECASE,
)
def extract_contacts(
    text: str,
    client_username: Optional[str] = None,
    author_url: Optional[str] = None,
    order_url: Optional[str] = None,
) -> dict[str, list[str]]:
    tg_contacts: list[str] = []
    if client_username:
        u = client_username.lstrip("@").strip()
        if u:
            tg_contacts.append(f"@{u}")

    for u in TG_USER_RE.findall(text):
        item = f"@{u}"
        if item not in tg_contacts:
            tg_contacts.append(item)

    for slug in TG_LINK_RE.findall(text):
        clean_slug = slug.lstrip("+").split("/")[0]
        item = f"https://t.me/{slug}" if slug.startswith("+") else f"@{clean_slug}"
        if item not in tg_contacts:
            tg_contacts.append(item)

    ig_contacts: list[str] = []
    for handle in IG_LINK_RE.findall(text):
        item = f"https://instagram.com/{handle}"
        if item not in ig_contacts:
            ig_contacts.append(item)
    for handle in IG_MENTION_RE.findall(text):
        if handle.lower() not in {"com", "ru", "net", "org"}:
            item = f"@{handle}"
            if item not in ig_contacts:
                ig_contacts.append(item)

    emails = list(dict.fromkeys(EMAIL_RE.findall(text)))
    wa_links = [f"https://wa.me/{num}" for num in dict.fromkeys(WA_LINK_RE.findall(text))]
    profiles = [author_url] if author_url else []
    order_links = [order_url] if order_url else []
    dm_hints = ["в ЛС / личку"] if DM_HINT_RE.search(text) else []

    return {
        "tg": tg_contacts,
        "ig": ig_contacts,
        "email": emails,
        "wa": wa_links,
        "profile": profiles,
        "order": order_links,
        "dm": dm_hints,
    }


def has_contact_for_deal(contacts: dict[str, list[str]]) -> bool:
    return bool(
        contacts.get("tg")
        or contacts.get("ig")
        or contacts.get("email")
        or contacts.get("wa")
        or contacts.get("profile")
        or contacts.get("order")
        or contacts.get("dm")
    )


def normalize_chat_identifier(raw: str) -> str:
    s = raw.strip().strip("/").strip(",")
    if not s:
        return ""
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:t\.me|telegram\.me|telegram\.dog)/", "", s, flags=re.IGNORECASE)
    if s.startswith("joinchat/") or s.startswith("+"):
        return f"https://t.me/{s}"
    if re.fullmatch(r"-?\d{5,20}", s):
        return s
    s = s.lstrip("@").split("/")[0].split("?")[0].strip()
    if not s:
        return ""
    return f"@{s}"


def parse_chat_inputs(text: str) -> list[str]:
    tokens = re.split(r"[\s,;]+", text.strip())
    result: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        norm = normalize_chat_identifier(tok)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def detect_category(text: str) -> Optional[str]:
    lower = text.lower()
    best_cat: Optional[str] = None
    best_score = 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in lower:
                score += 2 if (" " in kw or len(kw) >= 6) else 1
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat if best_score > 0 else None


def extract_budget_and_split(text: str) -> tuple[Optional[float], str, Optional[float], Optional[float]]:
    match = BUDGET_RE.search(text)
    if not match:
        return None, "$", None, None

    raw_num = match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        amount = float(raw_num)
    except ValueError:
        return None, "$", None, None

    if amount <= 0 or amount > 1_000_000:
        return None, "$", None, None

    raw_cur = (match.group(2) or "").lower()
    if raw_cur in {"₽", "руб", "рубля", "рублей", "р"}:
        currency = "₽"
    elif raw_cur in {"€", "eur"}:
        currency = "€"
    elif raw_cur == "ton":
        currency = " TON"
    elif raw_cur == "usdt":
        currency = " USDT"
    else:
        currency = "$"
    executor_share = round(amount * 0.6, 2)
    agency_share = round(amount * 0.4, 2)
    return amount, currency, executor_share, agency_share


def is_matching_order(
    text: str,
    category: Optional[str],
    has_contact: bool,
    site_queries: Optional[list[str]] = None,
) -> bool:
    if not category or not has_contact:
        return False
    cleaned = text.strip()
    if len(cleaned) < 10:
        return False

    has_demand = bool(DEMAND_RE.search(cleaned))
    has_crypto = bool(CRYPTO_RE.search(cleaned))
    has_tg_user = bool(TG_USER_RE.search(cleaned))
    has_site_query = False
    if site_queries:
        lower = cleaned.lower()
        has_site_query = any(q.strip().lower() in lower for q in site_queries if q.strip())

    return has_demand or (has_crypto and has_tg_user) or (has_site_query and (has_crypto or has_tg_user or len(cleaned) >= 35))


def build_order_cards(
    order_num: int,
    category: str,
    raw_text: str,
    source_label: str,
    client_username: Optional[str] = None,
    order_url: Optional[str] = None,
    author_url: Optional[str] = None,
) -> tuple[str, str]:
    short_desc = " ".join(raw_text.strip().split())
    if len(short_desc) > 450:
        short_desc = short_desc[:447] + "..."

    amount, currency, exec_share, agency_share = extract_budget_and_split(raw_text)
    has_crypto = bool(CRYPTO_RE.search(raw_text))
    contacts = extract_contacts(
        raw_text,
        client_username=client_username,
        author_url=author_url,
        order_url=order_url,
    )
    primary_user = contacts["tg"][0] if contacts["tg"] else None

    price_line = (
        f"Цена: {exec_share:g}{currency}"
        if exec_share is not None
        else "Цена: по договорённости (60/40)"
    )

    if category in DIRECT_CONTACT_CATEGORIES and primary_user:
        contact_line = f"Прямой контакт заказчика: {primary_user}"
    else:
        contact_line = f"После выполнения заказа писать ему и кидать материал ему : {CONTACT_USERNAME}"

    tags = []
    if has_crypto:
        tags.append("🪙 Оплата: крипта / кошелёк")
    if primary_user:
        tags.append(f"👤 TG юз: {primary_user}")
    if contacts["ig"]:
        tags.append(f"📸 IG: {', '.join(contacts['ig'])}")
    if contacts["wa"]:
        tags.append(f"📱 WA: {', '.join(contacts['wa'])}")
    if contacts["email"]:
        tags.append(f"✉️ Email: {', '.join(contacts['email'])}")
    if not any([primary_user, contacts["ig"], contacts["wa"], contacts["email"], order_url, author_url]) and contacts["dm"]:
        tags.append("📩 Связь: указано «в ЛС / личку»")
    if order_url:
        tags.append(f"🔗 Заказ на сайте: {order_url}")
    if author_url:
        tags.append(f"🧑‍💼 Профиль заказчика: {author_url}")
    tags.append(f"📡 Источник: {source_label}")
    tags_block = "\n".join(tags)

    group_card = (
        f"-----заказ#{order_num}-----\n"
        f"{category}\n"
        f"-{short_desc[:120]}\n"
        f"-Описание: {short_desc}\n"
        f"-Время на заказ: уточняется\n\n"
        f"{price_line}\n"
        f"{contact_line}\n\n"
        f"{tags_block}"
    )

    admin_card = (
        f"📥 Новый заказ #{order_num} [{category}]\n"
        f"Источник: {source_label}\n"
        f"Ссылка на заказ: {order_url or 'нет'}\n"
        f"Ссылка на профиль: {author_url or 'нет'}\n"
        f"TG юз: {', '.join(contacts['tg']) or 'не указан'}\n"
        f"IG: {', '.join(contacts['ig']) or 'не указан'}\n"
        f"WA: {', '.join(contacts['wa']) or 'не указан'}\n"
        f"Email: {', '.join(contacts['email']) or 'не указан'}\n"
        f"ЛС/личка: {'да' if contacts['dm'] else 'нет'}\n"
        f"Крипта/кошелёк: {'да' if has_crypto else 'нет'}\n"
        f"Бюджет: {f'{amount:g}{currency}' if amount is not None else 'не указан'}\n"
        f"Исполнитель (60%): {f'{exec_share:g}{currency}' if exec_share is not None else '—'}\n"
        f"Агентство (40%): {f'{agency_share:g}{currency}' if agency_share is not None else '—'}\n\n"
        f"Текст:\n{short_desc}"
    )
    return group_card, admin_card# =====================================================================
# 5. СОСТОЯНИЕ И ХРАНИЛИЩЕ
# =====================================================================

def load_state() -> dict:
    default_data = {
        "last_order": 0,
        "monitored_chats": parse_chat_inputs("\n".join(DEFAULT_MONITOR_CHATS)),
        "seen_web_hashes": [],
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_data["last_order"] = int(data.get("last_order", 0))
            chats = data.get("monitored_chats", [])
            if isinstance(chats, list) and chats:
                default_data["monitored_chats"] = parse_chat_inputs("\n".join(str(c) for c in chats))
            hashes = data.get("seen_web_hashes", [])
            if isinstance(hashes, list):
                default_data["seen_web_hashes"] = hashes[-4000:]
        except Exception:
            pass
    return default_data


def save_state(state: dict) -> None:
    state["seen_web_hashes"] = state.get("seen_web_hashes", [])[-4000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


STATE = load_state()
SEEN_WEB_HASHES: set[str] = set(STATE.get("seen_web_hashes", []))


class MonitorStates(StatesGroup):
    waiting_for_chats_to_add = State()
    waiting_for_chat_to_remove = State()


# =====================================================================
# 6. ОТПРАВКА ЗАКАЗА В ТОПИК И АДМИНУ
# =====================================================================

async def dispatch_order(
    bot: Bot,
    raw_text: str,
    source_label: str,
    client_username: Optional[str] = None,
    site_queries: Optional[list[str]] = None,
    order_url: Optional[str] = None,
    author_url: Optional[str] = None,
    notify_chat_id: Optional[int] = None,
    reply_to_message_id: Optional[int] = None,
) -> bool:
    category = detect_category(raw_text)
    contacts = extract_contacts(
        raw_text,
        client_username=client_username,
        author_url=author_url,
        order_url=order_url,
    )
    if not is_matching_order(
        raw_text,
        category,
        has_contact=has_contact_for_deal(contacts),
        site_queries=site_queries,
    ) or category is None:
        return False

    route = ROUTES.get(category, {"chat_id": DEFAULT_CHAT_ID, "thread_id": DEFAULT_THREAD_ID})
    target_chat_id = route["chat_id"]
    target_thread_id = route.get("thread_id")

    STATE["last_order"] = int(STATE.get("last_order", 0)) + 1
    order_num = STATE["last_order"]
    save_state(STATE)

    group_card, admin_card = build_order_cards(
        order_num=order_num,
        category=category,
        raw_text=raw_text,
        source_label=source_label,
        client_username=client_username,
        order_url=order_url,
        author_url=author_url,
    )

    try:
        await bot.send_message(
            chat_id=target_chat_id,
            text=group_card,
            message_thread_id=target_thread_id,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"[ERROR] Не удалось отправить заказ #{order_num} в {target_chat_id} (thread={target_thread_id}): {exc}")
        if notify_chat_id:
            await bot.send_message(
                chat_id=notify_chat_id,
                text=f"❌ Ошибка отправки в топик: {exc}",
                reply_to_message_id=reply_to_message_id,
            )
        return False

    if ADMIN_ID:
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_card, disable_web_page_preview=True)
        except Exception as exc:
            print(f"[WARN] Не удалось отправить копию админу: {exc}")

    if notify_chat_id:
        await bot.send_message(
            chat_id=notify_chat_id,
            text=f"✅ Заказ #{order_num} [{category}] отправлен в топик.",
            reply_to_message_id=reply_to_message_id,
        )
    return True# =====================================================================
# 7. ФОНОВЫЙ СКАНЕР САЙТОВ И RSS/ATOM ЛЕНТ (WEB_SOURCES_CONFIG)
# =====================================================================

AUTHOR_LINK_HINTS = re.compile(r"/(?:user|users|client|employer|customer|profile|author|freelancer|u)/", re.IGNORECASE)
ORDER_LINK_HINTS = re.compile(r"/(?:task|tasks|project|projects|job|jobs|vacancy|vacancies|order|orders|kwork|contest)/", re.IGNORECASE)


def extract_items_from_payload(payload: str, base_url: str) -> list[dict]:
    stripped = payload.lstrip()
    items: list[dict] = []

    if stripped.startswith("<?xml") or "<rss" in stripped[:300].lower() or "<feed" in stripped[:300].lower():
        try:
            root = ET.fromstring(payload)
            for item in root.iter():
                tag = item.tag.split("}")[-1].lower()
                if tag in {"item", "entry"}:
                    parts = []
                    found_link = None
                    for child in item:
                        ctag = child.tag.split("}")[-1].lower()
                        if ctag in {"title", "description", "summary", "content"} and child.text:
                            clean_txt = BeautifulSoup(child.text, "html.parser").get_text(" ", strip=True)
                            if clean_txt:
                                parts.append(clean_txt)
                        elif ctag == "link":
                            href = child.attrib.get("href") or (child.text or "").strip()
                            if href:
                                found_link = urljoin(base_url, href)
                    joined = " ".join(" — ".join(parts).split())
                    if joined:
                        items.append({
                            "text": joined,
                            "order_url": found_link or base_url,
                            "author_url": None,
                        })
            if items:
                return items
        except Exception:
            pass

    soup = BeautifulSoup(payload, "html.parser")
    for el in soup.find_all(["article", "li", "div", "tr"]):
        txt = " ".join(el.get_text(" ", strip=True).split())
        if not (15 <= len(txt) <= 1800):
            continue

        order_url = None
        author_url = None
        for a_tag in el.find_all("a", href=True):
            abs_href = urljoin(base_url, a_tag["href"].strip())
            if not abs_href.startswith(("http://", "https://")):
                continue
            link_text = " ".join(a_tag.get_text(" ", strip=True).split()).lower()
            if not author_url and (
                AUTHOR_LINK_HINTS.search(abs_href)
                or any(h in link_text for h in ["заказчик", "автор", "профиль", "employer", "client", "author", "profile"])
            ):
                author_url = abs_href
            elif not order_url and (
                ORDER_LINK_HINTS.search(abs_href)
                or len(link_text) >= 12
            ):
                order_url = abs_href

        items.append({
            "text": txt,
            "order_url": order_url or base_url,
            "author_url": author_url,
        })
    return items


async def poll_web_sources(bot: Bot) -> None:
    active_sources = [
        cfg for cfg in WEB_SOURCES_CONFIG
        if isinstance(cfg, dict) and str(cfg.get("url", "")).strip().startswith(("http://", "https://"))
    ]
    if not active_sources:
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    while True:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                for cfg in active_sources:
                    url = cfg["url"].strip()
                    site_name = cfg.get("name") or url
                    queries = cfg.get("queries") or DEFAULT_SITE_SEARCH_QUERIES
                    try:
                        async with session.get(url, timeout=20) as resp:
                            if resp.status != 200:
                                continue
                            payload = await resp.text(errors="ignore")
                            parsed_items = extract_items_from_payload(payload, url)
                            for item in parsed_items:
                                chunk = item["text"]
                                h = f"{url}:{hash(chunk)}"
                                if h in SEEN_WEB_HASHES:
                                    continue
                                SEEN_WEB_HASHES.add(h)
                                STATE["seen_web_hashes"] = list(SEEN_WEB_HASHES)
                                save_state(STATE)
                                await dispatch_order(
                                    bot=bot,
                                    raw_text=chunk,
                                    source_label=site_name,
                                    site_queries=queries,
                                    order_url=item.get("order_url"),
                                    author_url=item.get("author_url"),
                                )
                    except Exception as exc:
                        print(f"[WEB WARN] {site_name} ({url}): {exc}")
        except Exception as exc:
            print(f"[WEB SESSION WARN] {exc}")

        await asyncio.sleep(WEB_POLL_INTERVAL_SEC)


# =====================================================================
# 8. МОНИТОРИНГ TELEGRAM-ЧАТОВ ЧЕРЕЗ TELETHON
# =====================================================================

async def start_telethon_monitor(bot: Bot) -> Optional[TelegramClient]:
    if not API_ID or not API_HASH:
        print("[INFO] API_ID или API_HASH не заданы — авто-чтение внешних чатов через Telethon отключено.")
        return None

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    print("[OK] Telethon-мониторинг запущен.")

    @client.on(events.NewMessage())
    async def on_new_message(event: events.NewMessage.Event) -> None:
        monitored = set(STATE.get("monitored_chats", []))
        if not monitored:
            return

        chat = await event.get_chat()
        chat_id_str = str(getattr(event, "chat_id", ""))
        chat_username = f"@{chat.username.lower()}" if getattr(chat, "username", None) else ""

        matches_monitored = False
        for item in monitored:
            norm_item = normalize_chat_identifier(item).lower()
            if not norm_item:
                continue
            if norm_item == chat_id_str.lower():
                matches_monitored = True
                break
            if chat_username and norm_item.endswith(chat_username):
                matches_monitored = True
                break

        if not matches_monitored:
            return

        text = (event.raw_text or "").strip()
        if not text:
            return

        sender = await event.get_sender()
        sender_user = f"@{sender.username}" if getattr(sender, "username", None) else None
        source_label = chat_username or getattr(chat, "title", None) or chat_id_str

        await dispatch_order(
            bot=bot,
            raw_text=text,
            source_label=source_label,
            client_username=sender_user,
        )

    return client


# =====================================================================
# 9. КОМАНДЫ, КНОПКИ И МЕНЮ БОТА (AIOGRAM)
# =====================================================================

dp = Dispatcher()


async def build_main_menu_kb(bot: Bot) -> InlineKeyboardMarkup:
    me = await bot.get_me()
    add_group_url = (
        f"https://t.me/{me.username}?startgroup=true"
        if me.username
        else "https://t.me/"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить в группу", url=add_group_url)],
            [
                InlineKeyboardButton(text="➕ Добавить чаты", callback_data="mon_add"),
                InlineKeyboardButton(text="🗑 Удалить чат", callback_data="mon_del"),
            ],
            [
                InlineKeyboardButton(text="📋 Список чатов", callback_data="mon_list"),
                InlineKeyboardButton(text="📖 Инструкция", callback_data="help_guide"),
            ],
        ]
    )


def format_chats_list() -> str:
    chats = STATE.get("monitored_chats", [])
    if not chats:
        return "Список отслеживаемых чатов пока пуст."
    lines = [f"{i + 1}. {c}" for i, c in enumerate(chats)]
    return "Отслеживаемые чаты:\n" + "\n".join(lines)


GUIDE_TEXT = (
    "📖 Инструкция по работе бота\n\n"
    "1. «➕ Добавить в группу» — добавляет бота в твою группу/супергруппу. "
    "Внутри нужного топика напиши /id, чтобы узнать chatid и threadid и прописать их в ROUTES.\n\n"
    "2. Авто-чтение чатов (Telethon):\n"
    "• Все твои ссылки уже заложены в список по умолчанию.\n"
    "• Впиши API_ID и API_HASH с my.telegram.org в bot.py, запусти скрипт и пройди вход по номеру/коду.\n"
    "• Аккаунт-монитор должен состоять во всех добавленных чатах.\n\n"
    "3. Сайты и платформы (WEB_SOURCES_CONFIG):\n"
    "• Бот пропускает только заказы, где есть контакт/ссылка или упоминание «в лс / в личку».\n\n"
    "4. Логика заказов и сплит:\n"
    "• Фиксирует оплату криптой/кошельком и контакты заказчика, считает 60% исполнителю и 40% агентству."
)


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    await message.reply(f"chatid: {chat_id}\nthreadid: {thread_id}")


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    kb = await build_main_menu_kb(message.bot)
    await message.answer(
        "Бот агентства запущен.\n\n"
        "• Нажми «➕ Добавить в группу», чтобы подключить бота к группе.\n"
        "• Нажми «📖 Инструкция», чтобы посмотреть полный порядок настройки.\n"
        "• Управляй списком чатов через кнопки ниже (все твои ссылки уже добавлены).\n"
        "• Сайты и запросы под каждый сайт настроены в WEB_SOURCES_CONFIG.",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "help_guide")
async def cb_help_guide(callback: CallbackQuery) -> None:
    kb = await build_main_menu_kb(callback.message.bot)
    await callback.message.answer(GUIDE_TEXT, reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "mon_list")
async def cb_mon_list(callback: CallbackQuery) -> None:
    kb = await build_main_menu_kb(callback.message.bot)
    await callback.message.answer(
        f"📡 Монитор чатов\n\n{format_chats_list()}\n\n"
        "Важно: аккаунт-монитор должен состоять в этих чатах.",
        reply_markup=kb,
    )
    await callback.answer()


@dp.callback_query(F.data == "mon_add")
async def cb_mon_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MonitorStates.waiting_for_chats_to_add)
    await callback.message.answer(
        "Скинь ссылки вида https://t.me/..., юзернеймы (@chat) или ID чатов.\n"
        "Можно сразу пачкой через пробел, запятую или с новой строки."
    )
    await callback.answer()


@dp.callback_query(F.data == "mon_del")
async def cb_mon_del(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MonitorStates.waiting_for_chat_to_remove)
    await callback.message.answer(
        f"{format_chats_list()}\n\nНапиши ссылку, юзернейм или ID чата, который нужно убрать:"
    )
    await callback.answer()@dp.message(MonitorStates.waiting_for_chats_to_add)
async def process_add_chats(message: Message, state: FSMContext) -> None:
    incoming = parse_chat_inputs(message.text or "")
    if not incoming:
        await message.reply("Не удалось распознать ссылки/юзернеймы. Попробуй ещё раз.")
        return

    current = STATE.get("monitored_chats", [])
    current_lower = {c.lower() for c in current}
    added = []
    for item in incoming:
        if item.lower() not in current_lower:
            current.append(item)
            current_lower.add(item.lower())
            added.append(item)

    STATE["monitored_chats"] = current
    save_state(STATE)
    await state.clear()

    kb = await build_main_menu_kb(message.bot)
    await message.answer(
        f"Добавлено чатов: {len(added)}\n\n{format_chats_list()}",
        reply_markup=kb,
    )


@dp.message(MonitorStates.waiting_for_chat_to_remove)
async def process_remove_chat(message: Message, state: FSMContext) -> None:
    targets = {t.lower() for t in parse_chat_inputs(message.text or "")}
    if not targets:
        await message.reply("Укажи ссылку, юзернейм или ID чата для удаления.")
        return

    current = STATE.get("monitored_chats", [])
    new_list = [c for c in current if c.lower() not in targets]
    removed_count = len(current) - len(new_list)

    STATE["monitored_chats"] = new_list
    save_state(STATE)
    await state.clear()

    kb = await build_main_menu_kb(message.bot)
    await message.answer(
        f"Удалено из монитора: {removed_count}\n\n{format_chats_list()}",
        reply_markup=kb,
    )


@dp.message(F.chat.type == "private")
async def handle_private_order_test(message: Message) -> None:
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    fwd_user = None
    if message.forward_from and message.forward_from.username:
        fwd_user = f"@{message.forward_from.username}"

    sent = await dispatch_order(
        bot=message.bot,
        raw_text=text,
        source_label="ручной_тест_личка",
        client_username=fwd_user,
        notify_chat_id=message.chat.id,
        reply_to_message_id=message.message_id,
    )
    if not sent:
        await message.reply(
            "Сообщение не прошло фильтр заказа (нужно направление, спрос/ТЗ/оплата и контакт, ссылка или упоминание «в лс / в личку»)."
        )


# =====================================================================
# 10. ЗАПУСК
# =====================================================================

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    telethon_client = await start_telethon_monitor(bot)
    web_task = asyncio.create_task(poll_web_sources(bot))

    try:
        print("[OK] Бот запущен.")
        await dp.start_polling(bot)
    finally:
        web_task.cancel()
        if telethon_client is not None:
            await telethon_client.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())