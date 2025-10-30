import os
import asyncio
import re
import json
import nest_asyncio
nest_asyncio.apply()

# 🚀 Aiogram Imports
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import (
    Message,
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

# 🤖 Telethon Imports
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import (
    DeleteContactsRequest,
    ImportContactsRequest,
    GetContactsRequest
)
from telethon.tl.types import InputPhoneContact, InputUser

# ☁️ Google Drive API Imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# 🔹 তোমার Drive Folder ID
GOOGLE_FOLDER_ID = "10PhKlbF6TFz5CTaTQiKDFwmQxGu8gTMF"

# 🔹 Token ফাইলের নাম (auto refresh হলে এখানে সেভ হবে)
TOKEN_FILE = "token.json"

# 🔹 ক্রেডেনশিয়াল লোড করা
def load_credentials():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return Credentials.from_authorized_user_info(data)
    else:
        # 👉 প্রথমবারের জন্য ম্যানুয়ালি টোকেন বসাও (তুমি যেটা দিয়েছো)
        creds = Credentials(
            token="ya29.a0ATi6K2tM5RICjBCL1D3lOW5Fm8xjEl3OMd9sIYL6VyMXBVNWbAQNxB-ThBv8tV14LbYIdnHN7ZQpqcz60b1Jy5mUypsExwDdbjHgs_-A6ZB6HWxSbpqh8G99Mjq-nny2wtWwWNA2l0ApjaCpsP-qiLI0PZIIqKWvUrElV9-SF4iz5PI5F1OtGwpVJ3ScUeRvGrGoRUUaCgYKAdUSARESFQHGX2MiiD8DQilhsZckD_4AyLy9aw0206",
            refresh_token="1//0ccJG0M2N5PDvCgYIARAAGAwSNwF-L9IrsGedoagIRQiVcw7nckAgMDg-KYvXOXjTeAKL22PmEb8ioca5sHmWhZ6J6VkI3tMfIRA",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="29510678393-onbisk73ubkihqpbg0hacp9hmn2drtk6.apps.googleusercontent.com",
            client_secret="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",
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        # 🔹 প্রথমবার সেভ করে রাখবে
        save_credentials(creds)
        return creds

# 🔹 ক্রেডেনশিয়াল সেভ করা
def save_credentials(creds):
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

# 🔹 টোকেন রিফ্রেশ অটো সিস্টেম
def ensure_valid_token():
    global creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            print("🔁 Token auto-refreshed successfully!")
        except Exception as e:
            print("⚠️ Token refresh failed:", e)

# 🔹 লোড ও সার্ভিস তৈরি
creds = load_credentials()
drive_service = build("drive", "v3", credentials=creds)


# 🔹 আপলোড ফাংশন
def upload_to_drive(file_path, file_name):
    """Google Drive এ ফাইল আপলোড (Auto Token Refresh সহ)"""
    try:
        ensure_valid_token()  # ✅ টোকেন চেক ও রিফ্রেশ

        file_metadata = {"name": file_name, "parents": [GOOGLE_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        print(f"✅ Uploaded successfully: {uploaded_file.get('id')}")
        return uploaded_file.get("id")

    except HttpError as e:
        err_msg = e.content.decode() if hasattr(e, "content") else str(e)
        print("❌ Google Drive error:", err_msg)
        raise Exception(f"Google Drive error: {err_msg}")
    except Exception as e:
        print("⚠️ Unexpected upload error:", e)
        raise

import io
from googleapiclient.http import MediaIoBaseDownload
import tempfile

def download_drive_file_to_tmp(file_id, filename=None):
    """Drive file download করে লোকাল টেম্প ফাইল পথ রিটার্ন করে"""
    if not filename:
        filename = file_id + ".session"
    tmp_dir = os.path.join("sessions", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, filename)
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    try:
        while not done:
            status, done = downloader.next_chunk()
    except Exception as e:
        fh.close()
        raise
    fh.close()
    return local_path

import phonenumbers
import pycountry

def get_country_flag(iso_code):
    """ISO country code থেকে পতাকা ইমোজি তৈরি"""
    try:
        return ''.join(chr(127397 + ord(c)) for c in iso_code.upper())
    except:
        return "🏳️"

def get_country_info(phone_number: str):
    """ফোন নম্বর থেকে দেশের পতাকা ও নাম বের করে (স্বয়ংক্রিয় 195 দেশের জন্য)"""
    try:
        parsed = phonenumbers.parse(phone_number, None)
        country_code = phonenumbers.region_code_for_number(parsed)
        if not country_code:
            return ("🌍", "Unknown")

        country = pycountry.countries.get(alpha_2=country_code)
        flag = get_country_flag(country_code)
        return (flag, country.name if country else "Unknown")
    except:
        return ("🌍", "Unknown")

# ✅ নতুন purge অপশন কীবোর্ড
purge_option_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧾 Delete Messages", callback_data="purge_messages")],
    [InlineKeyboardButton(text="🚪 Leave Groups", callback_data="purge_groups")],
    [InlineKeyboardButton(text="📇 Delete Contacts", callback_data="purge_contacts")]
])

API_ID = 29054703
API_HASH = "4306675966f08ae9f2d06cc59165db81"
BOT_TOKEN = "7972270179:AAFMVzaAl6qishsQ5-mr1MgIsIQSQ1MTVKY"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

user_state = {}

def get_user_session_dir(user_id):
    path = os.path.join("sessions", str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Store Accounts"), KeyboardButton(text="📊 My Accounts")],
        [KeyboardButton(text="🔐 Login"), KeyboardButton(text="📤 Export")],
        [KeyboardButton(text="🗑 Delete"), KeyboardButton(text="💀 Terminate")],
        [KeyboardButton(text="🧹 Purge Account"), KeyboardButton(text="📥 Import Session")],
        [KeyboardButton(text="📡 Check Active Telegram Numbers"), KeyboardButton(text="📋 Check Session Health")],
        [KeyboardButton(text="🔎 Check Session Authorization")]   # ✅ নতুন বোতাম
    ],
    resize_keyboard=True
)

# ✅ Terminate অপশনের ইনলাইন কীবোর্ড
terminate_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💥 Terminate", callback_data="confirm_terminate")]
    ]
)

