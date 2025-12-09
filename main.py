# file: main.py

import asyncio
import logging
import re
import os  # <--- Додано для роботи зі змінними оточення
from aiohttp import web # <--- Додано для веб-сервера

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

import database as db

# --- Конфігурація ---
# ВАЖЛИВО: На Render токен краще брати з os.environ, але поки залишаємо як є, 
# або замініть на: os.getenv("TELEGRAM_API_TOKEN")
TOKEN = "7943770029:AAGdKA8iegeEWGuWjFT1r4SFC5lTTLryhvI" 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- Константи ---
TECH_MAP = {
    'Python': ['python', 'py'], 'JavaScript': ['javascript', 'js'], 'TypeScript': ['typescript', 'ts'],
    'Java': ['java'], 'C#': ['c#', 'csharp'], 'React': ['react', 'reactjs'],
    'Angular': ['angular'], 'Vue.js': ['vue', 'vuejs'], 'Node.js': ['node.js', 'nodejs', 'node'],
    'Django': ['django'], 'Flask': ['flask'], 'SQL': ['sql'],
    'PostgreSQL': ['postgresql', 'postgres'], 'MongoDB': ['mongodb', 'mongo'], 'Docker': ['docker'],
    'Kubernetes': ['kubernetes', 'k8s'], 'AWS': ['aws', 'amazon web services'], 'Git': ['git'],
    'C++': ['c++', 'cpp'], 'PHP': ['php'], 'Swift': ['swift'], 'Kotlin': ['kotlin'], 'Go': ['go', 'golang']
}
SPECIALIZATIONS_LIST = ["Frontend", "Backend", "Full Stack", "QA", "DevOps", "PM", "Designer", "Mobile Dev"]

# --- Стани (FSM) ---
class ProfileCreation(StatesGroup):
    name = State()
    specialization = State()
    skills = State()
    experience = State()
    portfolio = State()
    contacts = State()

class SearchProcess(StatesGroup):
    choose_method = State()
    enter_skills = State()
    choose_spec = State()

# --- CallbackData ---
class ViewProfile(CallbackData, prefix="view"):
    user_id: int

class RateUser(CallbackData, prefix="rate"):
    target_id: int
    order_id: int
    score: int

class OrderAction(CallbackData, prefix="order"):
    action: str 
    order_id: int
    target_id: int = 0

# --- Допоміжні функції ---
def normalize_and_validate_tech(text_input: str) -> tuple[list[str], list[str]]:
    user_inputs = [item.strip().lower() for item in text_input.split(',')]
    normalized = set()
    invalid = []
    for item in user_inputs:
        found = False
        for official_name, aliases in TECH_MAP.items():
            if item in aliases or item == official_name.lower():
                normalized.add(official_name)
                found = True
                break
        if not found:
            invalid.append(item)
    return sorted(list(normalized)), invalid

# --- Клавіатури ---
def get_main_keyboard(user_id):
    active_order = db.get_active_order(user_id)
    builder = ReplyKeyboardBuilder()
    if active_order:
        builder.row(types.KeyboardButton(text="🔥 Активне замовлення"))
    else:
        builder.row(types.KeyboardButton(text="👤 Моя анкета"))
        builder.row(types.KeyboardButton(text="🔍 Пошук фахівця"))
        builder.row(types.KeyboardButton(text="❓ Допомога"))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Меню...")

def get_cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Скасувати"))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Введіть дані або скасуйте...")

def get_editing_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Пропустити"), types.KeyboardButton(text="Скасувати"))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Введіть нове значення...")

# --- Обробники команд ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = db.get_user_data(user_id)

    if user_data:
        await message.answer(f"👋 З поверненням, {user_data[0]}! Оберіть дію з меню:", reply_markup=get_main_keyboard(user_id))
    else:
        await state.clear()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="Я Фахівець 💻", callback_data="reg_specialist"))
        builder.row(InlineKeyboardButton(text="Я Замовник 🔍", callback_data="reg_client"))
        await message.answer(
            "👋 Вітаю! Для початку роботи <b>необхідно зареєструватися</b>.\nОберіть вашу роль:",
            reply_markup=builder.as_markup()
        )

