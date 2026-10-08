import os, re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
order_map = {}
last_order_by_user = {}

def format_rupiah(s):
    clean = re.sub(r'[^0-9]', '', s)
    try: return f"{int(clean):,}".replace(",", ".")
    except: return s

def get_field(text, key):
    for line in text.splitlines():
        if key.lower() in line.lower() and ":" in line:
            return line.split(":",1)[1].strip()
    return ""

def is_product_valid(produk):
    low = produk.lower().strip()
    has_kuota = bool(re.search(r'\d+(\.\d+)?\s*(gb|mb|giga)', low))
    has_masa = bool(re.search(r'\d*\s*(hari|tahun|bulan|minggu)', low))
    list_kartu = ["axis", "by.u", "byu", "indosat", "isat", "telkomsel", "tsel", "xl", "smartfren", "smart", "fren", "tri", "three", "3", "by u"]
    has_kartu = any(k in low for k in list_kartu)
    missing = []
    if not has_kartu: missing.append("kartu")
    if not has_kuota: missing.append("kuota (GB)")
    if not has_masa: missing.append("masa aktif")
    return len(missing)==0, missing

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("halo bos 𖹭 bot siap")
        return
    msg = """halo kakak 𖹭
selamat datang di moury tokki

mau isi kuota apa hari ini?
isi format di bawah ini ya kak.

— FORMAT ORDER —
produk :
tujuan :
choice : langsung/rekber @rekberfamous
payment :

pricelist : t.me/kuotar/102

— contoh —
produk : by.u 1GB 1 tahun
tujuan : 08xxxxxxxxxx
choice : langsung
payment : qris"""
    await update.message.reply_text(msg)

async def handle_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.message.text and update.message.text.startswith("/"): return
    text = update.message.text
    low = text.lower()
    existing_key = None
    for k,v in order_map.items():
        if v["buyer_id"] == update.effective_chat.id and "new_price" in v:
            existing_key = k
            break
    if existing_key:
        if "lanjut" in low and "tidak" not in low:
            sent = await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ BUYER MAU LANJUT\n{order_map[existing_key]['buyer_text']}\nHarga baru: {order_map[existing_key]['new_price']}")
            order_map[sent.message_id] = order_map.pop(existing_key)
            await update.message.reply_text("siap kak 𖹭")
            return
        if "tidak jadi" in low or "gak jadi" in low:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="oke kak terimakasih ya 𖹭\nditunggu next order nya kak 🐇🪽")
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ BUYER GAK JADI\n{order_map[existing_key]['buyer_text']}")
            del order_map[existing_key]
            return
    produk = get_field(text, "produk")
    tujuan = get_field(text, "tujuan")
    choice = get_field(text, "choice")
    payment = get_field(text, "payment")
    if not produk or not tujuan or not choice or not payment:
        await update.message.reply_text("mohon maaf kak formatnya belum lengkap 𖹭\n\n— FORMAT ORDER —\nproduk :\ntujuan :\nchoice : langsung/rekber @rekberfamous\npayment :\n\npricelist : t.me/kuotar/102\n\n— CONTOH —\nproduk : by.u 1GB 1 tahun\ntujuan : 08xxxxxxxxxx\nchoice : langsung\npayment : QRIS")
        return
    valid, missing = is_product_valid(produk)
    if not valid:
        await update.message.reply_text(f"produknya kurang lengkap kak 𖹭\n\nKurang : {', '.join(missing)}\nwajib ada kartu + kuota + masa aktif ya.\n\nsalah : axis\nbenar : axis 1GB 1 tahun \n\ntolong perbaiki lagi ya kak 🐇🪽")
        return
    last_order_by_user[update.effective_chat.id] = text
    sent = await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 ORDER BARU\n\n{text}")
    order_map[sent.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": text}
    await update.message.reply_text("diterima kak 𖹭 admin akan segera cek ya")

async def handle_bukti_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if not update.message.photo: return
    user = update.effective_user
    last_text = last_order_by_user.get(update.effective_chat.id, "order ga kecatet")
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 BUKTI TF MASUK\n\nDari: @{user.username} | ID: {user.id}\n\n{last_text}")
        await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception as e:
        print(f"gagal notif bukti: {e}")
    await update.message.reply_text("bukti diterima kak, mohon tunggu konfirmasi admin ya 𖹭")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID or not update.message.reply_to_message: return
    replied_id = update.message.reply_to_message.message_id
    if replied_id not in order_map: return
    data = order_map[replied_id]
    buyer_id = data["buyer_id"]
    buyer_text = data["buyer_text"]
    low = update.message.text.strip().lower()
    text = update.message.text
    if "harga terbaru" in low:
        produk_baru = get_field(text, "produk") or get_field(buyer_text, "produk")
        tujuan_baru = get_field(text, "tujuan") or get_field(buyer_text, "tujuan")
        harga_baru = format_rupiah(get_field(text, "harga terbaru"))
        data["new_price"] = harga_baru
        order_map[replied_id] = data
        await context.bot.send_message(chat_id=buyer_id, text=f"mohon maaf kak harganya sudah berubah 𖹭\n\nproduk : {produk_baru}\ntujuan : {tujuan_baru}\nharga terbaru : {harga_baru}\n\napakah mau lanjut?\n\n```\nmau lanjut\nmaaf tidak jadi\n```", parse_mode="Markdown")
        await update.message.reply_text(f"done {harga_baru}")
        return
    if any(c.isdigit() for c in low) and ":" not in text and low not in [".pay",".rekber",".p","p"]:
        harga_baru = format_rupiah(text.strip())
        data["new_price"] = harga_baru
        order_map[replied_id] = data
        await context.bot.send_message(chat_id=buyer_id, text=f"mohon maaf kak harganya sudah berubah menjadi Rp {harga_baru} apakah mau lanjut?\n\n```\nmau lanjut\nmaaf tidak jadi\n```", parse_mode="Markdown")
        await update.message.reply_text(f"done {harga_baru}")
        return
    if low in [".pay","pay",".p","p"]:
        await context.bot.send_message(chat_id=buyer_id, text=f"halo kak, pembayaran sudah masuk ya. mohon ditunggu maksimal 1 jam. jika lebih dari 1 jam belum ada kabar silahkan ke roomchat admin @cAsisten ya kak. terima kasih 🐇\n\n{buyer_text}")
        await update.message.reply_text("done.p")
        return
    if low in [".rekber","rekber"]:
        await context.bot.send_message(chat_id=buyer_id, text=f"silakan kalau mau rekber kak 𖹭\nwajib di @rekberfamous saja ya\n\nadmin menggunakan payment dana dan ini username admin yang akan masuk ke link grup yaitu @PENTINGY silakan langsung kirim link ke roomchat admin tersebut\n\n{buyer_text}")
        await update.message.reply_text("done rekber")
        del order_map[replied_id]

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    app.add_handler(MessageHandler(filters.PHOTO, handle_bukti_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buyer))
    print("bot jalan woe fix bukti +.p pendek")
    app.run_polling()

if __name__ == "__main__":
    main()