# ✅ Store Accounts এর জন্য ❌ Cancel Inline Keyboard
store_cancel_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_store")]
    ]
)


@router.message(CommandStart())
async def start_cmd(message: Message):
    user_state.pop(message.from_user.id, None)  # ← এটা যোগ করো
    await message.answer("স্বাগতম! একটি অপশন বেছে নিন:", reply_markup=main_menu)


@router.message(lambda msg: msg.text == "📥 Store Accounts")
async def store_accounts(message: types.Message):
    user_state.pop(message.from_user.id, None)
    user_state[message.from_user.id] = "awaiting_phone"
    await message.answer(
        "📱 ফোন নম্বর দিন (e.g. +8801XXXXXXXXX):",
        reply_markup=store_cancel_inline_keyboard
    )

@router.callback_query(lambda c: c.data == "cancel_store")
async def cancel_store_account(callback_query: types.CallbackQuery):
    user_state.pop(callback_query.from_user.id, None)
    await callback_query.message.answer(
        "✅ অপারেশন বাতিল করা হয়েছে।", reply_markup=main_menu
    )

@router.message(lambda msg: user_state.get(msg.from_user.id) == "awaiting_phone")
async def get_otp(message: Message):
    phone = message.text.strip()
    user_state[message.from_user.id] = {"phone": phone}
    await message.answer("📨 OTP পাঠানো হচ্ছে...")
    asyncio.create_task(send_otp(message.chat.id, phone))


async def send_otp(chat_id, phone):
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        if await client.is_user_authorized():
            await bot.send_message(chat_id, "🔓 এই অ্যাকাউন্ট ইতিমধ্যে লগইন করা হয়েছে।")
            await client.disconnect()
            return

        sent = await client.send_code_request(phone)
        user_state[chat_id]['session'] = client.session.save()
        user_state[chat_id]['phone_code_hash'] = sent.phone_code_hash

        await bot.send_message(chat_id, "📩 কোড পাঠানো হয়েছে, এখন OTP দিন:")
        await client.disconnect()

    except Exception as e:
        await bot.send_message(chat_id, f"❌ OTP পাঠাতে সমস্যা: {e}")

@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and "phone" in user_state[msg.from_user.id])
async def save_session(message: Message):
    code = message.text.strip()
    state = user_state[message.from_user.id]
    phone = state["phone"]
    session_str = state.get("session")
    phone_code_hash = state.get("phone_code_hash")
    session_dir = get_user_session_dir(message.from_user.id)
    session_path = os.path.join(session_dir, f"{message.from_user.id}_{phone.replace('+', '')}.session")

    if not phone_code_hash:
        await message.answer("❌ কোড hash পাওয়া যায়নি। আবার শুরু করুন।")
        return

    try:
        # ✅ পুরোনো ও নতুন সেশন দুইটাই সাপোর্ট করবে
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        except Exception:
            client = TelegramClient(session_str, API_ID, API_HASH)

        await client.connect()
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)

        # ✅ লোকাল সেশন ফাইল সেভ
        with open(session_path, "wb") as f:
            f.write(client.session.save().encode("utf-8"))

        await client.disconnect()

        # ✅ Google Drive এ আপলোড
        try:
            user_id = str(message.from_user.id)
            file_name = os.path.basename(session_path)
            file_id = upload_to_drive(session_path, file_name)
            await message.answer(
                f"✅ সেশন সফলভাবে Google Drive এ আপলোড হয়েছে!\n📂 File ID: `{file_id}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await message.answer(f"⚠️ Google Drive এ আপলোড ব্যর্থ: {e}")

        # ✅ লোকাল ফাইল মুছে ফেলো (সিকিউরিটির জন্য)
        try:
            os.remove(session_path)
        except:
            pass

        await message.answer(f"✅ সেশন সেভ সম্পন্ন: {phone}")

    except Exception as e:
        await message.answer(f"❌ লগইন ব্যর্থ: {e}")
    finally:
        user_state.pop(message.from_user.id, None)

from aiogram.types import Message
from googleapiclient.errors import HttpError

@router.message(lambda msg: msg.text == "📊 My Accounts")
async def list_accounts(message: Message):
    """Drive থেকে ইউজারভিত্তিক সেশন লিস্ট + দেশভিত্তিক সুন্দর প্রোফেশনাল ভিউ"""
    user_state.pop(message.from_user.id, None)

    try:
        # 🔹 Google Drive থেকে ফাইল লিস্ট করা
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc"
        ).execute()

        files = results.get("files", [])
        user_id = str(message.from_user.id)

        # 🔹 ইউজারভিত্তিক ফাইল ফিল্টার
        files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not files:
            await message.answer("❌ কোনো সেশন ফাইল পাওয়া যায়নি (Drive এ)।")
            return

        # 🔹 দেশভিত্তিক অ্যাকাউন্ট সংখ্যা গণনা
        country_counts = {}
        for f in files:
            filename = f["name"]
            parts = filename.split("_")
            if len(parts) < 2:
                continue

            phone_part = parts[1]
            if not phone_part:
                continue

            flag, country = get_country_info("+" + phone_part)
            if country not in country_counts:
                country_counts[country] = {"flag": flag, "count": 0}
            country_counts[country]["count"] += 1

        # 🔹 দেশভিত্তিক সারসংক্ষেপ তৈরি
        country_summary = {}
        total_accounts = sum(info["count"] for info in country_counts.values())

        for country, info in country_counts.items():
            country_summary[(info["flag"], country)] = info["count"]

        # 🔹 সুন্দরভাবে ফরম্যাট করা মেসেজ
        msg = "📊 <b>𝗠𝘆 𝗔𝗰𝗰𝗼𝘂𝗻𝘁𝘀 𝗦𝘂𝗺𝗺𝗮𝗿𝘆</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        color_emojis = ["🟢", "🟡", "🔵", "🟣", "🟤", "🟠", "⚪", "⚫"]

        for i, ((flag, name), count) in enumerate(
            sorted(country_summary.items(), key=lambda x: x[1], reverse=True), 1
        ):
            color = color_emojis[i % len(color_emojis)]
            msg += f"{color} {flag} <b>{name}</b> — <code>{count}</code> Account{'s' if count > 1 else ''}\n"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🗂️ <b>Total Linked:</b> <code>{total_accounts}</code> Account{'s' if total_accounts > 1 else ''} ✅"

        await message.answer(msg, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"⚠️ কোনো সমস্যা ঘটেছে:\n<code>{e}</code>", parse_mode="HTML")

