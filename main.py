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
    missing = []
    if not has_kartu: missing.append("kartu")
    if not has_kuota: missing.append("kuota (gb)")
    if not has_masa: missing.append("masa aktif")
    return len(missing)==0, missing

def get_buyer_info(user):
    uname = f"@{user.username}" if user.username else "-"
    return f"{uname} | {user.first_name} | id: {user.id}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("halo bos 𖹭 bot siap\n.p = proses\n.pay [nominal] = tagihan\n.done = selesai\n.unblock [id]")
        return
    msg = """halo kak 𖹭
selamat datang di moury tokki

mau isi kuota apa hari ini?
isi format di bawah ini ya kak.

— format order —
produk :
tujuan :
choice : langsung/rekber @rekberfamous
payment :

pricelist : t.me/kuotar/102

— contoh —
produk : by.u 1gb 1 tahun
tujuan : 08xxxxxxxxxx
choice : langsung
payment : qris"""
    await update.message.reply_text(msg)

async def handle_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.message.text and update.message.text.startswith("/"): return
    user_id = update.effective_user.id
    if user_id in blocked_users:
        return
    text = update.message.text or ""
    low = text.lower()
    now = time.time()
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 60]
    spam_tracker[user_id].append(now)
    if len(spam_tracker[user_id]) > 7:
        blocked_users.add(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚫 auto block spam woe!\n\n{get_buyer_info(update.effective_user)}\nspam {len(spam_tracker[user_id])}x dalam 1 menit\n\ntext terakhir: {text[:200]}")
        await update.message.reply_text("maaf kak terdeteksi spam, kamu di blokir sementara. hubungi @cAsisten jika ada kesalahan.")
        return

    existing_key = None
    for k,v in order_map.items():
        if v["buyer_id"] == update.effective_chat.id and "new_price" in v:
            existing_key = k
            break
    if existing_key:
        if "lanjut" in low and "tidak" not in low:
            sent = await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ buyer mau lanjut\n dari: {get_buyer_info(update.effective_user)}\n{order_map[existing_key]['buyer_text']}\n harga baru: {order_map[existing_key]['new_price']}")
            order_map[sent.message_id] = order_map.pop(existing_key)
            await update.message.reply_text("siap kak 𖹭")
            return
        if "tidak jadi" in low or "gak jadi" in low:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="oke kak terimakasih ya 𖹭\nditunggu next order nya kak.")
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ buyer gak jadi\n dari: {get_buyer_info(update.effective_user)}\n{order_map[existing_key]['buyer_text']}")
            del order_map[existing_key]
            return

    produk = get_field(text, "produk")
    tujuan = get_field(text, "tujuan")
    choice = get_field(text, "choice")
    payment = get_field(text, "payment")
    buyer_info = get_buyer_info(update.effective_user)

    if not produk or not tujuan or not choice or not payment:
        if text.count(":") < 2:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ iseng / format ngaco\n dari: {buyer_info}\n text: {text[:300]}")
        await update.message.reply_text("mohon maaf kak formatnya belum lengkap 𖹭\n\n— format order —\nproduk :\ntujuan :\nchoice : langsung/rekber @rekberfamous\npayment :\n\npricelist : t.me/kuotar/102")
        return

    valid, missing = is_product_valid(produk)
    if not valid:
        await update.message.reply_text(f"produknya kurang lengkap kak 𖹭\n\nkurang : {', '.join(missing)}")
        return

    last_order_by_user[update.effective_chat.id] = text
    sent = await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 order baru\n\n👤 buyer: {buyer_info}\n\n{text}")
    order_map[sent.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": text, "buyer_info": buyer_info}
    await update.message.reply_text("diterima kak 𖹭 admin akan segera cek ya")

async def handle_bukti_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.effective_user.id in blocked_users: return
    if not update.message.photo: return
    user = update.effective_user
    last_text = last_order_by_user.get(update.effective_chat.id, "order ga kecatet")
    buyer_info = get_buyer_info(user)
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 bukti tf masuk\n\n👤 buyer: {buyer_info}\n\n{last_text}")
        await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception as e:
        print(f"gagal notif bukti: {e}")
    await update.message.reply_text("bukti diterima kak, mohon tunggu konfirmasi admin ya 𖹭")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    text_raw = update.message.text or ""
    low = text_raw.strip().lower()

    if low.startswith(".unblock"):
        try:
            target_id = int(re.findall(r'\d+', text_raw)[0])
            if target_id in blocked_users:
                blocked_users.remove(target_id)
                await update.message.reply_text(f"done unblock {target_id}")
            else:
                await update.message.reply_text(f"{target_id} ga ke blokir woe")
        except:
            await update.message.reply_text("format:.unblock [id]")
        return

    if not update.message.reply_to_message: return
    replied_id = update.message.reply_to_message.message_id
    if replied_id not in order_map: return

    data = order_map[replied_id]
    buyer_id = data["buyer_id"]
    buyer_text = data["buyer_text"]

    #.pay dengan nominal
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
            pay_text = f"""halo kak 𖹭
untuk pembayaran cek di @nupah ya.
setelah transfer kirim buktinya di sini tanpa di crop/edit ya

nominal : rp {nominal}

produk : {produk_val}
tujuan : {tujuan_val}
choice : {choice_val}
payment : {payment_val}"""
        else:
            pay_text = f"""halo kak 𖹭
untuk pembayaran cek di @nupah ya.
setelah transfer kirim buktinya di sini tanpa di crop/edit yay!

        await context.bot.send_message(chat_id=buyer_id, text=pay_text)
        await update.message.reply_text(f"done pay {nominal if nominal else ''}")
        return

    #.p = proses
    if low in [".p","p",".proses","proses","process",".process"]:
        proses_text = """ting!, pembayaran sudah masuk ya. mohon ditunggu maksimal 1 jam. jika lebih dari 1 jam belum ada kabar silahkan ke roomchat admin @cAsisten ya kak. terima kasih!"""
        await context.bot.send_message(chat_id=buyer_id, text=f"{proses_text}\n\n{buyer_text}")
        await update.message.reply_text("done p proses")
        return

    #.done = selesai
        if low in [".done","done",".selesai","selesai"]:
        done_text = "the love u ordered has arrived safely\n\nterimakasih banyak sudah beli di moury tokki ya kakak! semoga kuotanya awet dan bermanfaat, kalau berkenan boleh bantu isi honest review di @komentagr yaa. ditunggu order selanjutnyaa!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{done_text}\n\n{buyer_text}")
        await update.message.reply_text("done selesai")
        del order_map[replied_id]
        return

    # harga terbaru kalo admin ketik angka doang / "harga terbaru :"
    if "harga terbaru" in low:
        produk_baru = get_field(text_raw, "produk") or get_field(buyer_text, "produk")
        tujuan_baru = get_field(text_raw, "tujuan") or get_field(buyer_text, "tujuan")
        harga_baru = format_rupiah(get_field(text_raw, "harga terbaru"))
        data["new_price"] = harga_baru
        order_map[replied_id] = data
        await context.bot.send_message(chat_id=buyer_id, text=f"mohon maaf kak harganya sudah berubah 𖹭\n\nproduk : {produk_baru}\ntujuan : {tujuan_baru}\nharga terbaru : {harga_baru}\n\napakah mau lanjut?\n\n```\nmau lanjut\nmaaf tidak jadi\n```", parse_mode="Markdown")
        await update.message.reply_text(f"done {harga_baru}")
        return

    if any(c.isdigit() for c in low) and ":" not in text_raw and low not in [".pay",".rekber",".p","p",".block","block",".done"]:
        harga_baru = format_rupiah(text_raw.strip())
        data["new_price"] = harga_baru
        order_map[replied_id] = data
        await context.bot.send_message(chat_id=buyer_id, text=f"mohon maaf kak harganya sudah berubah menjadi rp {harga_baru} apakah mau lanjut?\n\n```\nmau lanjut\nmaaf tidak jadi\n```", parse_mode="Markdown")
        await update.message.reply_text(f"done {harga_baru}")
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    app.add_handler(MessageHandler(filters.PHOTO, handle_bukti_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buyer))
    print("bot jalan woe full version")
    app.run_polling()

if __name__ == "__main__":
    main()
