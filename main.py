import os, re, time
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_RAW = os.getenv("ADMIN_ID", "0")
ADMIN_IDS = set()
for x in ADMIN_RAW.replace(" ", "").split(","):
    if x.strip().isdigit():
        ADMIN_IDS.add(int(x.strip()))
ADMIN_IDS.add(8479422708)

def is_admin(uid):
    return uid in ADMIN_IDS

order_map = {}
last_order_by_user = {}
spam_tracker = {}
blocked_users = set()
stok_map = {}
blacklist_map = {}
all_buyers = set()
libur_mode = False
libur_pesan = ""
WIB = timezone(timedelta(hours=7))
JAM_TUTUP_MULAI = 21
JAM_TUTUP_SELESAI = 9

def detect_operator(nomor):
    clean = re.sub(r'[^0-9]', '', nomor)
    if clean.startswith("62"):
        clean = "0" + clean[2:]
    if any(clean.startswith(p) for p in ["0811","0812","0813","0821","0822","0823","0852","0853","0851"]):
        return "Telkomsel"
    if any(clean.startswith(p) for p in ["0817","0818","0819","0859","0877","0878"]):
        return "XL"
    if any(clean.startswith(p) for p in ["0831","0832","0833","0838"]):
        return "Axis / XL"
    if any(clean.startswith(p) for p in ["0814","0815","0816","0855","0856","0857","0858"]):
        return "Indosat/IM3"
    if any(clean.startswith(p) for p in ["0895","0896","0897","0898","0899"]):
        return "Three/3"
    if any(clean.startswith(p) for p in ["0881","0882","0883","0884","0885","0886","0887","0888","0889"]):
        return "Smartfren"
    return "Tidak terdeteksi"

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
    if any(k in low for k in ["pulsa", "token", "listrik", "pln", "masa aktif"]):
        return True
    has_kuota = bool(re.search(r'\d+(\.\d+)?\s*(gb|mb|giga)', low))
    has_masa = bool(re.search(r'\d*\s*(hari|tahun|bulan|minggu)', low))
    list_kartu = ["axis", "by.u", "byu", "indosat", "isat", "telkomsel", "tsel", "xl", "smartfren", "smart", "fren", "tri", "three", "3", "by u"]
    has_kartu = any(k in low for k in list_kartu)
    return has_kartu and has_kuota and has_masa