@router.message(lambda msg: msg.text == "📤 Export")
async def export_prompt_drive(message: Message):
    user_state.pop(message.from_user.id, None)

    results = drive_service.files().list(
        q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed = false",
        fields="files(id, name)",
        orderBy="createdTime desc"
    ).execute()
    
    files = results.get("files", [])
    user_id = str(message.from_user.id)
    files = [f for f in files if f["name"].startswith(user_id + "_")]
    if not files:
        await message.answer("❌ কোনো সেশন নেই (Drive এ)।")
        return

    msg_list = "\n".join([f"{i+1}. {f['name']}" for i,f in enumerate(files)])
    await message.answer(f"📤 Export করতে নম্বর দিন (e.g. 1,2):\n\n{msg_list}")
    user_state[message.from_user.id] = {"action":"awaiting_export_indices", "drive_files": files}


@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and user_state[msg.from_user.id].get("action")=="awaiting_export_indices")
async def export_sessions_drive(message: Message):
    try:
        data = user_state[message.from_user.id]
        files = data.get("drive_files", [])
        indices = [int(i.strip())-1 for i in message.text.split(",")]
        for idx in indices:
            if idx < 0 or idx >= len(files):
                continue
            meta = files[idx]
            local_path = download_drive_file_to_tmp(meta["id"], meta["name"])
            await message.answer_document(FSInputFile(local_path), caption=f"📤 {meta['name']}")
            try:
                os.remove(local_path)
            except:
                pass

    except Exception as e:
        await message.answer(f"❌ সমস্যা: {e}")
    finally:
        user_state.pop(message.from_user.id, None)


@router.message(lambda msg: msg.text == "🗑 Delete")
async def delete_prompt_drive(message: Message):
    """Google Drive থেকে সুন্দরভাবে সেশন ডিলিট করার UI"""
    user_state.pop(message.from_user.id, None)

    try:
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc"
        ).execute()

        files = results.get("files", [])
        user_id = str(message.from_user.id)
        files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not files:
            await message.answer("❌ কোনো সেশন পাওয়া যায়নি (Drive এ)।")
            return

        # 🌟 সুন্দরভাবে লিস্ট তৈরি
        msg = "🗑 <b>𝗦𝗲𝗹𝗲𝗰𝘁 𝗦𝗲𝘀𝘀𝗶𝗼𝗻𝘀 𝗧𝗼 𝗗𝗲𝗹𝗲𝘁𝗲</b>\n\n"
        for i, f in enumerate(files, 1):
            name = f["name"].replace(".session", "")
            phone = name.split("_")[-1]
            if not phone:
                continue

            # দেশের পতাকা + নাম বের করা
            flag, country = get_country_info("+" + phone if not phone.startswith("+") else phone)
            msg += f"⬢ {flag} <b>{country}</b> — +{phone}\n"

        msg += "\n────────────────────\n"
        msg += f"📦 <b>Total Sessions:</b> {len(files)} ✅\n"
        msg += "🖊️ <b>Reply with numbers to delete (e.g. 1,2,3)</b>"

        await message.answer(msg, parse_mode="HTML")
        user_state[message.from_user.id] = {
            "action": "awaiting_delete_indices",
            "drive_files": files
        }

    except Exception as e:
        await message.answer(f"⚠️ সমস্যা: {e}")


@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) 
                 and user_state[msg.from_user.id].get("action") == "awaiting_delete_indices")
async def delete_sessions_drive(message: Message):
    """এক বা একাধিক সেশন লগআউট + ডিলিট"""
    try:
        data = user_state[message.from_user.id]
        files = data.get("drive_files", [])
        indices = [int(i.strip()) - 1 for i in message.text.split(",") if i.strip().isdigit()]

        deleted = []
        for idx in indices:
            if idx < 0 or idx >= len(files):
                continue

            file_meta = files[idx]
            file_id = file_meta["id"]
            file_name = file_meta["name"]

            try:
                # 🔄 সেশন ডাউনলোড ও লগআউট
                local_path = download_drive_file_to_tmp(file_id, file_name)
                with open(local_path, "rb") as f:
                    session_str = f.read().decode()

                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()
                if await client.is_user_authorized():
                    await client.log_out()
                await client.disconnect()

                # 🗑 Drive থেকে মুছে ফেলা
                drive_service.files().delete(fileId=file_id).execute()
                deleted.append(file_name)

                try:
                    os.remove(local_path)
                except:
                    pass

            except Exception as e:
                await message.answer(f"⚠️ `{file_name}` মুছতে সমস্যা: {e}")

        # 🌈 সুন্দর আউটপুট মেসেজ
        if deleted:
            msg = "🧹 <b>𝗗𝗲𝗹𝗲𝘁𝗶𝗼𝗻 𝗦𝘂𝗺𝗺𝗮𝗿𝘆</b>\n\n"
            for i, name in enumerate(deleted, 1):
                phone = name.split("_")[-1].replace(".session", "")
                flag, country = get_country_info("+" + phone if not phone.startswith("+") else phone)
                msg += f"{i}. {flag} <b>{country}</b> — +{phone}\n"
            msg += "\n✅ <b>Deleted:</b> {0} session(s)".format(len(deleted))
        else:
            msg = "⚠️ কোনো সেশন ডিলিট করা হয়নি।"

        await message.answer(msg, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ সমস্যা: {e}")
    finally:
        user_state.pop(message.from_user.id, None)

@router.message(lambda msg: msg.text == "🔐 Login")
async def login_prompt_drive(message: Message):
    """Google Drive থেকে ইউজারের সেশন ফাইল সুন্দরভাবে দেখাবে"""
    user_state.pop(message.from_user.id, None)
    await message.answer("⏳ Google Drive থেকে সেশন লোড হচ্ছে...")

    try:
        # 🔹 Drive থেকে সেশন লিস্ট
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc"
        ).execute()

        files = results.get("files", [])
        user_id = str(message.from_user.id)
        user_files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not user_files:
            await message.answer("❌ কোনো সেশন নেই (Drive এ)।")
            return

        # সুন্দর ফরম্যাটে দেখাও (দেশভিত্তিক পতাকা)
        msg_lines = ["🌐 <b>Select Account To Login</b>\n"]
        for i, f in enumerate(user_files, 1):
            name = f["name"].replace(".session", "")
            parts = name.split("_")
            phone = parts[-1] if len(parts) > 1 else name
            flag, country = get_country_info("+" + phone if not phone.startswith("+") else phone)
            msg_lines.append(f"⬢ {flag}  <b>{country}</b> — {phone}")

        msg_lines.append("\n────────────────────")
        msg_lines.append(f"🗂️ <b>Total Accounts:</b> {len(user_files)} ✅")
        msg_lines.append("🖊️ Reply a number to login.")

        await message.answer("\n".join(msg_lines), parse_mode="HTML")
        user_state[message.from_user.id] = {"action": "awaiting_otp_drive", "files": user_files}

    except Exception as e:
        await message.answer(f"⚠️ Drive লোডে সমস্যা: <code>{e}</code>", parse_mode="HTML")


