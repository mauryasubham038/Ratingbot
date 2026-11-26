# pip install python-telegram-bot==21.6
import sqlite3, random, time
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ContextTypes)

TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 123456789               # owner ki Telegram numeric ID
PREMIUM_CONTACT = "@hellllooo4"
VERY_GOOD_AT, PREMIUM_AT = 100, 200
PENDING_DAYS = 30                  # itne din tak pending yaad rakhega
SUPPORT_URL = "https://t.me/hellllooo4"

db = sqlite3.connect("bot.db", check_same_thread=False)
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
  tg_id INTEGER PRIMARY KEY, uid TEXT UNIQUE, gender TEXT,
  points INTEGER DEFAULT 0, premium INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS links(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT);
CREATE TABLE IF NOT EXISTS pending(seeker INTEGER PRIMARY KEY, earner TEXT);
""")
for tbl, col in (("users", "premium INTEGER DEFAULT 0"),
                 ("pending", "ts INTEGER")):
    try:
        db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
    except sqlite3.OperationalError:
        pass
db.execute("UPDATE pending SET ts=? WHERE ts IS NULL", (int(time.time()),))
db.commit()

def tier(points, premium):
    if premium or points >= PREMIUM_AT: return "premium"
    return "very" if points >= VERY_GOOD_AT else "good"

NAMES = {"good": "Good Girl", "very": "Very Good Girl", "premium": "Premium Girl"}

def rate_kb(uid):
    return M([[B(str(i), callback_data=f"rate:{uid}:{i}") for i in range(6)],
              SUPPORT_ROW])

SUPPORT_ROW = [B("🆘 Support @hellllooo4", url=SUPPORT_URL)]

def pending_of(tg):
    # 30 din se purani pending entries history se hata do
    db.execute("DELETE FROM pending WHERE ts < ?",
               (int(time.time()) - PENDING_DAYS * 86400,)); db.commit()
    r = db.execute("SELECT earner FROM pending WHERE seeker=?", (tg,)).fetchone()
    return r[0] if r else None

# ---------- user flow ----------
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = M([[B("💰 Earn Me", callback_data="earn")],
            [B("🙋 Service Want", callback_data="seek")],
            [B("🎥 Video", callback_data="video")],
            SUPPORT_ROW])
    p = pending_of(u.effective_user.id)
    if p:
        return await u.effective_message.reply_text(
            "⚠️ Pehle pichli ID ko rating do, tab tak bot aur kuchh nahi karega.",
            reply_markup=rate_kb(p))
    await u.effective_message.reply_text("Welcome! Choose an option:", reply_markup=kb)

async def cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer()
    d = q.data.split(":"); a = d[0]; me = q.from_user.id

    # rating pending ho to rating ke alawa kuchh bhi allowed nahi
    if a not in ("rm", "rate"):
        p = pending_of(me)
        if p:
            return await q.message.reply_text(
                "⚠️ Pehle pichli ID ko rating do, tab tak bot aur kuchh nahi karega.",
                reply_markup=rate_kb(p))

    if a == "video":
        links = db.execute("SELECT url FROM links").fetchall()
        if not links:
            return await q.message.reply_text("Abhi koi video link available nahi hai.")
        return await q.message.reply_text(f"🎥 Video link:\n{random.choice(links)[0]}")

    # ----- EARN -----
    if a == "earn":
        row = db.execute("SELECT uid FROM users WHERE tg_id=?", (me,)).fetchone()
        if row:
            return await q.edit_message_text(f"Aap already add ho.\nYour ID: {row[0]}")
        await q.edit_message_text("Select:", reply_markup=M([[
            B("👦 I am Boy", callback_data="eg:boy"),
            B("👧 I am Girl", callback_data="eg:girl")]]))

    elif a == "eg":
        await q.edit_message_text("Choose:", reply_markup=M([
            [B("✅ Without verification", callback_data=f"wv:{d[1]}")],
            [B("👑 Premium", callback_data="prem")]]))

    elif a == "prem":
        await q.edit_message_text(
            f"👑 Premium me add hone ke liye {PREMIUM_CONTACT} se baat karo.")

    elif a == "wv":
        await q.edit_message_text(
            "Service dene ke liye aap agree karte ho? (18+ only)",
            reply_markup=M([[B("✅ You agree", callback_data=f"agree:{d[1]}")]]))

    elif a == "agree":
        if not db.execute("SELECT 1 FROM users WHERE tg_id=?", (me,)).fetchone():
            db.execute("INSERT INTO users(tg_id,uid,gender) VALUES(?,?,?)",
                       (me, str(me), d[1]))
            db.commit()
        await q.edit_message_text(f"✅ Add ho gaye!\nYour ID: {me}")

    # ----- SERVICE WANT -----
    elif a == "seek":
        p = pending_of(me)
        if p:
            return await q.edit_message_text(
                "⚠️ Pehle pichli ID ko rating do, phir nayi ID milegi.",
                reply_markup=rate_kb(p))
        await q.edit_message_text("Select:", reply_markup=M([[
            B("👦 Boy", callback_data="sg:boy"), B("👧 Girl", callback_data="sg:girl")]]))

    elif a == "sg":
        g = d[1]
        await q.edit_message_text("Choose category:", reply_markup=M([
            [B("⭐ Good Girl", callback_data=f"t:{g}:good")],
            [B("🌟 Very Good Girl", callback_data=f"t:{g}:very")],
            [B("👑 Premium Girl", callback_data=f"t:{g}:premium")]]))

    elif a == "t":
        g, t = d[1], d[2]
        p = pending_of(me)
        if p:
            return await q.edit_message_text(
                "⚠️ Pehle pichli ID ko rating do, phir nayi ID milegi.",
                reply_markup=rate_kb(p))
        rows = [r for r in db.execute(
            "SELECT uid,tg_id,points,premium FROM users "
            "WHERE gender=? AND tg_id!=?", (g, me))
            if tier(r[2], r[3]) == t]
        if not rows:
            return await q.edit_message_text("Abhi is category me koi available nahi hai.")
        uid, tg = random.choice(rows)[:2]
        db.execute("INSERT OR REPLACE INTO pending(seeker,earner,ts) VALUES(?,?,?)",
                   (me, uid, int(time.time()))); db.commit()
        link = f"tg://user?id={tg}"   # sirf Telegram ID, username save nahi hota
        await q.edit_message_text(
            f'💬 <a href="{link}">👉 Yaha click karke baat karo</a>\n\n'
            "Baat ke baad rating dena zaruri hai.",
            parse_mode="HTML",
            reply_markup=M([[B("⭐ Rate now", callback_data=f"rm:{uid}")]]))

    elif a == "rm":
        await q.edit_message_text(
            "Rating do (0 = kharab, 5 = bahut accha):", reply_markup=rate_kb(d[1]))

    elif a == "rate":
        uid, r = d[1], int(d[2])
        if pending_of(me) != uid:
            return await q.edit_message_text("Ye rating pehle hi ho chuki hai.")
        pts = -1 if r == 0 else r
        db.execute("UPDATE users SET points=MAX(points+?,0) WHERE uid=?", (pts, uid))
        db.execute("DELETE FROM pending WHERE seeker=?", (me,)); db.commit()
        await q.edit_message_text("✅ Thanks! Rating add ho gayi.\nNayi ID ke liye Service Want dabao.")

# ---------- owner commands ----------
def admin(f):
    async def w(u, c):
        if u.effective_user.id != ADMIN_ID:
            return await u.message.reply_text("Not allowed.")
        return await f(u, c)
    return w

@admin
async def addlink(u, c):
    if not c.args: return await u.message.reply_text("Use: /addlink URL")
    db.execute("INSERT INTO links(url) VALUES(?)", (c.args[0],)); db.commit()
    await u.message.reply_text("✅ Link added.")

@admin
async def dellink(u, c):
    if not c.args: return await u.message.reply_text("Use: /dellink ID")
    db.execute("DELETE FROM links WHERE id=?", (c.args[0],)); db.commit()
    await u.message.reply_text("🗑 Link deleted.")

@admin
async def links(u, c):
    rows = db.execute("SELECT id,url FROM links").fetchall()
    await u.message.reply_text("\n".join(f"{i}: {x}" for i, x in rows) or "No links.")

@admin
async def addpremium(u, c):
    a = c.args
    if not a or not a[0].isdigit():
        return await u.message.reply_text(
            "Registered user: /addpremium <tg_id>\n"
            "Naya user: /addpremium <tg_id> <boy|girl>")
    tg = int(a[0])
    if db.execute("SELECT 1 FROM users WHERE tg_id=?", (tg,)).fetchone():
        db.execute("UPDATE users SET premium=1 WHERE tg_id=?", (tg,))
    else:
        if len(a) < 2 or a[1] not in ("boy", "girl"):
            return await u.message.reply_text("Use: /addpremium <tg_id> <boy|girl>")
        db.execute("INSERT INTO users(tg_id,uid,gender,premium) VALUES(?,?,?,1)",
                   (tg, str(tg), a[1]))
    db.commit()
    await u.message.reply_text("👑 Premium me add ho gaya.")

@admin
async def delpremium(u, c):
    if not c.args or not c.args[0].isdigit():
        return await u.message.reply_text("Use: /delpremium <tg_id>")
    db.execute("UPDATE users SET premium=0 WHERE tg_id=?", (int(c.args[0]),)); db.commit()
    await u.message.reply_text("Premium hata diya.")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addlink", addlink))
app.add_handler(CommandHandler("dellink", dellink))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("addpremium", addpremium))
app.add_handler(CommandHandler("delpremium", delpremium))
app.add_handler(CallbackQueryHandler(cb))
app.run_polling()