@dp.message(Command("help"))
@dp.message(StateFilter(None), F.text == "❓ Допомога")
async def show_help(message: Message):
    help_text = (
        "<b>🤖 Довідка та Інструкція користувача</b>\n\n"
        "<b>📌 Основні можливості:</b>\n"
        "• <b>Пошук:</b> Знаходьте фахівців за конкретними мовами програмування або категоріями.\n"
        "• <b>Гібридний профіль:</b> Ви можете бути і Замовником, і Фахівцем з одного акаунту.\n"
        "• <b>Рейтинг:</b> Оцінюйте співпрацю. Рейтинги виконавця та замовника рахуються окремо.\n\n"
        "<b>⚙️ Формат введення даних:</b>\n"
        "• <b>Навички:</b> Вводьте через кому (наприклад: <i>Python, Docker, AWS</i>).\n"
        "• <b>Портфоліо:</b> Посилання має починатися з <code>http://</code> або <code>https://</code>.\n\n"
        "<b>🛡 Поради щодо безпеки угод:</b>\n"
        "1. Не починайте роботу до того, як статус замовлення стане <b>«В роботі»</b>.\n"
        "2. Контакти (username) відкриваються лише після підтвердження замовлення обома сторонами.\n"
        "3. Завжди завершуйте замовлення кнопкою <b>«Завершити»</b>, щоб отримати можливість залишити відгук.\n\n"
        "<b>Команди:</b>\n"
        "/start - Перезапуск бота\n"
        "/myprofile - Керування анкетами\n"
        "/search - Пошук виконавців\n"
        "/cancel - Скасувати дію"
    )
    await message.answer(help_text)

@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "скасувати", StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Дію скасовано.", reply_markup=get_main_keyboard(message.from_user.id))