@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and user_state[msg.from_user.id].get("action") == "awaiting_otp_drive")
async def watch_for_otp_drive(message: Message):
    """Drive থেকে নির্বাচিত সেশন ডাউনলোড করে Telegram OTP ক্যাচ করবে"""
    try:
        index = int(message.text.strip()) - 1
        state = user_state.get(message.from_user.id)
        files = state["files"]

        if index < 0 or index >= len(files):
            await message.answer("⚠️ ভুল ইনডেক্স দিয়েছেন।")
            return

        file_info = files[index]
        file_id = file_info["id"]
        file_name = file_info["name"]

        await message.answer(f"📂 Selected: <code>{file_name}</code>\n⏳ Downloading...", parse_mode="HTML")

        # 🔹 Drive থেকে ফাইল ডাউনলোড
        local_path = download_drive_file_to_tmp(file_id, file_name)

        # 🔹 সেশন লোড
        with open(local_path, "rb") as f:
            data = f.read()
        try:
            session_str = data.decode()
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        except:
            client = TelegramClient(local_path, API_ID, API_HASH)

        await client.connect()
        try:
            me = await client.get_me()
            phone = me.phone if me else "Unknown"
            await message.answer(f"📱 Phone: <code>{phone}</code>\n📤 Waiting for OTP from 777000...", parse_mode="HTML")
        except:
            await message.answer("📤 Waiting for Telegram OTP (777000)...")

        otp_caught = asyncio.get_event_loop().create_future()

        @client.on(events.NewMessage)
        async def otp_handler(event):
            if event.sender_id != 777000:
                return

            text = event.raw_text
            match_en = re.search(r"(\d{4,6})", text)
            match_ar = re.search(r"([\u0660-\u0669]{4,6})", text)
            otp = match_en.group(1) if match_en else None
            if otp and not otp_caught.done():
                otp_caught.set_result((otp, text))

        try:
            otp, text = await asyncio.wait_for(otp_caught, timeout=300)
            await bot.send_message(
                message.chat.id,
                f"✅ OTP Code: <code>{otp}</code>\n\nMessage:\n<code>{text}</code>",
                parse_mode="HTML"
            )
        except asyncio.TimeoutError:
            await message.answer("❌ OTP Timeout — ৫ মিনিট পার হয়ে গেছে।")
        finally:
            await client.disconnect()

    except Exception as e:
        await message.answer(f"❌ সমস্যা: <code>{e}</code>", parse_mode="HTML")
    finally:
        user_state.pop(message.from_user.id, None)
        try:
            os.remove(local_path)
        except:
            pass

@router.message(lambda msg: msg.text == "💀 Terminate")
async def terminate_prompt_drive(message: Message):
    """Google Drive থেকে টার্মিনেট সেশন দেখায় সুন্দর ডিজাইনে"""
    user_state.pop(message.from_user.id, None)

    try:
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name)"
        ).execute()

        files = results.get("files", [])
        user_id = str(message.from_user.id)
        files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not files:
            await message.answer("❌ কোনো সেশন পাওয়া যায়নি (Drive এ)।")
            return

        # 🌐 প্রফেশনাল ডিজাইন
        msg = "💀 <b>𝗦𝗲𝗹𝗲𝗰𝘁 𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗧𝗼 𝗧𝗲𝗿𝗺𝗶𝗻𝗮𝘁𝗲</b>\n\n"
        for i, f in enumerate(files, 1):
            name = f["name"].replace(".session", "")
            phone = name.split("_")[-1]
            if not phone:
                continue

            # 🇸🇦 দেশের পতাকা ও নাম আনছে
            flag, country = get_country_info("+" + phone if not phone.startswith("+") else phone)
            msg += f"⬢ {flag} <b>{country}</b> — +{phone}\n"

        msg += "\n────────────────────\n"
        msg += f"📛 <b>Total Sessions:</b> {len(files)} ✅\n"
        msg += "✏️ <b>Reply a number to terminate.</b>"

        await message.answer(msg, parse_mode="HTML")
        user_state[message.from_user.id] = {
            "action": "awaiting_terminate_index",
            "drive_files": files
        }

    except Exception as e:
        await message.answer(f"⚠️ কোনো সমস্যা ঘটেছে:\n`{e}`", parse_mode="Markdown")


