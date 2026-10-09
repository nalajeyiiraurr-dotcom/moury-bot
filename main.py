import os, re, time, pytz
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

order_map = {}
last_order_by_user = {}
spam_tracker = {}
blocked_users = set()
stok_map = {}

WIB = pytz.timezone("Asia/Jakarta")
JAM_TUTUP_MULAI = 21
JAM_TUTUP_SELESAI = 9

def format_rupiah(s):
    clean = re.sub(r'[^0-9]', '', s)
    if not clean: return s
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
    return has_kartu and has_kuota and has_masa

def get_buyer_info(user):
    uname = f"@{user.username}" if user.username else "-"
    return f"{uname} | {user.first_name} | id: {user.id}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("halo bos bot siap:.p.pay.rekber.done.unblock.cek dan reply angka = harga berubah")
        return
    keyboard = [
        [InlineKeyboardButton("⚠️ WAJIB BACA SEBELUM ORDER", url="https://t.me/exprovi/38")],
        [InlineKeyboardButton("Kuota XL", url="https://t.me/kuotar/6"),
         InlineKeyboardButton("Kuota Axis", url="https://t.me/kuotar/12")],
        [InlineKeyboardButton("Kuota Indosat/IM3", url="https://t.me/kuotar/19"),
         InlineKeyboardButton("Kuota Three/3", url="https://t.me/kuotar/21")],
        [InlineKeyboardButton("Kuota Telkomsel", url="https://t.me/kuotar/23"),
         InlineKeyboardButton("Kuota Smartfren", url="https://t.me/kuotar/25")],
        [InlineKeyboardButton("Kuota By.U", url="https://t.me/kuotar/27"),
         InlineKeyboardButton("Pulsa", url="https://t.me/kuotar/41")],
        [InlineKeyboardButton("⚡ Token Listrik", url="https://t.me/kuotar/50"),
         InlineKeyboardButton("⏰ Masa Aktif Kartu", url="https://t.me/kuotar/97")],
        [InlineKeyboardButton("📝 Format Order", url="https://t.me/exprovi/46")],
        [InlineKeyboardButton("👩🏻‍💻 CS t.me/cAsisten", url="https://t.me/cAsisten")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = """h-hiluuu kak selamat datang di moury tokki 𖹭

mau beli apa hari ini?

pricelist lengkap ada di tombol bawah ya kak, tinggal klik aja sesuai kebutuhan ✨

jangan lupa baca WAJIB BACA SEBELUM ORDER dulu ya biar prosesnya lancar 𖹭

terimakasih udah mampir ke moury tokki!"""
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return
    if update.message.text and update.message.text.startswith("/"): return
    user_id = update.effective_user.id
    if user_id in blocked_users: return
    text = update.message.text or ""
    now = time.time()
    if user_id not in spam_tracker: spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 60]
    spam_tracker[user_id].append(now)
    if len(spam_tracker[user_id]) > 7:
        blocked_users.add(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"spam detected auto block 5 menit buyer {get_buyer_info(update.effective_user)}")
        await update.message.reply_text("halo kak mohon maaf kamu terdeteksi spam karena mengirim pesan terlalu cepat yaa, chat kamu dijeda dulu selama 5 menit ya kak, setelah 5 menit boleh chat lagi ya, terima kasih banyak ya kakak!")
        async def unblock_job(context):
            blocked_users.discard(user_id)
            spam_tracker.pop(user_id, None)
        context.job_queue.run_once(unblock_job, 300)
        return

    # --- JAM TUTUP 9 MALAM - 7 PAGI (FIX PUNYA KAKAK) ---
    now_wib = datetime.now(WIB)
    if now_wib.hour >= JAM_TUTUP_MULAI or now_wib.hour < JAM_TUTUP_SELESAI:
        await update.message.reply_text(
            "halo kak selamat malam 𖹭\n\n"
            "mohon maaf toko sedang tutup jam 9 malam - 9 pagi WIB\n\n"
            "silahkan kirim ulang format nya pas jam buka ya kakk\n\n"
            "makasih banyak ya kak!"
        )
        return

    # --- AUTO JAWAB STOK ---
    text_low = text.lower()
    is_nanya_stok = any(k in text_low for k in ["stok", "ready", "ada gak", "adakah", "tersedia"])
    if is_nanya_stok and not get_field(text, "produk"):
        for produk_key, status in stok_map.items():
            if produk_key in text_low:
                if status == "habis":
                    await update.message.reply_text(f"mohon maaf kak untuk {produk_key} sedang habis ya 𖹭 silahkan cek produk lain di @kuotar yap!")
                else:
                    await update.message.reply_text(f"ada kak ready ya untuk {produk_key} 𖹭 silahkan langsung kirim format ordernya ya kak!")
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

    if low.startswith(".setstok"):
        isi = text_raw.replace(".setstok","").strip().lower()
        if "habis" in isi:
            produk_key = isi.replace("habis","").strip()
            stok_map[produk_key] = "habis"
            await update.message.reply_text(f"done stok {produk_key} = HABIS ❌")
        elif "ada" in isi or "ready" in isi:
            produk_key = isi.replace("ada","").replace("ready","").strip()
            stok_map[produk_key] = "ada"
            await update.message.reply_text(f"done stok {produk_key} = ADA ✅")
        else:
            await update.message.reply_text("format:.setstok [nama produk] habis / ada\ncontoh:.setstok xl 100gb habis")
        return

    if low.startswith(".stok"):
        if not stok_map:
            await update.message.reply_text("stok kosong, set dulu pakai.setstok")
        else:
            teks = "📦 LIST STOK SAAT INI 𖹭\n\n"
            for k,v in stok_map.items():
                icon = "✅" if v=="ada" else "❌"
                teks += f"{icon} {k} : {v}\n"
            await update.message.reply_text(teks)
        return

    if low.startswith(".unblock"):
        try:
            target_id = int(re.findall(r'\d+', text_raw)[0])
            blocked_users.discard(target_id)
            spam_tracker.pop(target_id, None)
            await update.message.reply_text(f"done unblock {target_id}")
        except:
            await update.message.reply_text("format:.unblock id")
        return

    if not update.message.reply_to_message: return
    replied_id = update.message.reply_to_message.message_id
    if replied_id not in order_map: return
    data = order_map[replied_id]
    buyer_id = data["buyer_id"]
    buyer_text = data["buyer_text"]

    if low.startswith(".cek") or low == "cek":
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        teks_tenggang = f"""🚨 prittt prittt! kartumu sedang masa tenggang.

silahkan isi pulsa atau masa aktif terlebih dahulu agar nomor kembali aktif. kalau ditanya *"jadi gabisa?" atau "jadi gimana?"*, jawabannya sudah ada di atas ya kak: *aktifkan nomor terlebih dahulu!.*

📭 kalau mau isi pulsa atau masa aktif terlebih dahulu, saya juga menyediakan yaa. boleh cek di sini kalau berminat: [ t.me/kuotar/102 ] <3

━━━━━━━━━━━━━━
nomor tujuan: {tujuan_val}
apakah mau tetap lanjut atau tidak jadi kak?"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Mau Lanjut (Aktifkan Dulu)", callback_data=f"cek_lanjut_{replied_id}"),
             InlineKeyboardButton("❌ Maaf Tidak Jadi", callback_data=f"cek_batal_{replied_id}")]
        ])
        await context.bot.send_message(chat_id=buyer_id, text=teks_tenggang, reply_markup=keyboard)
        await update.message.reply_text(f"done cek tenggang ke {tujuan_val}")
        return

    if low.startswith(".pay") or low.startswith("pay"):
        sisa = low.replace(".pay","").replace("pay","").strip()
        nominal_raw = re.sub(r'[^0-9k\.]', '', sisa)
        nominal = ""
        if nominal_raw:
            if "k" in nominal_raw:
                try:
                    angka = nominal_raw.replace("k","")
                    nominal = format_rupiah(str(int(float(angka)*1000)))
                except: nominal = nominal_raw
            else: nominal = format_rupiah(nominal_raw)
        produk_val = get_field(buyer_text, 'produk') or '-'
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        choice_val = get_field(buyer_text, 'choice') or 'langsung'
        payment_val = get_field(buyer_text, 'payment') or 'qris'
        if nominal:
            pay_text = f"halo kak untuk pembayaran cek di @nupah ya setelah transfer kirim buktinya di sini tanpa di crop edit ya\n\nnominal : rp {nominal}\n\nproduk : {produk_val}\ntujuan : {tujuan_val}\nchoice : {choice_val}\npayment : {payment_val}"
        else:
            pay_text = f"halo kak untuk pembayaran cek di @nupah ya setelah transfer kirim buktinya di sini tanpa di crop edit ya\n\nproduk : {produk_val}\ntujuan : {tujuan_val}\nchoice : {choice_val}\npayment : {payment_val}"
        await context.bot.send_message(chat_id=buyer_id, text=pay_text)
        await update.message.reply_text(f"done pay {nominal}")
        return

    if low in [".rekber","rekber",".rekberfamous","rekberfamous"]:
        produk_val = get_field(buyer_text, 'produk') or '-'
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        rekber_text = f"silahkan kalau mau rekber kak 𖹭\nwajib di @rekberfamous saja ya\n\nadmin menggunakan payment dana dan ini username admin yang akan masuk ke link grup yaitu @pentingY silahkan langsung kirim link grup ke roomchat admin tersebut.\n\nproduk : {produk_val}\ntujuan : {tujuan_val}"
        await context.bot.send_message(chat_id=buyer_id, text=f"{rekber_text}\n\n{buyer_text}")
        await update.message.reply_text("done rekber")
        return

    if low in [".p","p",".proses","proses",".acc","acc"]:
        proses_text = "ting! pembayaran sudah masuk ya. mohon ditunggu maksimal 1 jam. jika lebih dari 1 jam belum ada kabar silahkan ke roomchat admin @cAsisten ya kak. terima kasih!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{proses_text}\n\n{buyer_text}")
        await update.message.reply_text("done p proses")
        return

    if low in [".done","done",".selesai","selesai"]:
        done_text = "the love u ordered has arrived safely\n\nterimakasih banyak sudah beli di moury tokki ya kakak! semoga kuotanya awet dan bermanfaat, kalau berkenan boleh bantu isi honest review di @komentagr yaa. ditunggu order selanjutnyaa!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{done_text}\n\n{buyer_text}")
        await update.message.reply_text("done selesai")
        if replied_id in order_map: del order_map[replied_id]
        return

    clean_text = text_raw.strip()
    if re.fullmatch(r'[\d\.\,\s kK]+', clean_text) and re.search(r'\d', clean_text):
        nominal_raw = re.sub(r'[^0-9k\.]', '', clean_text.lower())
        nominal = ""
        if nominal_raw:
            if "k" in nominal_raw:
                try:
                    angka = nominal_raw.replace("k","")
                    nominal = format_rupiah(str(int(float(angka)*1000)))
                except: nominal = nominal_raw
            else:
                nominal = format_rupiah(nominal_raw)
        else:
            nominal = clean_text
        produk_val = get_field(buyer_text, 'produk') or '-'
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        teks_harga = f"""halo kak mohon maaf harga berubah ya 𖹭

untuk produk: {produk_val}
tujuan : {tujuan_val}

harga terbarunya jadi Rp {nominal} ya kak

apakah mau lanjut atau tidak jadi kak?"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Mau Lanjut", callback_data=f"harga_lanjut_{replied_id}"),
             InlineKeyboardButton("❌ Maaf Tidak Jadi", callback_data=f"harga_batal_{replied_id}")]
        ])
        await context.bot.send_message(chat_id=buyer_id, text=teks_harga, reply_markup=keyboard)
        await update.message.reply_text(f"done harga berubah {nominal} ke {tujuan_val}")
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    try:
        prefix, action, order_msg_id = data.split("_", 2)
        order_msg_id = int(order_msg_id)
    except: return
    if order_msg_id not in order_map:
        await query.edit_message_text("order sudah tidak tersedia kak")
        return
    order_data = order_map[order_msg_id]
    buyer_text = order_data["buyer_text"]
    buyer_id = order_data["buyer_id"]
    if user_id!= buyer_id and user_id!= ADMIN_ID: return
    produk_val = get_field(buyer_text, 'produk') or '-'
    tujuan_val = get_field(buyer_text, 'tujuan') or '-'

    if prefix == "harga":
        if action == "lanjut":
            teks = f"""siap kak 𖹭

dicatat ya mau tetap lanjut dengan harga terbaru ya kak.

produk : {produk_val}
tujuan : {tujuan_val}

silahkan tunggu instruksi pembayaran dari admin ya kak!"""
            await query.edit_message_text(teks)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ BUYER MAU LANJUT HARGA BARU\nTujuan: {tujuan_val}\n{buyer_text}\n-> tinggal.pay kak")
        else:
            teks = f"""oke kak dicatat ya tidak jadi 𖹭

order untuk {tujuan_val} dibatalkan karena harga berubah ya kak. makasih banyak ya 🙏"""
            await query.edit_message_text(teks)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ BUYER BATAL HARGA BERUBAH\n{buyer_text}")
            if order_msg_id in order_map: del order_map[order_msg_id]

    elif prefix == "cek":
        if action == "lanjut":
            teks = f"""siap kak 𖹭

dicatat ya mau lanjut setelah aktifkan masa aktif terlebih dahulu ya kak.

silahkan isi pulsa / masa aktif dulu untuk nomor {tujuan_val} ya kak, kalau sudah aktif silahkan kirim format ulang ya biar bisa langsung diproses.

            await query.edit_message_text(teks)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ BUYER MAU AKTIFKAN MASA AKTIF DULU\nTujuan: {tujuan_val}\n{buyer_text}")
        else:
            teks = f"""oke kak dicatat ya tidak jadi 𖹭

order untuk nomor {tujuan_val} dibatalkan ya kak. makasih banyak!"""
            await query.edit_message_text(teks)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ BUYER BATAL KARENA TENGGANG\n{buyer_text}")
            if order_msg_id in order_map: del order_map[order_msg_id]

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    app.add_handler(MessageHandler(filters.PHOTO, handle_bukti_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buyer))
    print("bot jalan")
    app.run_polling()

if __name__ == "__main__":
    main()