# --- ПРІОРИТЕТНИЙ ОБРОБНИК: ПРОПУСТИТИ ---
@dp.message(StateFilter(ProfileCreation), F.text == "Пропустити")
async def skip_step(message: Message, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get('is_editing'): 
        return

    curr = await state.get_state()
    if curr == ProfileCreation.specialization: await ask_skills(message, state)
    elif curr == ProfileCreation.skills: await ask_experience(message, state)
    elif curr == ProfileCreation.experience: await ask_portfolio(message, state)
    elif curr == ProfileCreation.portfolio: await finish_spec_profile(message, state)

# --- ЛОГІКА ПРОФІЛІВ ---

@dp.message(Command("myprofile"))
@dp.message(StateFilter(None), F.text == "👤 Моя анкета")
async def show_profile_choice(message: Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Анкета Фахівця", callback_data="show_spec_profile"))
    builder.row(InlineKeyboardButton(text="💼 Анкета Роботодавця", callback_data="show_client_profile"))
    await message.answer("Яку анкету ви хочете переглянути?", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "show_client_profile")
async def show_client_profile(query: CallbackQuery):
    await query.answer()
    user_data = db.get_user_data(query.from_user.id)
    if not user_data:
        await query.message.answer("Помилка даних. Натисніть /start")
        return
    
    full_name, username = user_data
    avg, count = db.get_rating(query.from_user.id, 'client')
    rating_text = f"⭐️ {avg} ({count})" if count > 0 else "Немає оцінок"
    
    text = (
        f"<b>💼 Ваша анкета роботодавця</b>\n"
        f"👤 Ім'я: {full_name}\n"
        f"🔗 Юзернейм: @{username if username else 'Немає'}\n"
        f"📊 Рейтинг замовника: {rating_text}"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Змінити ім'я", callback_data="edit_client_name"))
    
    await query.message.edit_text(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "edit_client_name")
async def edit_client_name_start(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.answer("Введіть ваше нове ім'я та прізвище:", reply_markup=get_cancel_keyboard())
    await state.set_state(ProfileCreation.name)
    await state.update_data(changing_name_only=True)

@dp.callback_query(F.data == "show_spec_profile")
async def show_spec_profile(query: CallbackQuery):
    await query.answer()
    details = db.get_specialist_details(query.from_user.id)
    
    if not details:
        await query.message.answer("Анкета не знайдена. Натисніть /start")
        return

    is_active = details[7]
    full_name = details[1]
    
    if not is_active:
        text = (
            f"<b>👤 Ваша анкета фахівця (Не активна)</b>\n"
            f"Ім'я: {full_name}\n\n"
            f"⚠️ <b>Анкета не заповнена!</b>\n"
            f"Вас не видно у пошуку. Щоб отримувати замовлення, потрібно заповнити дані про технології."
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🚀 Активувати / Заповнити анкету", callback_data="activate_spec_profile"))
        await query.message.edit_text(text, reply_markup=builder.as_markup())
        return

    avg, count = db.get_rating(query.from_user.id, 'specialist')
    rating_text = f"⭐️ {avg} ({count})" if count > 0 else "Новачок"
    
    text = (
        f"<b>👤 Ваша анкета фахівця (Активна)</b>\n"
        f"👤 Ім'я: {full_name}\n"
        f"💻 Спец: {details[2]}\n"
        f"🛠 Мови/Технології: {details[3]}\n"
        f"📈 Досвід: {details[4]}\n"
        f"🌐 Портфоліо: {details[5]}\n"
        f"📊 Рейтинг виконавця: {rating_text}"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Редагувати дані", callback_data="edit_spec_profile"))
    await query.message.edit_text(text, reply_markup=builder.as_markup())

# --- РЕЄСТРАЦІЯ ---

@dp.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Я Фахівець 💻", callback_data="reg_specialist"))
    builder.row(InlineKeyboardButton(text="Я Замовник 🔍", callback_data="reg_client"))
    await message.answer("Ким ви плануєте бути в першу чергу?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.in_(['reg_specialist', 'reg_client']))
async def process_registration_start(query: CallbackQuery, state: FSMContext):
    await query.answer()
    role_choice = query.data
    await state.update_data(role_choice=role_choice)
    await query.message.delete()
    await query.message.answer("Введіть ваше ім'я та прізвище:", reply_markup=get_cancel_keyboard())
    await state.set_state(ProfileCreation.name)

@dp.message(ProfileCreation.name, F.text)
async def process_name(message: Message, state: FSMContext):
    name = message.text
    user_id = message.from_user.id
    username = message.from_user.username
    db.register_user(user_id, username, name)
    data = await state.get_data()
    
    if data.get('changing_name_only'):
        await message.answer("✅ Ім'я успішно змінено!", reply_markup=get_main_keyboard(user_id))
        await state.clear()
        return

    role_choice = data.get('role_choice')
    if role_choice == 'reg_client':
        await message.answer("✅ Реєстрацію завершено! Ви увійшли як Замовник.", reply_markup=get_main_keyboard(user_id))
        await state.clear()
    else:
        await message.answer("Чудово! Тепер заповнимо професійні дані.", reply_markup=get_cancel_keyboard())
        await ask_specialization(message, state)

@dp.callback_query(F.data.in_(['activate_spec_profile', 'edit_spec_profile']))
async def start_spec_filling(query: CallbackQuery, state: FSMContext):
    await query.answer()
    details = db.get_specialist_details(query.from_user.id)
    if details and details[7] == 1:
        await state.update_data(
            specialization=details[2], skills=details[3], experience=details[4],
            portfolio_url=details[5], contact_info=details[6], is_editing=True
        )
        await query.message.answer("Редагування профілю фахівця...", reply_markup=get_editing_keyboard())
    else:
        await query.message.answer("Заповніть дані, щоб активувати анкету фахівця.", reply_markup=get_cancel_keyboard())
    
    await ask_specialization(query.message, state)

# --- Етапи заповнення ---

async def ask_specialization(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = "Оберіть спеціалізацію:"
    builder = InlineKeyboardBuilder()
    for spec in SPECIALIZATIONS_LIST:
        builder.row(InlineKeyboardButton(text=spec, callback_data=spec))
    if data.get('is_editing'): text += f"\n\n<i>Поточне: {data.get('specialization')}</i>"
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(ProfileCreation.specialization)

@dp.callback_query(ProfileCreation.specialization)
async def process_specialization(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(specialization=query.data)
    await query.message.edit_text(f"Обрано: {query.data}")
    await ask_skills(query.message, state)

async def ask_skills(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"Вкажіть <b>мови програмування та технології</b> через кому:\n<i>Доступні: {', '.join(TECH_MAP.keys())}</i>"
    if data.get('is_editing'): text += f"\n\n<i>Поточні: {data.get('skills')}</i>"
    await message.answer(text)
    await state.set_state(ProfileCreation.skills)

@dp.message(ProfileCreation.skills, F.text)
async def process_skills(message: Message, state: FSMContext):
    normalized, invalid = normalize_and_validate_tech(message.text)
    if invalid:
        await message.answer(f"❌ Невідомі технології: {', '.join(invalid)}. Спробуйте ще раз.")
        return
    await state.update_data(skills=", ".join(normalized))
    await message.answer(f"Прийнято: {', '.join(normalized)}")
    await ask_experience(message, state)

async def ask_experience(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = "Досвід комерційної розробки?"
    builder = InlineKeyboardBuilder()
    exps = {"0-1 рік": "0-1", "1-3 роки": "1-3", "3-5 років": "3-5", "5+ років": "5+"}
    for k, v in exps.items(): builder.row(InlineKeyboardButton(text=k, callback_data=v))
    if data.get('is_editing'): 
        curr = next((k for k, v in exps.items() if v == data.get('experience')), "")
        text += f"\n\n<i>Поточне: {curr}</i>"
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(ProfileCreation.experience)

@dp.callback_query(ProfileCreation.experience)
async def process_experience(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(experience=query.data)
    await query.message.edit_text("Досвід збережено.")
    await ask_portfolio(query.message, state)

async def ask_portfolio(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = "Лінк на портфоліо (GitHub/LinkedIn):"
    if data.get('is_editing'): text += f"\n\n<i>Поточне: {data.get('portfolio_url')}</i>"
    await message.answer(text)
    await state.set_state(ProfileCreation.portfolio)

@dp.message(ProfileCreation.portfolio, F.text)
async def process_portfolio(message: Message, state: FSMContext):
    if not re.match(r'https?://\S+', message.text):
        await message.answer("❌ Посилання має починатися з http:// або https://")
        return
    await state.update_data(portfolio_url=message.text)
    await finish_spec_profile(message, state)

async def finish_spec_profile(message: Message, state: FSMContext):
    user = message.from_user
    if not user.username:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="Я встановив, спробувати знову", callback_data="retry_username"))
        await message.answer("⚠️ Встановіть @username в Telegram!", reply_markup=builder.as_markup())
        return

    await state.update_data(contact_info=f"@{user.username}")
    data = await state.get_data()
    db.update_specialist_profile(user.id, data)
    await state.clear()
    await message.answer("✅ Анкету фахівця активовано! Тепер вас видно у пошуку.", reply_markup=get_main_keyboard(user.id))

@dp.callback_query(F.data == "retry_username")
async def retry_username_check(query: CallbackQuery, state: FSMContext):
    await query.answer()
    if not query.from_user.username:
        await query.message.answer("Все ще немає.")
        return
    await state.update_data(contact_info=f"@{query.from_user.username}")
    data = await state.get_data()
    db.update_specialist_profile(query.from_user.id, data)
    await state.clear()
    await query.message.answer("✅ Анкету активовано!", reply_markup=get_main_keyboard(query.from_user.id))

# --- ПОШУК ТА ЗАМОВЛЕННЯ ---

@dp.message(F.text == "🔥 Активне замовлення")
async def show_active_order_menu(message: Message):
    user_id = message.from_user.id
    order = db.get_active_order(user_id)
    if not order:
        await message.answer("Немає активних замовлень.", reply_markup=get_main_keyboard(user_id))
        return

    order_id, client_id, specialist_id, status, finish_by, client_rated, spec_rated = order
    is_client = (user_id == client_id)
    
    if is_client:
        partner_id = specialist_id
        spec_details = db.get_specialist_details(partner_id)
        if spec_details:
            name = spec_details[1]
            contact = spec_details[6]
            role_title = "Фахівець"
            partner_display = f"{name} ({contact})"
        else:
            partner_display = "Фахівець (дані недоступні)"
    else:
        partner_id = client_id
        partner_info = db.get_client_details_full(partner_id)
        if partner_info:
            name = partner_info['name']
            contact = f"@{partner_info['username']}"
            role_title = "Замовник"
            partner_display = f"{name} ({contact})"
        else:
            partner_display = "Замовник"

    if status == 'pending':
        text = f"⏳ Замовлення #{order_id} очікує підтвердження."
        if not is_client:
             c_info = db.get_client_details_full(partner_id)
             rating_str = f"⭐️{c_info['rating']} ({c_info['reviews']})" if c_info else "New"
             text = f"🔔 <b>Нове замовлення #{order_id}!</b>\n\nЗамовник: <b>{partner_display}</b>\n\nХоче вас найняти."
             
             builder = InlineKeyboardBuilder()
             builder.row(InlineKeyboardButton(text="✅ Прийняти", callback_data=OrderAction(action="accept", order_id=order_id, target_id=client_id).pack()))
             builder.row(InlineKeyboardButton(text="❌ Відхилити", callback_data=OrderAction(action="decline", order_id=order_id, target_id=client_id).pack()))
             await message.answer(text, reply_markup=builder.as_markup())
             return
    elif status == 'active':
        text = f"🔥 <b>Замовлення #{order_id} в роботі!</b>\n\n{role_title}: <b>{partner_display}</b>\n<a href='tg://user?id={partner_id}'>Написати в особисті</a>"
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏁 Завершити роботу", callback_data=OrderAction(action="finish", order_id=order_id).pack()))
        await message.answer(text, reply_markup=builder.as_markup())
        return
    elif status == 'finish_request':
        if finish_by == user_id:
            text = f"⏳ Ви запросили завершення. Очікуємо підтвердження від <b>{partner_display}</b>."
        else:
            text = f"🏁 <b>{partner_display}</b> пропонує завершити роботу. Підтверджуєте?"
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="✅ Так, завершити", callback_data=OrderAction(action="confirm_finish", order_id=order_id).pack()))
            await message.answer(text, reply_markup=builder.as_markup())
            return
    await message.answer(text)

@dp.callback_query(OrderAction.filter(F.action == "hire"))
async def hire_specialist(query: CallbackQuery, callback_data: OrderAction):
    await query.answer()
    if query.from_user.id == callback_data.target_id:
        await query.message.answer("Ви не можете найняти самого себе!")
        return

    order_id = db.create_order(query.from_user.id, callback_data.target_id)
    if not order_id:
        await query.message.answer("❌ Ви або фахівець зайняті.")
        return
    
    await query.message.answer("✅ Пропозицію надіслано!", reply_markup=get_main_keyboard(query.from_user.id))
    try:
        client_info = db.get_client_details_full(query.from_user.id)
        rating_str = f"⭐️{client_info['rating']} ({client_info['reviews']})" if client_info else "New"
        c_name = client_info['name'] if client_info else "Замовник"
        c_username = client_info['username'] if client_info else ""
        
        msg_text = (
            f"🔔 <b>Нове замовлення!</b>\n\n"
            f"💼 Замовник: <b>{c_name}</b> (@{c_username})\n"
            f"📊 Рейтинг замовника: {rating_str}\n\n"
            f"Пропонує вам роботу."
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ Прийняти", callback_data=OrderAction(action="accept", order_id=order_id, target_id=query.from_user.id).pack()))
        builder.row(InlineKeyboardButton(text="❌ Відхилити", callback_data=OrderAction(action="decline", order_id=order_id, target_id=query.from_user.id).pack()))
        await bot.send_message(callback_data.target_id, msg_text, reply_markup=builder.as_markup())
    except: pass

@dp.callback_query(OrderAction.filter(F.action == "accept"))
async def accept_order(query: CallbackQuery, callback_data: OrderAction):
    db.update_order_status(callback_data.order_id, 'active')
    await query.message.edit_text("✅ Прийнято!")
    await query.message.answer("Робота почалась.", reply_markup=get_main_keyboard(query.from_user.id))
    try:
        spec_details = db.get_specialist_details(query.from_user.id)
        s_name = f"{spec_details[1]} ({spec_details[6]})"
        await bot.send_message(callback_data.target_id, f"🎉 <b>{s_name}</b> прийняв замовлення! Роботу розпочато.", reply_markup=get_main_keyboard(callback_data.target_id))
    except: pass

@dp.callback_query(OrderAction.filter(F.action == "decline"))
async def decline_order(query: CallbackQuery, callback_data: OrderAction):
    db.cancel_order_db(callback_data.order_id)
    await query.message.edit_text("❌ Відхилено.")
    try:
        await bot.send_message(callback_data.target_id, "😔 Відхилено.")
    except: pass

@dp.callback_query(OrderAction.filter(F.action == "finish"))
async def request_finish(query: CallbackQuery, callback_data: OrderAction):
    db.update_order_status(callback_data.order_id, 'finish_request', finish_requested_by=query.from_user.id)
    await query.message.edit_text("⏳ Запит надіслано.")
    order = db.get_order_by_id(callback_data.order_id)
    partner_id = order[2] if query.from_user.id == order[1] else order[1]
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ Підтвердити", callback_data=OrderAction(action="confirm_finish", order_id=callback_data.order_id).pack()))
        await bot.send_message(partner_id, f"🏁 Партнер пропонує завершити.", reply_markup=builder.as_markup())
    except: pass

@dp.callback_query(OrderAction.filter(F.action == "confirm_finish"))
async def confirm_finish(query: CallbackQuery, callback_data: OrderAction):
    db.update_order_status(callback_data.order_id, 'completed')
    order = db.get_order_by_id(callback_data.order_id)
    client_id, specialist_id = order[1], order[2]
    
    await query.message.edit_text("🎉 Завершено!")
    
    await bot.send_message(client_id, "Роботу офіційно завершено.", reply_markup=get_main_keyboard(client_id))
    await bot.send_message(specialist_id, "Роботу офіційно завершено.", reply_markup=get_main_keyboard(specialist_id))
    
    await send_rating_request(client_id, specialist_id, callback_data.order_id, "specialist")
    await send_rating_request(specialist_id, client_id, callback_data.order_id, "client")

async def send_rating_request(rater_id, target_id, order_id, target_role_str):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.add(InlineKeyboardButton(text=f"{i}⭐️", callback_data=RateUser(target_id=target_id, order_id=order_id, score=i).pack()))
    
    role_ua = "фахівця" if target_role_str == "specialist" else "замовника"
    await bot.send_message(rater_id, f"Будь ласка, оцініть співпрацю з {role_ua}:", reply_markup=builder.as_markup())

@dp.callback_query(RateUser.filter())
async def save_rating(query: CallbackQuery, callback_data: RateUser):
    order = db.get_order_by_id(callback_data.order_id)
    if not order:
        await query.answer("Помилка замовлення.")
        return

    client_id, specialist_id = order[1], order[2]
    rater_id = query.from_user.id
    
    target_role = ""
    if rater_id == client_id:
        target_role = 'specialist'
        if order[6] == 1: 
             await query.answer("Вже оцінено.")
             await query.message.delete()
             return
        db.set_order_rated(order[0], 'client')
    elif rater_id == specialist_id:
        target_role = 'client'
        if order[5] == 1:
             await query.answer("Вже оцінено.")
             await query.message.delete()
             return
        db.set_order_rated(order[0], 'specialist')
    else:
        await query.answer("Помилка доступу.")
        return

    if db.add_rating(callback_data.target_id, rater_id, callback_data.score, target_role):
        await query.message.edit_text(f"✅ Дякуємо! Оцінка: {callback_data.score}⭐️")
    else:
        await query.answer("Помилка.", show_alert=True)

@dp.message(Command("search"))
@dp.message(StateFilter(None), F.text == "🔍 Пошук фахівця")
async def start_search(message: Message, state: FSMContext):
    if db.get_active_order(message.from_user.id):
        await message.answer("⚠️ Спочатку завершіть поточне замовлення.")
        return
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="За мовами"))
    builder.row(types.KeyboardButton(text="За спеціальністю"))
    builder.row(types.KeyboardButton(text="Скасувати"))
    await message.answer("Критерій пошуку:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(SearchProcess.choose_method)

@dp.message(SearchProcess.choose_method)
async def process_search_method(message: Message, state: FSMContext):
    if message.text == "За мовами":
        await message.answer(f"Введіть мови програмування:", reply_markup=get_cancel_keyboard())
        await state.set_state(SearchProcess.enter_skills)
    elif message.text == "За спеціальністю":
        builder = InlineKeyboardBuilder()
        for spec in SPECIALIZATIONS_LIST:
            builder.row(InlineKeyboardButton(text=spec, callback_data=f"search_spec_{spec}"))
        await message.answer("Спеціальність:", reply_markup=builder.as_markup())
        await state.set_state(SearchProcess.choose_spec)
    else:
        await message.answer("Невірний вибір.")

@dp.message(SearchProcess.enter_skills, F.text)
async def process_search_by_skills(message: Message, state: FSMContext):
    normalized, _ = normalize_and_validate_tech(message.text)
    await state.clear()
    if not normalized:
        await message.answer("Не розпізнано.", reply_markup=get_main_keyboard(message.from_user.id))
        return
    
    found_ids = set()
    for skill in normalized:
        for uid, _, _, _ in db.search_specialists(skill): found_ids.add(uid)
    await show_search_results(message, found_ids, f"Мови: {', '.join(normalized)}")

@dp.callback_query(SearchProcess.choose_spec, F.data.startswith("search_spec_"))
async def process_search_by_spec(query: CallbackQuery, state: FSMContext):
    await query.answer()
    spec = query.data.split("search_spec_")[1]
    await state.clear()
    found_ids = set()
    for uid, _, _, _ in db.search_specialists_by_spec(spec): found_ids.add(uid)
    await show_search_results(query.message, found_ids, f"Спеціальність: {spec}")

async def show_search_results(message: Message, found_ids, title):
    if not found_ids:
        await message.answer("Нікого не знайдено.", reply_markup=get_main_keyboard(message.chat.id))
        return
    builder = InlineKeyboardBuilder()
    for uid in found_ids:
        details = db.get_specialist_details(uid)
        if details:
            name = details[1]
            spec = details[2]
            avg, count = db.get_rating(uid, 'specialist')
            rating_str = f"⭐️{avg}" if count > 0 else "New"
            builder.row(InlineKeyboardButton(text=f"{name} ({spec}) | {rating_str}", callback_data=ViewProfile(user_id=uid).pack()))
    await message.answer(f"Результати ({title}):", reply_markup=builder.as_markup())
    if isinstance(message, Message):
        await message.answer("Пошук завершено.", reply_markup=get_main_keyboard(message.from_user.id))

@dp.callback_query(ViewProfile.filter())
async def view_profile(query: CallbackQuery, callback_data: ViewProfile):
    await query.answer()
    details = db.get_specialist_details(callback_data.user_id)
    if not details: return
    
    _, name, spec, skills, exp, portfolio, contacts, active = details
    avg, count = db.get_rating(callback_data.user_id, 'specialist')
    rating_text = f"⭐️ {avg} ({count})" if count > 0 else "New"
    
    txt = f"<b>Профіль:</b>\n👤 {name}\n💻 {spec}\n📊 {rating_text}\n🛠️ {skills}\n📈 {exp}\n🌐 {portfolio}"
    builder = InlineKeyboardBuilder()
    if query.from_user.id != callback_data.user_id:
         builder.row(InlineKeyboardButton(text="💼 Найняти", callback_data=OrderAction(action="hire", order_id=0, target_id=callback_data.user_id).pack()))
    
    await query.message.answer(txt, reply_markup=builder.as_markup())

@dp.message(StateFilter(None))
async def unknown_command(message: Message):
    await message.reply("Невідома команда.")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Fake web server started on port {port}")

# --- ГОЛОВНА ФУНКЦІЯ ---
async def main():
    db.init_db()
    # Спочатку запускаємо веб-сервер (фоново)
    await start_web_server()
    # Потім запускаємо поллінг бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")