@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and user_state[msg.from_user.id].get("action") == "awaiting_terminate_index")
async def terminate_sessions_drive(message: Message):
    """ইউজার যেই সেশন ইনডেক্স দেয়, সেটি টার্মিনেটের জন্য প্রস্তুত করে"""
    try:
        data = user_state[message.from_user.id]
        files = data.get("drive_files", [])
        index = int(message.text.strip()) - 1

        if index < 0 or index >= len(files):
            await message.answer("⚠️ ভুল ইনডেক্স দিয়েছেন।")
            user_state.pop(message.from_user.id, None)
            return

        file_meta = files[index]
        file_id = file_meta["id"]
        file_name = file_meta["name"]

        # ✅ সেশন ফাইল ডাউনলোড
        await message.answer(f"⏳ <b>Loading session:</b> <code>{file_name}</code>", parse_mode="HTML")
        local_path = download_drive_file_to_tmp(file_id, file_name)
        with open(local_path, "rb") as f:
            session_str = f.read().decode()

        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await message.answer("❌ এই সেশন অনুমোদিত নয়।")
            await client.disconnect()
            os.remove(local_path)
            user_state.pop(message.from_user.id, None)
            return

        sessions = await client(GetAuthorizationsRequest())
        auth_list = sessions.authorizations

        msg_lines = []
        for i, auth in enumerate(auth_list):
            platform = auth.platform or "Unknown"
            device_model = auth.device_model or "Unknown"
            ip = auth.ip or "Unknown"
            current = "🟢 (Current Device)" if auth.current else ""
            msg_lines.append(f"{i+1}. {platform} — {device_model} — {ip} {current}")

        # ✅ inline keyboard define
        terminate_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Confirm Terminate", callback_data="confirm_terminate")],
            [InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel_action")]
        ])

        user_state[message.from_user.id] = {
            "session_str": session_str,
            "drive_file_id": file_id,
            "drive_file_name": file_name
        }

        msg_text = "📱 <b>Active Devices</b>\n\n" + "\n".join(msg_lines)
        await message.answer(msg_text, parse_mode="HTML", reply_markup=terminate_keyboard)

    except Exception as e:
        await message.answer(f"❌ সমস্যা: {e}")
        try:
            await client.disconnect()
        except:
            pass
        user_state.pop(message.from_user.id, None)


@router.callback_query(lambda c: c.data == "confirm_terminate")
async def handle_terminate_callback(callback_query: types.CallbackQuery):
    """সেশন টার্মিনেট প্রক্রিয়া"""
    user_id = callback_query.from_user.id
    state = user_state.get(user_id)

    if not state or "session_str" not in state:
        await callback_query.message.answer("⚠️ সেশন পাওয়া যায়নি বা টাইমআউট হয়েছে।", reply_markup=main_menu)
        return

    session_str = state["session_str"]

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await callback_query.message.answer("❌ সেশন অনুমোদিত নয়।", reply_markup=main_menu)
            await client.disconnect()
            return

        sessions = await client(GetAuthorizationsRequest())
        terminated, failed = 0, 0

        for auth in sessions.authorizations:
            if not auth.current:
                try:
                    await client(ResetAuthorizationRequest(auth.hash))
                    terminated += 1
                except:
                    failed += 1

        if terminated > 0:
            msg = f"✅ <b>{terminated}</b> ডিভাইস থেকে সফলভাবে সাইন আউট করা হয়েছে।"
            if failed > 0:
                msg += f"\n⚠️ {failed} ডিভাইস ব্যর্থ হয়েছে।"
        else:
            msg = "⚠️ কোনো অন্য ডিভাইস পাওয়া যায়নি।"

        await callback_query.message.answer(msg, parse_mode="HTML", reply_markup=main_menu)

    except Exception as e:
        if "24 hours" in str(e):
            await callback_query.message.answer(
                "⚠️ Telegram নিয়ম অনুযায়ী, নতুন ডিভাইস দিয়ে ২৪ ঘণ্টার মধ্যে Terminate করা যাবে না।",
                reply_markup=main_menu
            )
        else:
            await callback_query.message.answer(f"❌ টার্মিনেট ত্রুটি: {e}", reply_markup=main_menu)
    finally:
        await client.disconnect()
        user_state.pop(user_id, None)


# ====== BEAUTIFIED: Import / Purge / Number-check features (Ready to paste) ======
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest, GetContactsRequest
from telethon.tl.types import InputPhoneContact, InputUser

# shared state
user_state = getattr(globals(), "user_state", {})  # preserve existing if any
if not isinstance(user_state, dict):
    user_state = {}
# ensure router exists
router = globals().get("router") or types.Router()

# -------------------
# Inline keyboards / constants (styled)
# -------------------
purge_option_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🗑️ Delete All Messages", callback_data="purge_messages")],
    [InlineKeyboardButton(text="🚪 Leave All Groups/Channels", callback_data="purge_groups")],
    [InlineKeyboardButton(text="👥 Delete All Contacts", callback_data="purge_contacts")],
    [InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_menu")]
])

terminate_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💣 Confirm Terminate", callback_data="confirm_terminate")],
    [InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel_action")]
])

# -------------------
# 1) 📥 Import Session (polished)
# -------------------
@router.message(lambda msg: msg.text == "📥 Import Session")
async def import_prompt_design(message: types.Message):
    user_state.pop(message.from_user.id, None)
    ui = (
        "📥 <b>Import Telegram Session</b>\n\n"
        "💾 Please upload your <code>.session</code> file (Document).\n\n"
        "Supported formats:\n"
        "• StringSession (text)\n"
        "• Telethon .session (SQLite)\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "⚙️ After import it will be optionally uploaded to Google Drive (if Drive configured)."
    )
    await message.answer(ui, parse_mode="HTML")
    user_state[message.from_user.id] = {"action": "awaiting_import_session"}


@router.message(lambda msg: msg.document and isinstance(user_state.get(msg.from_user.id), dict)
                and user_state[msg.from_user.id].get("action") == "awaiting_import_session")
