import os
import re
import json
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Request, Response

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# Import your existing supabase client
from db.supabase_client import supabase

# --- CONFIG ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram-bot")

# --- FASTAPI APP ---
app = FastAPI()

# --- TELEGRAM APP ---
telegram_app = Application.builder().token(BOT_TOKEN).build()

# --- MARKDOWN & HELPERS ---
def md_escape(text: str) -> str:
    if not text: return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

def extract_ig_username(text: str) -> Optional[str]:
    text = text.strip()
    if "instagram.com" in text:
        m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", text)
        return m.group(1) if m else None
    if text.startswith("@"): return text[1:]
    if re.fullmatch(r"[A-Za-z0-9_.]+", text): return text
    return None

# --- DATABASE HELPERS ---
def get_session(chat_id: str):
    return supabase.table("telegram_sessions").select("*").eq("chat_id", chat_id).maybe_single().execute().data

def save_session(chat_id: str, stage: str, payload: dict):
    supabase.table("telegram_sessions").upsert({"chat_id": chat_id, "stage": stage, "payload": payload}).execute()

def clear_session(chat_id: str):
    supabase.table("telegram_sessions").delete().eq("chat_id", chat_id).execute()

# --- BOT LOGIC ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    chat_id, text = str(msg.chat.id), msg.text.strip()
    session = get_session(chat_id)

    if session and session.get("stage") == "project":
        try:
            projects = session["payload"]["projects"]
            project = projects[int(text) - 1]
            ig = session["payload"]["ig"]
            
            row = supabase.table("monitored_accounts").select("id, ig_username").eq("project_id", project["id"]).maybe_single().execute().data
            if not row:
                supabase.table("monitored_accounts").insert({"project_id": project["id"], "ig_username": ig}).execute()
            else:
                existing = [u.strip() for u in (row.get("ig_username") or "").split(",") if u.strip()]
                if ig not in existing:
                    existing.append(ig)
                    supabase.table("monitored_accounts").update({"ig_username": ", ".join(existing)}).eq("id", row["id"]).execute()
            
            await msg.reply_text(f"✅ *@{md_escape(ig)}* added to *{md_escape(project['name'])}*", parse_mode=ParseMode.MARKDOWN_V2)
            clear_session(chat_id)
        except:
            await msg.reply_text("❌ Invalid selection.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    ig = extract_ig_username(text)
    if not ig: return

    acc = supabase.table("telegram_accounts").select("user_id").eq("chat_id", chat_id).maybe_single().execute().data
    if not acc:
        await msg.reply_text("❌ Please complete setup first.")
        return

    projs = supabase.table("projects").select("id,name").eq("user_id", acc["user_id"]).eq("active", True).execute().data
    if not projs:
        await msg.reply_text("❌ No active projects.")
        return

    reply = f"Choose a project for *@{md_escape(ig)}*:\n\n" + "\n".join([f"{i+1}\\. {md_escape(p['name'])}" for i, p in enumerate(projs)])
    save_session(chat_id, "project", {"ig": ig, "projects": projs})
    await msg.reply_text(reply, parse_mode=ParseMode.MARKDOWN_V2)

# Register Handlers
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- WEBHOOK ENDPOINT ---
@app.post("/api/bot")
async def webhook_handler(request: Request):
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != WEBHOOK_SECRET:
            return Response(status_code=403)

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    
    async with telegram_app:
        await telegram_app.process_update(update)
    
    return {"status": "ok"}

@app.get("/api/bot")
async def health_check():
    return {"status": "alive"}