def get_buyer_info(user):
    uname = f"@{user.username}" if user.username else "-"
    return f"{uname} | {user.first_name} | id: {user.id}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text("halo bos bot siap\n.p.pay.rekber.done.cek [reply]\n.setstok xl 100gb gangguan |.stok\n.bc [promo] |.bl [nomor] alasan |.unbl |.listbl\n.libur [pesan] |.buka\nreply angka = harga berubah")
        return
    keyboard = [
        [InlineKeyboardButton("⚠️ WAJIB BACA SEBELUM ORDER", url="https://t.me/exprovi/38")],
        [InlineKeyboardButton("Kuota XL", url="https://t.me/kuotar/6"), InlineKeyboardButton("Kuota Axis", url="https://t.me/kuotar/12")],
        [InlineKeyboardButton("Kuota Indosat/IM3", url="https://t.me/kuotar/19"), InlineKeyboardButton("Kuota Three/3", url="https://t.me/kuotar/21")],
        [InlineKeyboardButton("Kuota Telkomsel", url="https://t.me/kuotar/23"), InlineKeyboardButton("Kuota Smartfren", url="https://t.me/kuotar/25")],
        [InlineKeyboardButton("Kuota By.U", url="https://t.me/kuotar/27"), InlineKeyboardButton("Pulsa", url="https://t.me/kuotar/41")],
        [InlineKeyboardButton("⚡ Token Listrik", url="https://t.me/kuotar/50"), InlineKeyboardButton("⏰ Masa Aktif Kartu", url="https://t.me/kuotar/97")],
        [InlineKeyboardButton("📝 Format Order", url="https://t.me/exprovi/46")],
        [InlineKeyboardButton("👩🏻‍💻 CS", url="https://t.me/cAsisten")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "h-hiluuu kak selamat datang di moury tokki 𖹭\n\nmau beli apa hari ini?\n\npricelist lengkap ada di tombol bawah ya kak, tinggal klik aja sesuai kebutuhan ✨\n\njangan lupa baca WAJIB BACA SEBELUM ORDER dulu ya biar prosesnya lancar 𖹭\n\nterimakasih udah mampir ke moury tokki!"
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global libur_mode, libur_pesan
    if is_admin(update.effective_user.id):
        return
    if update.message.text and update.message.text.startswith("/"):
        return
    user_id = update.effective_user.id
    if user_id in blocked_users:
        return
    text = update.message.text or ""
    all_buyers.add(update.effective_chat.id)
    low_text = text.lower()
    if any(k in low_text for k in ["sudah review", "udah review", "sudah rnk", "udah rnk", "done rnk", "done review"]):
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=f"⭐ BUYER SUDAH REVIEW / RNK ⭐\nBuyer: {get_buyer_info(update.effective_user)}\n\n{text}")
            except:
                pass
        await update.message.reply_text("wah makasih banyak kak sudah isi review nya di @komentagr yaa! berkah selalu kak 𖹭 ditunggu order selanjutnya!")
        return
    if libur_mode:
        await update.message.reply_text(f"halo kak mohon maaf toko sedang libur 𖹭\n\n{libur_pesan}\n\nsilahkan chat lagi nanti setelah toko buka ya kak! makasih banyak 🙏")
        return
    now = time.time()
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 60]
    spam_tracker[user_id].append(now)
    if len(spam_tracker[user_id]) > 7:
        blocked_users.add(user_id)
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=f"spam detected auto block 5 menit buyer {get_buyer_info(update.effective_user)}")
            except:
                pass
        await update.message.reply_text("halo kak mohon maaf kamu terdeteksi spam karena mengirim pesan terlalu cepat yaa, chat kamu dijeda dulu selama 5 menit ya kak!")
        async def unblock_job(ctx):
            blocked_users.discard(user_id)
            spam_tracker.pop(user_id, None)
        context.job_queue.run_once(unblock_job, 300)
        return
    now_wib = datetime.now(WIB)
    if now_wib.hour >= JAM_TUTUP_MULAI or now_wib.hour < JAM_TUTUP_SELESAI:
        await update.message.reply_text("halo kak selamat malam 𖹭\n\nmohon maaf toko sedang tutup jam 9 malam - 9 pagi WIB\n\nsilahkan kirim ulang format nya pas jam buka ya kakk\n\nkalau butuh yang fast respon bisa langsung kirim format nya ke @pentingY ya kak, admin fast standby di sana 24 jam 𖹭\n\nmakasih banyak ya kak!")
        return
    is_nanya_stok = any(k in low_text for k in ["stok", "ready", "ada gak", "adakah", "tersedia"])
    if is_nanya_stok and not get_field(text, "produk"):
        for produk_key, status in stok_map.items():
            if produk_key in low_text:
                if status in ["habis", "gangguan"]:
                    await update.message.reply_text(f"mohon maaf kak untuk {produk_key} sedang gangguan ya 𖹭 silahkan cek produk lain di @kuotar yap!")
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
    for produk_key, status in stok_map.items():
        if produk_key in produk.lower() and status in ["habis", "gangguan"]:
            await update.message.reply_text(f"mohon maaf kak untuk {produk} sedang gangguan ya 𖹭 silahkan cek produk lain di @kuotar yap!")
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=aid, text=f"⚠️ ORDER DITOLAK OTOMATIS - GANGGUAN\nProduk: {produk}\nKey: {produk_key}\nBuyer: {buyer_info}\n{text}")
                except:
                    pass
            return
    clean_tujuan = re.sub(r'[^0-9]', '', tujuan)
    if clean_tujuan in blacklist_map:
        alasan = blacklist_map[clean_tujuan]
        await update.message.reply_text(f"mohon maaf kak nomor {tujuan} terblacklist karena {alasan} ya 𖹭 silahkan hubungi @cAsisten jika merasa ada kesalahan")
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=f"⚠️ BLACKLIST ORDER DITOLAK\nNomor: {tujuan} ({alasan})\nBuyer: {buyer_info}\n{text}")
            except:
                pass
        return
    last_order_by_user[update.effective_chat.id] = text
    operator = detect_operator(tujuan)
    operator_note = f"\n🤖 Auto Deteksi: {operator}" if operator!= "Tidak terdeteksi" else ""
    for aid in ADMIN_IDS:
        try:
            sent = await context.bot.send_message(chat_id=aid, text=f"order baru buyer {buyer_info}{operator_note}\n\n{text}")
            order_map[sent.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": text}
        except:
            pass
    if operator!= "Tidak terdeteksi":
        await update.message.reply_text(f"diterima kak admin akan segera cek ya\n\nterdeteksi operator: {operator} 𖹭")
    else:
        await update.message.reply_text("diterima kak admin akan segera cek ya")

async def handle_bukti_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        return
    if update.effective_user.id in blocked_users:
        return
    if not update.message.photo:
        return
    buyer_info = get_buyer_info(update.effective_user)
    last_text = last_order_by_user.get(update.effective_chat.id, "-")
    all_buyers.add(update.effective_chat.id)
    for aid in ADMIN_IDS:
        try:
            sent1 = await context.bot.send_message(chat_id=aid, text=f"bukti tf masuk buyer {buyer_info}\n\n{last_text}")
            order_map[sent1.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": last_text}
            sent2 = await context.bot.forward_message(chat_id=aid, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
            order_map[sent2.message_id] = {"buyer_id": update.effective_chat.id, "buyer_text": last_text}
        except:
            pass
    await update.message.reply_text("bukti diterima kak mohon tunggu konfirmasi admin ya")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global libur_mode, libur_pesan
    if not is_admin(update.effective_user.id):
        return
    text_raw = update.message.text or update.message.caption or ""
    low = text_raw.strip().lower()
    if low.startswith(".bc"):
        pesan_bc = text_raw[3:].strip()
        if not pesan_bc:
            await update.message.reply_text("format:.bc [pesan promo]")
            return
        count = 0
        for buyer_id in list(all_buyers):
            try:
                await context.bot.send_message(chat_id=buyer_id, text=f"📢 INFO PROMO MOURY TOKKI 𖹭\n\n{pesan_bc}\n\ncek pricelist: @kuotar")
                count += 1
            except:
                pass
        await update.message.reply_text(f"done broadcast ke {count} buyer ✅")
        return
    if low.startswith(".bl "):
        parts = text_raw[3:].strip().split(" ",1)
        nomor = re.sub(r'[^0-9]', '', parts[0])
        alasan = parts[1] if len(parts) > 1 else "tanpa alasan"
        blacklist_map[nomor] = alasan
        await update.message.reply_text(f"done blacklist {nomor} alasan: {alasan} ✅")
        return
    if low.startswith(".unbl"):
        nomor = re.sub(r'[^0-9]', '', text_raw.replace(".unbl","").strip())
        if nomor in blacklist_map:
            del blacklist_map[nomor]
        await update.message.reply_text(f"done unblacklist {nomor} ✅")
        return
    if low.startswith(".listbl"):
        if not blacklist_map:
            await update.message.reply_text("blacklist kosong")
        else:
            teks = "🚫 LIST BLACKLIST 𖹭\n\n"
            for n,a in blacklist_map.items():
                teks += f"{n} : {a}\n"
            await update.message.reply_text(teks)
        return
    if low.startswith(".libur"):
        pesan = text_raw[6:].strip()
        if not pesan:
            pesan = "toko sedang libur ya kak"
        libur_mode = True
        libur_pesan = pesan
        await update.message.reply_text(f"done LIBUR ✅ {pesan}")
        return
    if low.startswith(".buka"):
        libur_mode = False
        libur_pesan = ""
        await update.message.reply_text("done BUKA ✅")
        return
    if low.startswith(".setstok"):
        isi = text_raw.replace(".setstok","").strip().lower()
        if "habis" in isi or "gangguan" in isi:
            produk_key = isi.replace("habis","").replace("gangguan","").strip()
            stok_map[produk_key] = "gangguan"
            await update.message.reply_text(f"done stok {produk_key} = GANGGUAN ❌\nbuyer akan dapat pesan 'sedang gangguan'")
        elif "ada" in isi or "ready" in isi:
            produk_key = isi.replace("ada","").replace("ready","").strip()
            stok_map[produk_key] = "ada"
            await update.message.reply_text(f"done stok {produk_key} = ADA ✅")
        return
    if low.startswith(".stok"):
        if not stok_map:
            await update.message.reply_text("stok kosong")
        else:
            teks = "📦 LIST STOK\n\n"
            for k,v in stok_map.items():
                teks += f"{k} : {v}\n"
            await update.message.reply_text(teks)
        return
    if low.startswith(".unblock"):
        try:
            target_id = int(re.findall(r'\d+', text_raw)[0])
            blocked_users.discard(target_id)
            await update.message.reply_text(f"done unblock {target_id}")
        except:
            await update.message.reply_text("format:.unblock id")
        return
    if not update.message.reply_to_message:
        return
    replied_id = update.message.reply_to_message.message_id
    if replied_id not in order_map:
        return
    data = order_map[replied_id]
    buyer_id = data["buyer_id"]
    buyer_text = data["buyer_text"]
    if low.startswith(".cek") or low == "cek":
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        teks_tenggang = f"🚨 prittt prittt! kartumu sedang masa tenggang.\n\nsilahkan isi pulsa atau masa aktif terlebih dahulu agar nomor kembali aktif.\n\n📭 kalau mau isi pulsa atau masa aktif terlebih dahulu, saya juga menyediakan yaa. boleh cek di sini: [ t.me/kuotar/102 ] <3\n\n━━━━━━━━━━━━━━\nnomor tujuan: {tujuan_val}\n\napakah mau tetap lanjut atau tidak jadi kak?"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Mau Lanjut", callback_data=f"cek_lanjut_{replied_id}"), InlineKeyboardButton("❌ Tidak Jadi", callback_data=f"cek_batal_{replied_id}")]])
        await context.bot.send_message(chat_id=buyer_id, text=teks_tenggang, reply_markup=keyboard)
        await update.message.reply_text(f"done cek {tujuan_val}")
        return
    if low.startswith(".pay") or low.startswith("pay"):
        sisa = low.replace(".pay","").replace("pay","").strip()
        nominal_raw = re.sub(r'[^0-9k\.]', '', sisa)
        nominal = ""
        if nominal_raw:
            if "k" in nominal_raw:
                try:
                    nominal = format_rupiah(str(int(float(nominal_raw.replace("k",""))*1000)))
                except:
                    nominal = nominal_raw
            else:
                nominal = format_rupiah(nominal_raw)
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
        rekber_text = "silahkan kalau mau rekber kak 𖹭\nwajib di @rekberfamous saja ya\n\nadmin menggunakan payment dana dan ini username admin yang akan masuk ke link grup yaitu @pentingY silahkan langsung kirim link grup ke roomchat admin tersebut."
        await context.bot.send_message(chat_id=buyer_id, text=rekber_text)
        await update.message.reply_text("done rekber")
        return
    if low in [".p","p",".proses","proses",".acc","acc"]:
        proses_text = "ting! pembayaran sudah masuk ya. mohon ditunggu maksimal 1 jam. jika lebih dari 1 jam belum ada kabar silahkan ke roomchat admin @cAsisten ya kak. terima kasih!"
        await context.bot.send_message(chat_id=buyer_id, text=f"{proses_text}\n\n{buyer_text}")
        await update.message.reply_text("done p")
        return
    if low in [".done","done",".selesai","selesai"]:
        done_text = "the love u ordered has arrived safely\n\nterimakasih banyak sudah beli di moury tokki ya kakak! semoga kuotanya awet dan bermanfaat, kalau berkenan boleh bantu isi honest review di @komentagr yaa. ditunggu order selanjutnyaa!"
        await context.bot.send_message(chat_id=buyer_id, text=done_text)
        await update.message.reply_text("done selesai - buyer sudah dikirim wording baru tanpa format")
        if replied_id in order_map:
            del order_map[replied_id]
        return
    clean_text = text_raw.strip()
    if re.fullmatch(r'[\d\.\,\s kK]+', clean_text) and re.search(r'\d', clean_text):
        nominal_raw = re.sub(r'[^0-9k\.]', '', clean_text.lower())
        if "k" in nominal_raw:
            try:
                nominal = format_rupiah(str(int(float(nominal_raw.replace("k",""))*1000)))
            except:
                nominal = nominal_raw
        else:
            nominal = format_rupiah(nominal_raw)
        produk_val = get_field(buyer_text, 'produk') or '-'
        tujuan_val = get_field(buyer_text, 'tujuan') or '-'
        teks_harga = f"halo kak mohon maaf harga berubah ya 𖹭\n\nuntuk produk: {produk_val}\ntujuan : {tujuan_val}\n\nharga terbarunya jadi Rp {nominal} ya kak\n\napakah mau lanjut atau tidak jadi kak?"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Mau Lanjut", callback_data=f"harga_lanjut_{replied_id}"), InlineKeyboardButton("❌ Tidak Jadi", callback_data=f"harga_batal_{replied_id}")]])
        await context.bot.send_message(chat_id=buyer_id, text=teks_harga, reply_markup=keyboard)
        await update.message.reply_text(f"done harga {nominal}")
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        replied_id = int(data.rsplit("_", 2)[-1])
    except:
        return
    if replied_id not in order_map:
        try:
            await query.edit_message_text("order sudah selesai ya kak 𖹭")
        except:
            pass
        return
    buyer_info = get_buyer_info(query.from_user)
    if "lanjut" in data:
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=f"✅ BUYER LANJUT {data} {buyer_info}")
            except:
                pass
        try:
            await query.edit_message_text(query.message.text + "\n\n✅ Oke kak mau lanjut ya!")
        except:
            pass
    else:
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=f"❌ BUYER BATAL {data} {buyer_info}")
            except:
                pass
        try:
            await query.edit_message_text(query.message.text + "\n\n❌ Oke tidak jadi ya!")
        except:
            pass
        if replied_id in order_map:
            del order_map[replied_id]

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN kosong")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_reply), group=0)
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_bukti_photo), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buyer), group=2)
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("Bot jalan...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