async def handle_import_session(message: types.Message):
    try:
        file = message.document
        if not file.file_name.endswith(".session"):
            await message.answer("❌ Only `.session` files are accepted. Please resend.")
            return

        session_dir = get_user_session_dir(message.from_user.id)
        os.makedirs(session_dir, exist_ok=True)
        file_path = os.path.join(session_dir, file.file_name)

        await bot.download(file, destination=file_path)
        await message.answer("⏳ Session received — validating...")

        # Try both formats: text string session first, else sqlite file session
        client = None
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            try:
                stext = raw.decode().strip()
                client = TelegramClient(StringSession(stext), API_ID, API_HASH)
            except Exception:
                # fallback to file path session (Telethon can use path to sqlite session)
                client = TelegramClient(file_path, API_ID, API_HASH)

            await client.connect()
            if not await client.is_user_authorized():
                await message.answer("❌ Session invalid or expired. Please re-login and try again.")
                await client.disconnect()
                os.remove(file_path)
                return

            me = await client.get_me()
            await message.answer(f"✅ Session imported: <b>{me.first_name}</b> — <code>{me.phone}</code>", parse_mode="HTML")

            # optional: upload to drive (if function present)
            try:
                file_id = None
                if "upload_to_drive" in globals():
                    file_id = upload_to_drive(file_path, os.path.basename(file_path))
                if file_id:
                    await message.answer(f"☁️ Uploaded to Google Drive (File ID: <code>{file_id}</code>)", parse_mode="HTML")
            except Exception as e:
                await message.answer(f"⚠️ Drive upload failed: {e}")

            await client.disconnect()
        except Exception as e:
            await message.answer(f"❌ Import error: {e}")
            try:
                if client:
                    await client.disconnect()
            except:
                pass
            if os.path.exists(file_path):
                os.remove(file_path)
        finally:
            user_state.pop(message.from_user.id, None)

    except Exception as e:
        user_state.pop(message.from_user.id, None)
        await message.answer(f"❌ Unexpected: {e}")


# -------------------
# 2) 🧹 Purge Account (polished flow)
# -------------------
@router.message(lambda msg: msg.text == "🧹 Purge Account")
async def purge_start(message: types.Message):
    user_state.pop(message.from_user.id, None)
    ui = (
        "🧹 <b>Purge Account Control Panel</b>\n\n"
        "Choose an option below to purge data from the selected Telegram session.\n\n"
        "⚠️ Use carefully — actions are irreversible."
    )
    await message.answer(ui, parse_mode="HTML")
    # Ask for session file
    await message.answer("📂 Please send the <code>.session</code> file to purge (as Document).", parse_mode="HTML")
    user_state[message.from_user.id] = {"action": "awaiting_purge_session"}


@router.message(lambda msg: msg.document and isinstance(user_state.get(msg.from_user.id), dict)
                and user_state[msg.from_user.id].get("action") == "awaiting_purge_session")
async def purge_session_received(message: types.Message):
    try:
        doc = message.document
        if not doc.file_name.endswith(".session"):
            await message.answer("❌ Please upload a valid .session file.")
            return

        local = f"/tmp/{doc.file_name}"
        await bot.download(doc, destination=local)

        with open(local, "r") as f:
            session_str = f.read().strip()

        # store session_str and show purge options
        user_state[message.from_user.id] = {"action": "awaiting_purge_choice", "session_str": session_str}
        ui = "🔧 <b>Purge Options</b>\n\nSelect one:\n\n• 🗑 Delete All Messages\n• 🚪 Leave All Groups/Channels\n• 👥 Delete All Contacts"
        await message.answer(ui, parse_mode="HTML", reply_markup=purge_option_keyboard)
    except Exception as e:
        user_state.pop(message.from_user.id, None)
        await message.answer(f"❌ Error receiving session: {e}")


@router.callback_query(lambda c: c.data.startswith("purge_"))
async def handle_purge_action(callback_query: types.CallbackQuery):
    action = callback_query.data  # purge_messages / purge_groups / purge_contacts
    uid = callback_query.from_user.id
    state = user_state.get(uid)
    if not state or "session_str" not in state:
        await callback_query.message.answer("⚠️ Session missing. Please upload .session file first.")
        return

    session_str = state["session_str"]
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()

    try:
        if not await client.is_user_authorized():
            await callback_query.message.answer("❌ Session unauthorized.")
            await client.disconnect()
            user_state.pop(uid, None)
            return

        # show a processing message
        await callback_query.message.answer("⏳ Processing, please wait...")

        if action == "purge_messages":
            # delete messages from user/bot dialogs
            dialogs = await client.get_dialogs()
            deleted = 0
            for d in dialogs:
                try:
                    if d.is_user or d.is_bot:
                        await client(DeleteHistoryRequest(peer=d.entity, just_clear=False, revoke=True))
                        deleted += 1
                except:
                    pass
            await callback_query.message.answer(f"✅ Messages cleared in {deleted} chats.")
        elif action == "purge_groups":
            left = 0
            async for d in client.iter_dialogs():
                try:
                    if d.is_group or d.is_channel:
                        await client(LeaveChannelRequest(channel=d.entity))
                        left += 1
                except:
                    pass
            await callback_query.message.answer(f"🚪 Left {left} groups/channels.")
        elif action == "purge_contacts":
            result = await client(GetContactsRequest(hash=0))
            users = result.users
            input_users = [InputUser(u.id, u.access_hash) for u in users if u.access_hash]
            if input_users:
                await client(DeleteContactsRequest(id=input_users))
                await callback_query.message.answer(f"👥 Deleted {len(input_users)} contacts.")
            else:
                await callback_query.message.answer("⚠️ No contacts found.")
        else:
            await callback_query.message.answer("⚠️ Unknown option.")

    except Exception as e:
        await callback_query.message.answer(f"❌ Purge error: {e}")
    finally:
        try:
            await client.disconnect()
        except:
            pass
        user_state.pop(uid, None)


@router.callback_query(lambda c: c.data == "back_to_menu")
async def _back_menu(callback_query: types.CallbackQuery):
    # fallback to main menu (if defined)
    await callback_query.message.edit_text("🏠 Main Menu", parse_mode="HTML", reply_markup=globals().get("main_menu"))


# -------------------
# 3) 📡 Check Active Telegram Numbers (polished)
# -------------------
@router.message(lambda msg: msg.text == "📡 Check Active Telegram Numbers")
async def check_numbers_start(message: types.Message):
    user_state.pop(message.from_user.id, None)
    ui = (
        "📡 <b>Number Checker</b>\n\n"
        "1) Send your <code>.session</code> file (Document).\n"
        "2) Then send numbers (one per line)."
    )
    await message.answer(ui, parse_mode="HTML")
    user_state[message.from_user.id] = {"action": "awaiting_check_session"}


@router.message(lambda msg: msg.document and isinstance(user_state.get(msg.from_user.id), dict)
                and user_state[msg.from_user.id].get("action") == "awaiting_check_session")
