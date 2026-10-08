import os, re, time
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

order_map = {}
last_order_by_user = {}
spam_tracker = {}
blocked_users = set()

def format_rupiah(s):
    clean = re.sub(r'[^0-9]', '', s)
    if not clean:
        return s
    try:
        return f"{int(clean):,}".replace(",", ".")
    except:
        return s

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
    return has_kartu and has_kuota and has_masa

def get_buyer_info(user):
    uname = f"@{user.username}" if user.username else "-"
    return f"{uname} | {user.first_name} | id: {user.id}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("halo bos bot siap p proses pay nominal done selesai")
        return
    msg = "halo kak selamat datang di moury tokki\n\nmau isi kuota apa hari ini\nisi format di bawah ini ya kak\n\nformat order\nproduk :\ntujuan :\nchoice : langsung atau rekber @rekberfamous\npayment :\n\npricelist : t.me/kuotar/102\n\ncontoh\nproduk : by.u 1gb 1 tahun\ntujuan : 08xxxxxxxxxx\nchoice : langsung\npayment : qris"
    await update.message.reply_text(msg)

async def handle_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.message.text and update.message.text.startswith("/"): return
    user_id = update.effective_user.id
    if user_id in blocked_users: return
    text = update.message.text or ""
    now = time.time()
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 60]
    spam_tracker[user_id].append(now)
    if len(spam_tracker[user_id]) > 7:
        blocked_users.add(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"auto block spam {get_buyer_info(update.effective_user)} text {text[:200]}")
        return
    produk = get_field(text, "produk")
    tujuan = get_field(text, "tujuan")
    choice = get_field(text, "choice")
    payment = get_field(text, "payment")
    buyer_info = get_buyer_info(update.effective_user)
    if not produk or not tujuan or not choice or not payment:
        await update.message.reply_text("mohon maaf kak formatnya belum lengkap produk tujuan choice payment")
        return
    if not is_product_valid(produk):
        await update.message.reply_text("produknya kurang lengkap kak")
        return
    last_order_by_user[update.effective_chat.id] = text
    sent = await context.bot.send_message(chat_id=ADMIN_ID, text=f"order baru buyer {buyer_info}\n\n{text}")
    order_map[sent.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": text}
    await update.message.reply_text("diterima kak admin akan segera cek ya")

async def handle_bukti_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.effective_user.id in blocked_users: return
    if not update.message.photo: return
    buyer_info = get_buyer_info(update.effective_user)
    last_text = last_order_by_user.get(update.effective_chat.id, "-")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"bukti tf masuk buyer {buyer_info}\n\n{last_text}")
    await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    await update.message.reply_text("bukti diterima kak mohon tunggu konfirmasi admin ya")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    text_raw = update.message.text or ""
    low = text_raw.strip().lower()
    if low.startswith(".unblock"):
        try:
            target_id = int(re.findall(r'\d+', text_raw)[0])
            blocked_users.discard(target_id)
            await update.message.reply_text(f"done unblock {target_id}")
        except:
            await update.message.reply_text("format unblock id")
        return
    if not update.message.reply_to_message: return
    replied_id = update.message.reply_to_message.message_id
    if replied_id not in order_map: return
    data = order_map[replied_id]
    buyer_id = data["buyer_id"]
    buyer_text = data["buyer_text"]
    if low.startswith(".pay") or low.startswith("pay"):
        sisa = low.replace(".pay","").replace("pay","").strip()
        nominal_raw = re.sub(r'[^0-9k\.]', '', sisa)
        nominal = ""
        if nominal_raw:
            if "k" in nominal_raw:
                try:
                    angka = nominal_raw.replace("k","")
                    nominal = format_rupiah(str(int(float(angka)*1000)))
                except:
                    nominal = nominal_raw
            else:
                nominal = format_rupiah(nominal_raw)
        produk_val = get_field(buyer_text, 'produk') or 'indosat 15gb 3 hari'
        tujuan_val = get_field(buyer_text, 'tujuan') or '0812345678'
        choice_val = get_field(buyer_text, 'choice') or 'langsung'
        payment_val = get_field(buyer_text, 'payment') or 'qris'
        if nominal:
            pay_text = f"halo kak untuk pembayaran cek di @nupah ya setelah transfer kirim buktinya di sini tanpa di crop edit ya\n\nnominal : rp {nominal}\n\nproduk : {produk_val}\ntujuan : {tujuan_val}\nchoice : {choice_val}\npayment : {payment_val}"
        else:
            pay_text = f"halo kak untuk pembayaran cek di @nupah ya setelah transfer kirim buktinya di sini tanpa di crop edit ya\n\nproduk : {produk_val}\ntujuan : {tujuan_val}\nchoice : {choice_val}\npayment : {payment_val}"
        await context.bot.send_message(chat_id=buyer_id, text=pay_text)
        await update.message.reply_text(f"done pay {nominal}")
        return
    if low in [".p","p",".proses","proses"]:
        proses_text = "ting! pembayaran sudah masuk ya. mohon ditunggu maksimal 1 jam. jika lebih dari 1 jam belum ada kabar silahkan ke roomchat admin @cAsisten ya kak. terima kasih!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{proses_text}\n\n{buyer_text}")
        await update.message.reply_text("done p proses")
        return
    if low in [".done","done",".selesai","selesai"]:
        done_text = "the love u ordered has arrived safely\n\nterimakasih banyak sudah beli di moury tokki ya kakak! semoga kuotanya awet dan bermanfaat, kalau berkenan boleh bantu isi honest review di @komentagr yaa. ditunggu order selanjutnyaa!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{done_text}\n\n{buyer_text}")
        await update.message.reply_text("done selesai")
        del order_map[replied_id]
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    app.add_handler(MessageHandler(filters.PHOTO, handle_bukti_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buyer))
    print("bot jalan")
    app.run_polling()

if __name__ == "__main__":
    main()
