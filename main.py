# pip install python-telegram-bot==21.6
import os, sqlite3, random, time
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ContextTypes)

TOKEN = os.environ["BOT_TOKEN"]            # env variable se token
ADMIN_ID = int(os.environ["ADMIN_ID"])     # owner ki Telegram numeric ID

PREMIUM_CONTACT = "@ZenithSsupport"        # Premium "Prove" yahin khulega
SUPPORT_URL = "https://t.me/hellllooo4"    # Support button
UPDATE_CHANNEL_URL = os.environ.get("UPDATE_CHANNEL_URL", "")  # channel link yaha daalo
VERY_GOOD_AT, PREMIUM_AT = 100, 200
PENDING_DAYS = 30                          # itne din tak pending yaad rakhega

HEARTS = "♥️♥️♥️♥️♥️"
HI_TEXT = f"Main HeartMatch se aaya hu, kya hum baat kar sakte hain? {HEARTS}"
PREMIUM_TEXT = "I want to join premium membership"

db = sqlite3.connect(os.environ.get("DB_PATH", "bot.db"), check_same_thread=False)
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
  tg_id INTEGER PRIMARY KEY, uid TEXT UNIQUE, gender TEXT,
  points INTEGER DEFAULT 0, premium INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS links(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT);
CREATE TABLE IF NOT EXISTS pending(seeker INTEGER PRIMARY KEY, earner TEXT);
""")
for tbl, col in (("users", "premium INTEGER DEFAULT 0"),
                 ("users", "username TEXT"),
                 ("pending", "ts INTEGER"),
                 ("pending", "g TEXT"),
                 ("pending", "t TEXT")):
    try:
        db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
    except sqlite3.OperationalError:
        pass
db.execute("UPDATE pending SET ts=? WHERE ts IS NULL", (int(time.time()),))
db.commit()

# gender: "boy" = BF, "girl" = GF
def tier(points, premium, gender):
    if gender == "boy":                      # BF me sirf good / very good
        return "very" if (premium or points >= VERY_GOOD_AT) else "good"
    if premium or points >= PREMIUM_AT: return "premium"
    return "very" if points >= VERY_GOOD_AT else "good"

NAMES = {"boy": {"good": "Good BF", "very": "Very Good BF"},
         "girl": {"good": "Good GF", "very": "Very Good GF", "premium": "Premium GF"}}

def support_row():
    row = [B("🆘 Support", url=SUPPORT_URL)]
    if UPDATE_CHANNEL_URL:
        row.append(B("📢 Updates", url=UPDATE_CHANNEL_URL))
    return row

def rate_kb(uid):
    return M([[B("Report" if i == 0 else str(i), callback_data=f"rate:{uid}:{i}")
               for i in range(6)],
              support_row()])

def menu_kb():
    return M([[B("🎫 Join Membership", callback_data="earn")],
              [B("💞 Need Partner", callback_data="seek")],
              [B("🎥 Video Link", callback_data="video")],
              support_row()])

def pending_of(tg):
    # 30 din se purani pending entries history se hata do
    db.execute("DELETE FROM pending WHERE ts < ?",
               (int(time.time()) - PENDING_DAYS * 86400,)); db.commit()
    r = db.execute("SELECT earner FROM pending WHERE seeker=?", (tg,)).fetchone()
    return r[0] if r else None

PENDING_MSG = "⚠️ Pehle pichli ID ko rating do. Rating ke baad hi aage badh sakte ho."

async def edit(q, text, **kw):
    try:
        await q.edit_message_text(text, **kw)
    except BadRequest as e:               # same text dobara bhejne par error ignore
        if "not modified" not in str(e).lower():
            raise

# ---------- user flow ----------
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    p = pending_of(u.effective_user.id)
    if p:
        return await u.effective_message.reply_text(PENDING_MSG, reply_markup=rate_kb(p))
    await u.effective_message.reply_text("💘 HeartMatch me aapka swagat hai!\nNeeche se chuno:",
                                         reply_markup=menu_kb())

async def join_check(q, g):
    """Username check -> membership join."""
    me, un = q.from_user.id, q.from_user.username
    if not un:
        return await edit(
            q, "⚠️ Aapka username nahi hai.\n\n"
               "Telegram Settings me jao, username set karo, "
               "phir 'Check again' dabao.",
            reply_markup=M([[B("🔄 Check again", callback_data=f"chk:{g}")]]))
    db.execute("INSERT INTO users(tg_id,uid,gender,username) VALUES(?,?,?,?) "
               "ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, "
               "gender=excluded.gender", (me, str(me), g, un))
    db.commit()
    await edit(q, "✅ Aap member ban gaye!\n\n"
                  "Ab /start dabao aur 'Need Partner' dabake ID lo.")

async def give_match(q, c, me, g, t):
    rows = [r for r in db.execute(
        "SELECT uid,tg_id,points,premium,username FROM users "
        "WHERE gender=? AND tg_id!=?", (g, me)) if tier(r[2], r[3], g) == t]
    random.shuffle(rows)
    for uid, tg, _, _, un in rows[:25]:
        try:                               # latest username lo
            un = (await c.bot.get_chat(tg)).username
        except Exception:
            pass                           # fetch fail -> saved username
        if not un:
            continue
        db.execute("UPDATE users SET username=? WHERE tg_id=?", (un, tg))
        db.execute("INSERT OR REPLACE INTO pending(seeker,earner,ts,g,t) "
                   "VALUES(?,?,?,?,?)", (me, uid, int(time.time()), g, t)); db.commit()
        url = f"https://t.me/{un}?text={quote(HI_TEXT)}"
        return await edit(
            q, f"💘 {NAMES[g][t]} ki ID mil gayi!\n\n"
               "'Chat now' dabao. Message pehle se likha hoga, bas Send karo.\n"
               "Baat ke baad rating dena zaruri hai.",
            reply_markup=M([[B("💬 Chat now", url=url)],
                            [B("⭐ Rate now", callback_data=f"rm:{uid}")]]))
    await edit(q, "Abhi is category me koi nahi hai. Thodi der baad try karo.")

async def cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer()
    d = q.data.split(":"); a = d[0]; me = q.from_user.id

    # rating pending ho to rating ke alawa kuchh bhi allowed nahi
    if a not in ("rm", "rate"):
        p = pending_of(me)
        if p:
            return await q.message.reply_text(PENDING_MSG, reply_markup=rate_kb(p))

    if a == "home":
        return await edit(q, "💘 HeartMatch me aapka swagat hai!\nNeeche se chuno:",
                          reply_markup=menu_kb())

    if a == "video":
        links = db.execute("SELECT url FROM links").fetchall()
        if not links:
            return await q.message.reply_text("Abhi koi video link nahi hai.")
        return await q.message.reply_text(
            "🎥 Video links:\n\n" + "\n".join(x[0] for x in links))

    # ----- JOIN MEMBERSHIP -----
    if a == "earn":
        row = db.execute("SELECT username FROM users WHERE tg_id=?", (me,)).fetchone()
        if row and row[0]:
            return await edit(q, "✅ Aap pehle se member ho.")
        await edit(
            q, "🎫 Join Membership\n\n"
               "Aapko baat karne ke liye dusre members ki ID milegi.\n"
               "Jitna achha baat karoge, utni achhi rating milegi.\n"
               "Rating ke hisab se aapko achhi category aur achhe users milenge.\n\nChuno:",
            reply_markup=M([[B("👦 I am Boy", callback_data="eg:boy"),
                             B("👧 I am Girl", callback_data="eg:girl")]]))

    elif a == "eg":
        if d[1] == "boy":                  # boy: seedha username check
            return await join_check(q, "boy")
        await edit(q, "Kaun sa membership chahiye?", reply_markup=M([
            [B("🙂 Normal", callback_data="chk:girl")],
            [B("👑 Premium", callback_data="prem")]]))

    elif a == "chk":
        await join_check(q, d[1])

    elif a == "prem":
        url = (f"https://t.me/{PREMIUM_CONTACT.lstrip('@')}"
               f"?text={quote(f'{PREMIUM_TEXT}. My ID: {me}')}")
        await edit(
            q, "👑 Premium Membership\n\n"
               "Admin check karega ki aap girl ho. Check hone ke baad aap "
               "Premium GF category me aa jaoge.\n\n"
               "'Prove' dabao. Support chat khulega aur message pehle se likha hoga.",
            reply_markup=M([[B("⬅️ Back", callback_data="eg:girl"),
                             B("✅ Prove", url=url)]]))

    # ----- NEED PARTNER -----
    elif a == "seek":
        await edit(q, "Aapko kya chahiye?", reply_markup=M([[
            B("💙 BF", callback_data="sg:boy"), B("💖 GF", callback_data="sg:girl")]]))

    elif a == "sg":
        g = d[1]
        rows = [[B(f"{e} {NAMES[g][t]}", callback_data=f"t:{g}:{t}")]
                for e, t in (("⭐", "good"), ("🌟", "very"), ("👑", "premium"))
                if t in NAMES[g]]
        await edit(q, "Category chuno:", reply_markup=M(rows))

    elif a == "t":
        await give_match(q, c, me, d[1], d[2])

    elif a == "rm":
        await edit(q, "Rating do:\nReport = bura, 5 = bahut achha",
                   reply_markup=rate_kb(d[1]))

    elif a == "rate":
        uid, r = d[1], int(d[2])
        if pending_of(me) != uid:
            return await edit(q, "Is ID ko aap rating de chuke ho.")
        g, t = db.execute("SELECT g,t FROM pending WHERE seeker=?", (me,)).fetchone()
        pts = -1 if r == 0 else r
        db.execute("UPDATE users SET points=MAX(points+?,0) WHERE uid=?", (pts, uid))
        db.execute("DELETE FROM pending WHERE seeker=?", (me,)); db.commit()
        row = []
        if g and t:
            row.append(B("🔄 Other ID", callback_data=f"t:{g}:{t}"))
        row.append(B("🏠 Start", callback_data="home"))
        await edit(q, "✅ Shukriya! Rating mil gayi.", reply_markup=M([row]))

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