async def check_session_received(message: types.Message):
    try:
        doc = message.document
        if not doc.file_name.endswith(".session"):
            await message.answer("❌ Please upload a valid .session file.")
            return
        local = f"/tmp/{doc.file_name}"
        await bot.download(doc, destination=local)
        with open(local, "r") as f:
            session_str = f.read().strip()

        user_state[message.from_user.id] = {"action": "awaiting_numbers", "session_str": session_str}
        await message.answer("🧾 Now send numbers (one per line), example:\n+88017XXXXXXX\n+9665XXXXXXX", parse_mode="HTML")
    except Exception as e:
        user_state.pop(message.from_user.id, None)
        await message.answer(f"❌ Error: {e}")


@router.message(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and user_state[msg.from_user.id].get("action") == "awaiting_numbers")
async def handle_numbers_check(message: types.Message):
    try:
        lines = [l.strip() for l in message.text.splitlines() if l.strip()]
        if not lines:
            await message.answer("⚠️ No numbers provided.")
            return

        state = user_state[message.from_user.id]
        session_str = state.get("session_str")
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await message.answer("❌ Session unauthorized.")
            await client.disconnect()
            user_state.pop(message.from_user.id, None)
            return

        await message.answer("🔍 Checking numbers — please wait...")

        contacts = [InputPhoneContact(client_id=i, phone=n.replace("+", ""), first_name="Check", last_name="") for i, n in enumerate(lines)]
        res = await client(ImportContactsRequest(contacts))
        found = res.users or []

        active_list = []
        for u in found:
            if getattr(u, "phone", None):
                flag, country = get_country_info("+" + str(u.phone))
                active_list.append(f"{flag} <b>{country}</b> — +{u.phone}")

        # cleanup imported contacts
        if found:
            # convert to InputUser list for delete
            try:
                await client(DeleteContactsRequest(id=[InputUser(u.id, u.access_hash) for u in found]))
            except:
                pass

        if active_list:
            msg = "✅ <b>Active Telegram numbers found:</b>\n\n" + "\n".join(active_list)
        else:
            msg = "❌ No active Telegram accounts found in the provided numbers."

        await message.answer(msg, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        try:
            await client.disconnect()
        except:
            pass
        user_state.pop(message.from_user.id, None)

# ============================================================
# 📋 CHECK SESSION HEALTH FEATURE (by Nahid Bot)
# ============================================================
import random, time

SPAMBOT_USERNAME = "@SpamBot"
SPAMBOT_REPLY_TIMEOUT = 25
SPAMBOT_POLL_INTERVAL = 2
CHECK_DELAY = 4   # প্রতিটি সেশনের মাঝে ৪ সেকেন্ড বিরতি (Rate Limit এড়াতে)

async def check_with_spambot(client):
    """@SpamBot এ /start পাঠিয়ে রিপ্লাই চেক করবে"""
    try:
        await asyncio.sleep(random.uniform(1, 2))
        await client.send_message(SPAMBOT_USERNAME, "/start")

        deadline = time.time() + SPAMBOT_REPLY_TIMEOUT
        while time.time() < deadline:
            msgs = await client.get_messages(SPAMBOT_USERNAME, limit=4)
            for m in msgs:
                if hasattr(m, "out") and not m.out:
                    text = (m.message or "").strip()
                    low = text.lower()
                    if any(k in low for k in ["limited", "suspended", "restricted", "frozen", "ban", "blocked"]):
                        return ("limited", text)
                    if any(k in low for k in ["warning", "spam", "suspicious", "report"]):
                        return ("warning", text)
                    return ("ok", text)
            await asyncio.sleep(SPAMBOT_POLL_INTERVAL)
        return ("no_reply", "No reply from SpamBot.")
    except Exception as e:
        return ("error", str(e))


@router.message(lambda msg: msg.text == "📋 Check Session Health")
async def check_all_sessions_health(message: Message):
    """লাইভ প্রগ্রেস ও ডিটেইল রিপোর্টসহ সেশন হেলথ চেক"""
    progress_msg = await message.answer("🔍 সেশন হেলথ চেক শুরু হচ্ছে...\n\n⏳ প্রস্তুতি নিচ্ছে...")

    try:
        # Google Drive থেকে সেশন লিস্ট আনো
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name)",
            orderBy="createdTime desc"
        ).execute()
        files = results.get("files", [])
        user_id = str(message.from_user.id)
        user_files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not user_files:
            await progress_msg.edit_text("❌ কোনো সেশন পাওয়া যায়নি।")
            return

        total = len(user_files)
        active = frozen = limited = failed = 0

        frozen_set = set()
        limited_set = set()
        failed_set = set()

        await progress_msg.edit_text(f"📦 মোট {total} টি সেশন চেক করা হবে...\n\nProgress: 0/{total} ⏳")

        for index, meta in enumerate(user_files, start=1):
            file_id = meta["id"]
            file_name = meta["name"]

            # fallback number (session name থেকে)
            try:
                raw_num = file_name.split("_")[1].split(".")[0]
                phone_number = "+" + raw_num if not raw_num.startswith("+") else raw_num
            except Exception:
                phone_number = "Unknown"

            flag, country = get_country_info(phone_number)

            try:
                local_path = download_drive_file_to_tmp(file_id, file_name)
                with open(local_path, "rb") as f:
                    session_str = f.read().decode()

                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()

                if not await client.is_user_authorized():
                    failed += 1
                    failed_set.add(f"{flag} {phone_number}")
                    await client.disconnect()
                    os.remove(local_path)
                    continue

                me = await client.get_me()
                phone_number = "+" + str(me.phone)
                flag, country = get_country_info(phone_number)

                # ✅ টেস্ট মেসেজ পাঠাও
                can_send = True
                try:
                    await client.send_message("me", "✅ Health Check Test")
                except Exception:
                    can_send = False

                # ✅ SpamBot চেক
                status, _ = await check_with_spambot(client)

                # ফলাফল নির্ধারণ
                if not can_send:
                    frozen += 1
                    frozen_set.add(f"{flag} {phone_number}")
                elif status in ("limited", "warning"):
                    limited += 1
                    limited_set.add(f"{flag} {phone_number}")
                elif status == "ok":
                    active += 1
                else:
                    failed += 1
                    failed_set.add(f"{flag} {phone_number}")

                await client.disconnect()
                os.remove(local_path)

            except Exception:
                failed += 1
                failed_set.add(f"{flag} {phone_number}")

            # লাইভ প্রগ্রেস আপডেট
            progress_text = (
                f"📋 <b>Session Health Check Running...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ Progress: {index}/{total}\n\n"
                f"✅ Active: {active}\n"
                f"⚠️ Limited: {limited}\n"
                f"🧊 Frozen: {frozen}\n"
                f"❌ Failed: {failed}\n"
            )
            await progress_msg.edit_text(progress_text, parse_mode="HTML")
            await asyncio.sleep(CHECK_DELAY)

        # 🔚 ফাইনাল রিপোর্ট
        report = (
            f"🏁 <b>Session Health Check Completed!</b>\n\n"
            f"✅ Active: {active}\n"
            f"⚠️ Limited: {limited}\n"
            f"🧊 Frozen: {frozen}\n"
            f"❌ Failed: {failed}\n"
            f"📦 Total: {total}\n\n"
        )

        # Frozen
        if frozen_set:
            report += "🧊 <b>Frozen Sessions:</b>\n"
            for num in frozen_set:
                report += f"{num}\n"
            report += "\n"

        # Limited
        if limited_set:
            report += "⚠️ <b>Limited Sessions:</b>\n"
            for num in limited_set:
                report += f"{num}\n"
            report += "\n"

        # Failed
        if failed_set:
            report += "❌ <b>Failed Sessions:</b>\n"
            for num in failed_set:
                report += f"{num}\n"

        await progress_msg.edit_text(report, parse_mode="HTML")

    except Exception as e:
        await progress_msg.edit_text(f"❌ ত্রুটি ঘটেছে: <code>{e}</code>", parse_mode="HTML")

# ---------------------------
# 🔎 Session Authorization Checker (no OTP required)
# ---------------------------
@router.message(lambda msg: msg.text == "🔎 Check Session Authorization")
async def check_session_authorization(message: Message):
    """
    GPT: This handler checks all session files in Drive for whether they are
    still authorized (works without needing the SIM/OTP).
    """
    progress = await message.answer("🔍 Checking session authorizations...\n\n⏳ Preparing...")
    try:
        # list files in drive
        results = drive_service.files().list(
            q=f"'{GOOGLE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name)",
            orderBy="createdTime desc"
        ).execute()
        files = results.get("files", [])
        user_id = str(message.from_user.id)
        user_files = [f for f in files if f["name"].startswith(user_id + "_")]

        if not user_files:
            await progress.edit_text("❌ কোনো সেশন পাওয়া যায়নি (Drive এ)।")
            return

        total = len(user_files)
        ok_list = []
        bad_list = []
        unknown_list = []
        await progress.edit_text(f"📦 মোট {total} সেশন পাওয়া গেল — Progress: 0/{total}")

        for idx, meta in enumerate(user_files, start=1):
            file_id = meta["id"]; file_name = meta["name"]
            # try to infer phone from filename as fallback
            try:
                raw_num = file_name.split("_", 1)[1].replace(".session", "")
                fallback_phone = ("+" + raw_num) if not raw_num.startswith("+") else raw_num
            except Exception:
                fallback_phone = "Unknown"

            status_line = f"{idx}/{total} — {file_name} : "

            try:
                local = download_drive_file_to_tmp(file_id, file_name)
                with open(local, "rb") as fh:
                    data = fh.read()
                # attempt to decode string session; if fails, use file path for Telethon
                try:
                    session_text = data.decode()
                    client = TelegramClient(StringSession(session_text), API_ID, API_HASH)
                except Exception:
                    client = TelegramClient(local, API_ID, API_HASH)

                await client.connect()
                try:
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        phone = getattr(me, "phone", None)
                        if phone:
                            ph = "+" + str(phone)
                        else:
                            ph = fallback_phone
                        flag, country = get_country_info(ph)
                        ok_list.append((flag, ph, file_name))
                    else:
                        # unauthorized
                        bad_list.append((fallback_phone, file_name))
                except Exception as e:
                    # could not fetch me; mark unknown but include filename
                    unknown_list.append((str(e)[:80], file_name))
                finally:
                    await client.disconnect()
                # remove local temp
                try: os.remove(local)
                except: pass

            except Exception as e:
                # can't download / open - treat as failed/unknown
                unknown_list.append((str(e)[:80], file_name))

            # update live progress
            done = idx
            await progress.edit_text(
                f"🔍 Checking authorizations...\nProgress: {done}/{total}\n\n"
                f"✅ OK: {len(ok_list)}  |  ❌ Unauthorized: {len(bad_list)}  |  ❓ Errors: {len(unknown_list)}"
            )

            # small delay to be gentle on Drive / I/O
            await asyncio.sleep(0.8)

        # build final report text
        report = "🏁 <b>Session Authorization Report</b>\n\n"
        report += f"📦 Total checked: {total}\n"
        report += f"✅ Authorized: {len(ok_list)}\n"
        report += f"❌ Unauthorized / Expired: {len(bad_list)}\n"
        report += f"❓ Errors: {len(unknown_list)}\n\n"

        if ok_list:
            report += "✅ <b>Authorized Sessions (can be used without OTP)</b>:\n"
            for flag, ph, fname in ok_list:
                report += f"{flag} {ph} — <code>{fname}</code>\n"
            report += "\n"
        if bad_list:
            report += "❌ <b>Unauthorized / Expired Sessions (need re-login / SIM)</b>:\n"
            for ph, fname in bad_list:
                report += f"{ph} — <code>{fname}</code>\n"
            report += "\n"
        if unknown_list:
            report += "❓ <b>Errors / Could not determine</b>:\n"
            for err, fname in unknown_list:
                report += f"{fname} — <code>{err}</code>\n"

        await progress.edit_text(report, parse_mode="HTML")

    except Exception as e:
        await progress.edit_text(f"❌ Error while checking sessions: <code>{e}</code>", parse_mode="HTML")

# ====== end of block ======


import asyncio
import logging

async def heartbeat():
    while True:
        print("✅ Bot is alive...")
        await asyncio.sleep(10)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("🚀 Starting bot...")

    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(heartbeat())  # optional
    await dp.start_polling(bot)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("❌ Bot stopped manually.")