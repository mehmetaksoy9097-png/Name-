import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
import string
import random as rnd

load_dotenv()

# ──────────────────────────────────────────────
#  CONFIG (bot_config.json > .env öncelik sırası)
# ──────────────────────────────────────────────
CONFIG_FILE = "bot_config.json"

CONFIG_KEYS = [
    ("GUILD_ID",           "int",  "0"),
    ("STAFF_ROLE_ID",      "int",  "0"),
    ("TICKET_CATEGORY_ID", "int",  "0"),
    ("VOICE_CATEGORY_ID",  "int",  "0"),
    ("LOG_CHANNEL_ID",     "int",  "0"),
    ("OPENROUTER_API_KEY", "str",  ""),
]

def load_config() -> dict:
    default = {k: (os.getenv(k) or d) for k, t, d in CONFIG_KEYS}
    if os.path.exists(CONFIG_FILE):
        try:
            saved = json.loads(open(CONFIG_FILE, "r", encoding="utf-8").read())
            for k, t, d in CONFIG_KEYS:
                if k in saved and saved[k]:
                    default[k] = saved[k]
        except:
            pass
    return default

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_cfg(key: str, typ: str = "str"):
    cfg = load_config()
    val = cfg.get(key, "0")
    if typ == "int":
        try:
            return int(val)
        except:
            return 0
    return val or ""

TOKEN              = "BURAYA_TOKEN_YAZ"  # Token buraya yaz
GUILD_ID           = get_cfg("GUILD_ID", "int")
STAFF_ROLE_ID      = get_cfg("STAFF_ROLE_ID", "int")
TICKET_CATEGORY_ID = get_cfg("TICKET_CATEGORY_ID", "int")
VOICE_CATEGORY_ID  = get_cfg("VOICE_CATEGORY_ID", "int")
LOG_CHANNEL_ID     = get_cfg("LOG_CHANNEL_ID", "int")

# ──────────────────────────────────────────────
#  EMOJİ IDLERİ (bot sunucudan çeker)
# ──────────────────────────────────────────────
ID_EMOJI_UYARI = 1500369302073905365
ID_EMOJI_GENEL = 1500121078805303447
ID_EMOJI_URUN  = 1500382470724522104
ID_EMOJI_SORU  = 1500099438838939650
ID_EMOJI_SESLI = 1501664937917808802

def e(emoji_id: int) -> Optional[discord.Emoji]:
    return bot.get_emoji(emoji_id)

DATA_FILE = "ticket_data.json"

# ──────────────────────────────────────────────
#  DATA (JSON)
# ──────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    {"id": "genel", "label": "Genel Destek",    "description": "Genel yardım ve destek için",          "placeholder": "Kategori seç...", "emoji_id": ID_EMOJI_GENEL},
    {"id": "urun",  "label": "Ürün Hizmetleri", "description": "Ürün satın alma ve teslimat için",     "placeholder": "Kategori seç...", "emoji_id": ID_EMOJI_URUN},
    {"id": "soru",  "label": "Soru Sormak",      "description": "Merak ettiğin şeyleri sor",            "placeholder": "Kategori seç...", "emoji_id": ID_EMOJI_SORU},
]

def load_data() -> dict:
    default = {"ticket_bans": {}, "ticket_counter": 0, "open_tickets": {}, "categories": DEFAULT_CATEGORIES}
    if not os.path.exists(DATA_FILE):
        return default
    try:
        content = open(DATA_FILE, "r", encoding="utf-8").read().strip()
        if not content:
            return default
        data = json.loads(content)
    except (json.JSONDecodeError, Exception):
        return default
    if "categories" not in data:
        data["categories"] = DEFAULT_CATEGORIES
        save_data(data)
    return data

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ──────────────────────────────────────────────
#  BOT SETUP
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="z!", intents=intents)

# ──────────────────────────────────────────────
#  KATEGORİ YÖNETİMİ
# ──────────────────────────────────────────────

# Modal: Kategori düzenle / yeni kategori oluştur
class KategoriModal(discord.ui.Modal):
    def __init__(self, mevcut: Optional[dict] = None):
        baslik = "Kategoriyi Düzenle" if mevcut else "Yeni Kategori Oluştur"
        super().__init__(title=baslik)
        self.mevcut = mevcut

        self.isim = discord.ui.TextInput(
            label="Kategori İsmi",
            placeholder="örn: VIP Destek",
            default=mevcut["label"] if mevcut else "",
            required=True, max_length=50
        )
        self.aciklama = discord.ui.TextInput(
            label="Açıklama",
            placeholder="Dropdown'da görünecek kısa açıklama",
            default=mevcut.get("description", "") if mevcut else "",
            required=True, max_length=100
        )
        self.placeholder = discord.ui.TextInput(
            label="Placeholder Mesajı",
            placeholder="Dropdown'ın üstündeki yazı",
            default=mevcut.get("placeholder", "Kategori seç...") if mevcut else "Kategori seç...",
            required=True, max_length=100
        )
        self.emoji_id = discord.ui.TextInput(
            label="Emoji ID",
            placeholder="örn: 1500121078805303447",
            default=str(mevcut["emoji_id"]) if mevcut and mevcut.get("emoji_id") else "",
            required=True, max_length=25
        )
        self.add_item(self.isim)
        self.add_item(self.aciklama)
        self.add_item(self.placeholder)
        self.add_item(self.emoji_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            emoji_id = int(self.emoji_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Geçersiz Emoji ID.", ephemeral=True)

        data = load_data()
        cats = data.get("categories", [])

        if self.mevcut:
            # Mevcut kategoriyi güncelle
            for cat in cats:
                if cat["id"] == self.mevcut["id"]:
                    cat["label"]       = self.isim.value.strip()
                    cat["description"] = self.aciklama.value.strip()
                    cat["placeholder"] = self.placeholder.value.strip()
                    cat["emoji_id"]    = emoji_id
                    break
            msg = f"✅ **{self.isim.value}** kategorisi güncellendi."
        else:
            # Yeni kategori oluştur
            new_id = self.isim.value.strip().lower().replace(" ", "_")[:20]
            # ID çakışması önle
            existing_ids = {c["id"] for c in cats}
            base_id = new_id
            counter = 1
            while new_id in existing_ids:
                new_id = f"{base_id}_{counter}"
                counter += 1
            cats.append({
                "id": new_id,
                "label": self.isim.value.strip(),
                "description": self.aciklama.value.strip(),
                "placeholder": self.placeholder.value.strip(),
                "emoji_id": emoji_id
            })
            msg = f"✅ **{self.isim.value}** kategorisi oluşturuldu."

        data["categories"] = cats
        save_data(data)

        embed = discord.Embed(description=msg, color=0x57F287)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Dropdown: Kategori yönetim paneli
class KategoriYonetimDropdown(discord.ui.Select):
    def __init__(self):
        data = load_data()
        cats = data.get("categories", DEFAULT_CATEGORIES)
        options = []
        for cat in cats:
            emoji = bot.get_emoji(cat["emoji_id"]) if cat.get("emoji_id") else None
            options.append(discord.SelectOption(
                label=cat["label"],
                value=f"edit_{cat['id']}",
                description=cat.get("description", ""),
                emoji=emoji
            ))
        options.append(discord.SelectOption(
            label="Yeni Kategori Oluştur",
            value="new",
            description="Yeni bir ticket kategorisi ekle",
            emoji=bot.get_emoji(1502698614055637124)
        ))
        options.append(discord.SelectOption(
            label="Kategori Sil",
            value="delete",
            description="Mevcut bir kategoriyi kaldır",
            emoji=bot.get_emoji(1502698744309878834)
        ))
        super().__init__(
            placeholder="Kategori seç veya yönet...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="kategori_yonetim_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]

        if val == "new":
            await interaction.response.send_modal(KategoriModal())

        elif val == "delete":
            data = load_data()
            cats = data.get("categories", [])
            if not cats:
                return await interaction.response.send_message("❌ Silinecek kategori yok.", ephemeral=True)
            view = KategoriSilView(cats)
            embed = discord.Embed(title="🗑️ Kategori Sil", description="Silmek istediğin kategoriyi seç:", color=0xFF4444)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif val.startswith("edit_"):
            cat_id = val[5:]
            data = load_data()
            cats = data.get("categories", [])
            mevcut = next((c for c in cats if c["id"] == cat_id), None)
            if not mevcut:
                return await interaction.response.send_message("❌ Kategori bulunamadı.", ephemeral=True)
            await interaction.response.send_modal(KategoriModal(mevcut=mevcut))


# Dropdown: Kategori sil
class KategoriSilDropdown(discord.ui.Select):
    def __init__(self, cats: list):
        options = [
            discord.SelectOption(label=cat["label"], value=cat["id"], description=cat.get("description", ""))
            for cat in cats
        ]
        super().__init__(
            placeholder="Silinecek kategoriyi seç...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="kategori_sil_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        cat_id = self.values[0]
        data = load_data()
        cats = data.get("categories", [])
        silinen = next((c for c in cats if c["id"] == cat_id), None)
        data["categories"] = [c for c in cats if c["id"] != cat_id]
        save_data(data)
        label = silinen["label"] if silinen else cat_id
        embed = discord.Embed(description=f"🗑️ **{label}** kategorisi silindi.", color=0xFF4444)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class KategoriSilView(discord.ui.View):
    def __init__(self, cats):
        super().__init__(timeout=60)
        self.add_item(KategoriSilDropdown(cats))


class KategoriYonetimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(KategoriYonetimDropdown())


class TicketDropdown(discord.ui.Select):
    def __init__(self):
        data = load_data()
        cats = data.get("categories", DEFAULT_CATEGORIES)
        placeholder = cats[0].get("placeholder", "Kategori seç...") if cats else "Kategori seç..."
        options = []
        for cat in cats:
            emoji = bot.get_emoji(cat["emoji_id"]) if cat.get("emoji_id") else None
            options.append(discord.SelectOption(
                label=cat["label"],
                value=cat["id"],
                description=cat.get("description", ""),
                emoji=emoji
            ))
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        uid = str(interaction.user.id)

        # ── Ticket ban kontrolü ──
        if uid in data["ticket_bans"]:
            ban = data["ticket_bans"][uid]
            until = ban.get("until")
            reason = ban.get("reason", "Belirtilmedi")
            expired = until != "permanent" and datetime.fromisoformat(until) <= datetime.utcnow()
            if expired:
                del data["ticket_bans"][uid]
                save_data(data)
            else:
                until_str = "Süresiz" if until == "permanent" else datetime.fromisoformat(until).strftime("%d.%m.%Y %H:%M")
                embed = discord.Embed(
                    title="🚫 Ticket Yasağı",
                    description=(
                        f"Ticket açma yetkiniz bulunmamaktadır.\n\n"
                        f"**Sebep:** {reason}\n"
                        f"**Bitiş:** {until_str}"
                    ),
                    color=0xFF4444
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # ── Zaten açık ticket var mı? ──
        for ch_id, info in data["open_tickets"].items():
            if str(info.get("user_id")) == uid:
                ch = interaction.guild.get_channel(int(ch_id))
                if ch:
                    embed = discord.Embed(
                        description=f"Zaten açık bir ticketınız var: {ch.mention}",
                        color=0xFFAA00
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

        cats = data.get("categories", DEFAULT_CATEGORIES)
        kategori_map = {}
        for cat in cats:
            emoji = bot.get_emoji(cat["emoji_id"]) if cat.get("emoji_id") else ""
            kategori_map[cat["id"]] = f"{emoji} {cat['label']}" if emoji else cat["label"]
        secilen = self.values[0]
        kategori_label = kategori_map.get(secilen, secilen)

        # ── Yükleniyor mesajı ──
        loading_embed = discord.Embed(
            title="⏳ Ticketiniz Oluşturuluyor",
            description=f"{e(ID_EMOJI_SORU)} **Biliyor muydunuz?** Bu sunucu kimseyi dolandırmadı.",
            color=0x5865F2
        )
        await interaction.response.send_message(embed=loading_embed, ephemeral=True)
        await asyncio.sleep(5)

        # ── Ticket kanalı oluştur ──
        guild      = interaction.guild
        category   = guild.get_channel(TICKET_CATEGORY_ID)
        staff_role = guild.get_role(STAFF_ROLE_ID)

        data["ticket_counter"] += 1
        counter = data["ticket_counter"]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_channels=True
            )

        safe_name    = interaction.user.name.lower().replace(" ", "-")[:20]
        channel_name = f"ticket-{counter:04d}-{safe_name}"

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket | {interaction.user} | {kategori_label}"
        )

        data["open_tickets"][str(ticket_channel.id)] = {
            "user_id": interaction.user.id,
            "category": secilen,
            "created_at": datetime.utcnow().isoformat()
        }
        save_data(data)

        # ── Ticket kanalına embed + butonlar ──
        ticket_embed = discord.Embed(
            title=f"🎫 Ticket #{counter:04d}",
            description=(
                f"Merhaba {interaction.user.mention}!\n\n"
                f"**Kategori:** {kategori_label}\n\n"
                f"Yetkili ekibimiz en kısa sürede size yardımcı olacaktır.\n"
                f"Lütfen sorununuzu detaylıca açıklayın."
            ),
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        ticket_embed.set_footer(text="Zumami Shop • Ticket Sistemi")
        if guild.icon:
            ticket_embed.set_thumbnail(url=guild.icon.url)

        view = TicketControlView(ticket_channel.id)
        await ticket_channel.send(
            content=f"{interaction.user.mention}" + (f" | {staff_role.mention}" if staff_role else ""),
            embed=ticket_embed,
            view=view
        )

        # ── Kullanıcıya bildir ──
        done_embed = discord.Embed(
            title="✅ Ticketiniz Oluşturuldu!",
            description=f"Ticketınız açıldı → {ticket_channel.mention}",
            color=0x57F287
        )
        await interaction.edit_original_response(embed=done_embed)

        await send_log(
            guild,
            f"📩 Yeni ticket açıldı: {ticket_channel.mention} | "
            f"Kullanıcı: {interaction.user} | Kategori: {kategori_label}"
        )


# ──────────────────────────────────────────────
#  PANEL VIEW
# ──────────────────────────────────────────────
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ──────────────────────────────────────────────
#  TICKET KONTROL BUTONLARI
# ──────────────────────────────────────────────
# Ticket buton emoji IDleri
EMOJI_HAYIR    = 1504478910782378116   # ❌ (üye çıkar, kapat)
EMOJI_PASSED   = 1504479130438336522   # ✅ (ticket ismi değiştir)
EMOJI_YETKILI  = 1500121229728944409   # 👑 (yetkili çağır)
EMOJI_UYE_EKLE = 1504481954924462111   # 👥 (üye ekle)


class TicketIsmiModal(discord.ui.Modal, title="✏️ Ticket İsmini Değiştir"):
    yeni_isim = discord.ui.TextInput(label="Yeni İsim", placeholder="örn: vip-destek", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        yeni = self.yeni_isim.value.strip().lower().replace(" ", "-")
        await interaction.channel.edit(name=yeni)
        embed = discord.Embed(description=f"✅ Ticket ismi **{yeni}** olarak değiştirildi.", color=0x57F287)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"✏️ Ticket ismi değiştirildi: {yeni} | Yetkili: {interaction.user}")


class UyeEkleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Eklenecek üyeyi ara...",
        min_values=1,
        max_values=1
    )
    async def uye_sec(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        embed = discord.Embed(description=f"✅ {member.mention} tickete eklendi.", color=0x57F287)
        await interaction.response.edit_message(embed=embed, view=None)


class UyeCikarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Çıkarılacak üyeyi ara...",
        min_values=1,
        max_values=1
    )
    async def uye_sec(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await interaction.channel.set_permissions(member, overwrite=None)
        embed = discord.Embed(description=f"✅ {member.mention} ticketten çıkarıldı.", color=0xFF4444)
        await interaction.response.edit_message(embed=embed, view=None)


class TicketControlView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(
        label="Üye Ekle",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_uye_ekle",
        emoji=discord.PartialEmoji(id=EMOJI_UYE_EKLE)
    )
    async def uye_ekle(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description="👥 Tickete eklemek istediğin üyeyi seç:", color=0x5865F2)
        await interaction.response.send_message(embed=embed, view=UyeEkleView(), ephemeral=True)

    @discord.ui.button(
        label="Üye Çıkar",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_uye_cikar",
        emoji=discord.PartialEmoji(id=EMOJI_HAYIR)
    )
    async def uye_cikar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description="❌ Ticketten çıkarmak istediğin üyeyi seç:", color=0xFF4444)
        await interaction.response.send_message(embed=embed, view=UyeCikarView(), ephemeral=True)

    @discord.ui.button(
        label="Yetkili Çağır",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_yetkili_cagir",
        emoji=discord.PartialEmoji(id=EMOJI_YETKILI)
    )
    async def yetkili_cagir(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role:
            await interaction.channel.send(f"{staff_role.mention} bir yetkili çağrıldı!")
        embed = discord.Embed(description="✅ Yetkililer bilgilendirildi.", color=0x57F287)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Ticket İsmi Değiştir",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_isim_degistir",
        emoji=discord.PartialEmoji(id=EMOJI_PASSED)
    )
    async def isim_degistir(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        is_staff   = staff_role in interaction.user.roles if staff_role else False
        if not is_staff:
            return await interaction.response.send_message("❌ Yetkiniz yok.", ephemeral=True)
        await interaction.response.send_modal(TicketIsmiModal())

    @discord.ui.button(
        label="Ticket Kapat",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_kapat",
        emoji=discord.PartialEmoji(id=EMOJI_HAYIR),
        row=2
    )
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        ch_id = str(interaction.channel.id)
        ticket_info = data["open_tickets"].get(ch_id)

        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        is_staff = staff_role in interaction.user.roles if staff_role else False
        is_owner = ticket_info and str(ticket_info["user_id"]) == str(interaction.user.id)

        if not is_staff and not is_owner:
            return await interaction.response.send_message(
                "❌ Bu ticketi kapatma yetkiniz yok.", ephemeral=True
            )

        embed = discord.Embed(
            title="🔒 Ticket Kapatılıyor",
            description="Bu ticket **5 saniye** içinde kapatılacak...",
            color=0xFF4444
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)

        if ch_id in data["open_tickets"]:
            vc_id = data["open_tickets"][ch_id].get("voice_channel_id")
            if vc_id:
                vc = interaction.guild.get_channel(vc_id)
                if vc:
                    await vc.delete(reason="Ticket kapatıldı")
            del data["open_tickets"][ch_id]
            save_data(data)

        await send_log(
            interaction.guild,
            f"🔒 Ticket kapatıldı: #{interaction.channel.name} | Kapatan: {interaction.user}"
        )
        await interaction.channel.delete(reason=f"Ticket kapatıldı - {interaction.user}")

    @discord.ui.button(
        label="Sesli Destek Aç",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_sesli",
        row=2
    )
    async def sesli(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.emoji = e(ID_EMOJI_SESLI)
        data = load_data()
        ch_id = str(interaction.channel.id)
        ticket_info = data["open_tickets"].get(ch_id)

        if not ticket_info:
            return await interaction.response.send_message(
                "❌ Bu kanal geçerli bir ticket değil.", ephemeral=True
            )

        guild          = interaction.guild
        staff_role     = guild.get_role(STAFF_ROLE_ID)
        voice_category = guild.get_channel(VOICE_CATEGORY_ID)
        member         = guild.get_member(ticket_info["user_id"])

        if not member:
            return await interaction.response.send_message(
                "❌ Ticket sahibi sunucuda bulunamadı.", ephemeral=True
            )

        existing_id = ticket_info.get("voice_channel_id")
        if existing_id:
            existing_vc = guild.get_channel(existing_id)
            if existing_vc:
                return await interaction.response.send_message(
                    f"Zaten açık bir sesli kanalınız var: {existing_vc.mention}", ephemeral=True
                )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            )

        vc = await guild.create_voice_channel(
            name=f"🔊 destek-{member.name[:15]}",
            category=voice_category,
            overwrites=overwrites
        )

        data["open_tickets"][ch_id]["voice_channel_id"] = vc.id
        save_data(data)

        embed = discord.Embed(
            title="🔊 Sesli Destek Kanalı Açıldı",
            description=f"{member.mention} için sesli kanal oluşturuldu!\n\n**Kanal:** {vc.mention}",
            color=0x57F287
        )
        await interaction.response.send_message(embed=embed)
        await send_log(guild, f"🔊 Sesli destek açıldı: {vc.name} | Ticket: {interaction.channel.name}")


# ──────────────────────────────────────────────
#  LOG
# ──────────────────────────────────────────────
async def send_log(guild: discord.Guild, message: str):
    if not LOG_CHANNEL_ID:
        return
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch:
        embed = discord.Embed(description=message, color=0x5865F2, timestamp=datetime.utcnow())
        await ch.send(embed=embed)


# ──────────────────────────────────────────────
#  PREFIX KOMUTLARI (z!ticket, z!ticketyasakla, z!ticketyasakkaldir)
# ──────────────────────────────────────────────
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

@bot.command(name="ticket")
@is_admin()
async def ticket_cmd(ctx):
    embed = discord.Embed(
        title="🏪 Zumami Shop",
        description=(
            "Stok veya herhangi bir konuda yardım almak için aşağıdan ticket açabilirsin.\n\n"
            f"{e(ID_EMOJI_UYARI)} **Uyarı:** Boş yere ticket açan, trolleyen veya ürün almadan uğraştıran "
            "kişilere **mute veya ticket yasağı** uygulanacaktır."
        ),
        color=0x5865F2
    )
    embed.set_footer(text="Zumami Shop • Destek Sistemi")
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    view = TicketPanelView()
    await ctx.send(embed=embed, view=view)
    try:
        await ctx.message.delete()
    except:
        pass


@bot.command(name="ticketyasakla")
@is_admin()
async def ticketyasakla(ctx, user: discord.Member, time: str, *, reason: str):
    data = load_data()
    uid = str(user.id)

    if time == "0" or time.lower() in ("süresiz", "permanent"):
        until = "permanent"
        until_str = "Süresiz"
    else:
        now = datetime.utcnow()
        try:
            amount = int(time[:-1])
            unit = time[-1].lower()
            delta_map = {
                "m": timedelta(minutes=amount),
                "h": timedelta(hours=amount),
                "d": timedelta(days=amount)
            }
            if unit not in delta_map:
                raise ValueError
            until     = (now + delta_map[unit]).isoformat()
            until_str = (now + delta_map[unit]).strftime("%d.%m.%Y %H:%M UTC")
        except (ValueError, IndexError):
            return await ctx.send("❌ Geçersiz süre. Örnek: `10m`, `2h`, `3d`, `0` (süresiz)")

    data["ticket_bans"][uid] = {
        "reason": reason,
        "until": until,
        "banned_by": str(ctx.author.id)
    }
    save_data(data)

    embed = discord.Embed(title="🚫 Ticket Yasağı Uygulandı", color=0xFF4444, timestamp=datetime.utcnow())
    embed.add_field(name="Kullanıcı", value=f"{user.mention} (`{user.id}`)", inline=False)
    embed.add_field(name="Sebep",     value=reason,    inline=False)
    embed.add_field(name="Bitiş",     value=until_str, inline=False)
    embed.add_field(name="Yetkili",   value=ctx.author.mention, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)

    await ctx.send(embed=embed)
    await send_log(
        ctx.guild,
        f"🚫 Ticket yasağı | Kullanıcı: {user} | Sebep: {reason} | Bitiş: {until_str} | Yetkili: {ctx.author}"
    )


@bot.command(name="ticketkategorileri")
@is_admin()
async def ticketkategorileri(ctx):
    data = load_data()
    cats = data.get("categories", DEFAULT_CATEGORIES)
    kat_listesi = "\n".join(
        f"**{i+1}.** {bot.get_emoji(c['emoji_id']) or ''} {c['label']} — *{c['description']}*"
        for i, c in enumerate(cats)
    ) or "Henüz kategori yok."

    embed = discord.Embed(
        title="🗂️ Ticket Kategorileri",
        description=f"{kat_listesi}\n\nAşağıdan düzenlemek istediğin kategoriyi seç veya yeni ekle/sil.",
        color=0x5865F2
    )
    view = KategoriYonetimView()
    await ctx.send(embed=embed, view=view)
    try:
        await ctx.message.delete()
    except:
        pass



@bot.command(name="ticketyasakkaldir")
@is_admin()
async def ticketyasakkaldir(ctx, user: discord.Member):
    data = load_data()
    uid = str(user.id)

    if uid not in data["ticket_bans"]:
        return await ctx.send(f"❌ {user.mention} zaten ticket yasağında değil.")

    del data["ticket_bans"][uid]
    save_data(data)

    embed = discord.Embed(
        title="✅ Ticket Yasağı Kaldırıldı",
        description=f"{user.mention} kullanıcısının ticket yasağı kaldırıldı.",
        color=0x57F287
    )
    await ctx.send(embed=embed)
    await send_log(
        ctx.guild,
        f"✅ Ticket yasağı kaldırıldı | Kullanıcı: {user} | Yetkili: {ctx.author}"
    )


# ──────────────────────────────────────────────
#  BOT HAZIR
# ──────────────────────────────────────────────
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(AIPanelView())
    bot.add_view(CekilisBaslatView())
    data_c = load_data()
    for cid in data_c.get("cekilisler", {}):
        bot.add_view(CekilisView(cid))
        bot.add_view(CekilisKatilimciView(cid))
    data = load_data()
    for ch_id in data.get("open_tickets", {}):
        bot.add_view(TicketControlView(int(ch_id)))

    print(f"✅ {bot.user} aktif! | Guild: {GUILD_ID}")


# ──────────────────────────────────────────────
#  AI PANEL – Sunucu Bilgi Sistemi
# ──────────────────────────────────────────────

import aiohttp
import re

OPENROUTER_API_KEY  = get_cfg("OPENROUTER_API_KEY")
OPENROUTER_MODEL    = "openai/gpt-4o-mini"
OPENROUTER_URL      = "https://openrouter.ai/api/v1/chat/completions"

# Bot sunucudan bilgi toplarken gezecek sabit kanallar
AI_INFO_CHANNEL_IDS = [1496904142827032717, 1502603476604293140]

# Küfür / uygunsuz içerik tespiti için anahtar kelimeler
KUFUR_LISTESI = [
    "sik", "oç", "orospu", "göt", "amk", "bok", "piç", "kahpe",
    "ibne", "pezevenk", "yarrak", "amına", "31 çek", "31 çekm",
    "mastürb", "seks", "porn", "sex", "fuck", "shit", "bitch",
    "küfür", "tehdit", "öldür", "gebertir", "seni bulur"
]

def icerik_uygunsuz_mu(metin: str) -> bool:
    metin_lower = metin.lower()
    return any(k in metin_lower for k in KUFUR_LISTESI)


async def sunucu_bilgisi_topla(guild: discord.Guild) -> str:
    """Sunucunun tüm kanallarını ve sabit info kanallarını tarayıp özet döner."""
    bilgiler = []

    # 1) Sabit info kanallarından mesajları oku
    for ch_id in AI_INFO_CHANNEL_IDS:
        kanal = guild.get_channel(ch_id)
        if not kanal or not isinstance(kanal, discord.TextChannel):
            continue
        try:
            msgs = [m async for m in kanal.history(limit=50, oldest_first=True)]
            icerik = "\n".join(
                f"[{m.created_at.strftime('%d.%m.%Y')}] {m.author.display_name}: {m.clean_content}"
                for m in msgs if m.clean_content.strip()
            )
            if icerik:
                bilgiler.append(f"### #{kanal.name} kanalı içeriği:\n{icerik}")
        except Exception:
            pass

    # 2) Sunucu genel yapısı
    yapi = []
    yapi.append(f"Sunucu adı: {guild.name}")
    yapi.append(f"Üye sayısı: {guild.member_count}")
    yapi.append(f"Oluşturulma: {guild.created_at.strftime('%d.%m.%Y')}")

    # Kategoriler ve kanallar
    for cat in guild.categories:
        alt = [f"  - #{c.name}" for c in cat.channels if isinstance(c, discord.TextChannel)]
        if alt:
            yapi.append(f"Kategori [{cat.name}]:\n" + "\n".join(alt))

    # Roller
    roller = [r.name for r in guild.roles if r.name != "@everyone"]
    yapi.append("Roller: " + ", ".join(roller))

    bilgiler.append("### Sunucu Yapısı:\n" + "\n".join(yapi))

    return "\n\n".join(bilgiler)


async def openrouter_sor(soru: str, sunucu_bilgisi: str) -> str:
    """OpenRouter API'ye istek atar, cevap döner."""
    sistem_mesaji = (
        "Sen bir Discord sunucusunun yardımcı yapay zeka asistanısın. "
        "Kullanıcıların sunucu hakkında sorduğu soruları yanıtlarsın. "
        "Aşağıda sana sunucu hakkında toplanmış bilgiler verilmiştir. "
        "Bu bilgileri kullanarak Türkçe, kısa ve net cevap ver.\n\n"
        "SUNUCU BİLGİLERİ:\n"
        f"{sunucu_bilgisi[:6000]}"  # token limitini aşmamak için
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": sistem_mesaji},
            {"role": "user",   "content": soru}
        ],
        "max_tokens": 600,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.gg",
        "X-Title": "DiscordBot"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
            if resp.status != 200:
                metin = await resp.text()
                raise Exception(f"OpenRouter hata {resp.status}: {metin[:200]}")
            veri = await resp.json()
            return veri["choices"][0]["message"]["content"].strip()


# AI Panel butonu
class AIPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Kanal Aç",
        style=discord.ButtonStyle.primary,
        custom_id="aipanel_kanal_ac",
        emoji="🤖"
    )
    async def kanal_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        uid   = str(interaction.user.id)
        data  = load_data()

        # Ticket yasağı kontrolü (aynı ban sistemi)
        if uid in data["ticket_bans"]:
            ban   = data["ticket_bans"][uid]
            until = ban.get("until")
            expired = until != "permanent" and datetime.fromisoformat(until) <= datetime.utcnow()
            if expired:
                del data["ticket_bans"][uid]
                save_data(data)
            else:
                until_str = "Süresiz" if until == "permanent" else datetime.fromisoformat(until).strftime("%d.%m.%Y %H:%M")
                embed = discord.Embed(
                    title="🚫 Erişim Yasağı",
                    description=f"**Sebep:** {ban.get('reason', 'Belirtilmedi')}\n**Bitiş:** {until_str}",
                    color=0xFF4444
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Zaten açık AI kanalı var mı?
        ai_tickets = data.get("ai_tickets", {})
        for ch_id, info in ai_tickets.items():
            if str(info.get("user_id")) == uid:
                mevcut = guild.get_channel(int(ch_id))
                if mevcut:
                    return await interaction.response.send_message(
                        embed=discord.Embed(description=f"Zaten açık bir AI destek kanalın var: {mevcut.mention}", color=0xFFAA00),
                        ephemeral=True
                    )

        await interaction.response.defer(ephemeral=True)

        # Bilgileri topla
        try:
            sunucu_bilgisi = await sunucu_bilgisi_topla(guild)
        except Exception as e:
            sunucu_bilgisi = f"Bilgi toplanamadı: {e}"

        # Kanal oluştur
        staff_role = guild.get_role(STAFF_ROLE_ID)
        category   = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)

        safe_name = interaction.user.name.lower().replace(" ", "-")[:20]
        kanal = await guild.create_text_channel(
            name=f"ai-bilgi-{safe_name}",
            category=category,
            overwrites=overwrites,
            topic=f"AI Bilgi Kanalı | {interaction.user}"
        )

        # Kaydet
        if "ai_tickets" not in data:
            data["ai_tickets"] = {}
        data["ai_tickets"][str(kanal.id)] = {
            "user_id": interaction.user.id,
            "sunucu_bilgisi": sunucu_bilgisi,
            "created_at": datetime.utcnow().isoformat()
        }
        save_data(data)

        # Karşılama mesajı
        hosgeldin = discord.Embed(
            title="🤖 AI Sunucu Asistanı",
            description=(
                f"Merhaba {interaction.user.mention}! 👋\n\n"
                "Sunucu hakkında merak ettiğin her şeyi sorabilirsin.\n"
                "Örneğin:\n"
                "• Event başladı mı / bitti mi?\n"
                "• Hangi roller var?\n"
                "• Sunucuda ne zaman etkinlik oluyor?\n\n"
                "Sadece bu kanala yaz, sana yardımcı olayım! 😊"
            ),
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        hosgeldin.set_footer(text="Uygunsuz içerik → otomatik yasak uygulanır")

        await kanal.send(content=interaction.user.mention, embed=hosgeldin)
        await interaction.followup.send(
            embed=discord.Embed(description=f"✅ Kanalın açıldı → {kanal.mention}", color=0x57F287),
            ephemeral=True
        )
        await send_log(guild, f"🤖 AI bilgi kanalı açıldı: {kanal.mention} | Kullanıcı: {interaction.user}")


# AI mesajlarını dinle
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    data  = load_data()
    ch_id = str(message.channel.id)

    if "ai_tickets" in data and ch_id in data["ai_tickets"]:
        uid         = str(message.author.id)
        ticket_info = data["ai_tickets"][ch_id]

        # Küfür/uygunsuz içerik kontrolü
        if icerik_uygunsuz_mu(message.content):
            until     = datetime.utcnow() + timedelta(days=30)
            until_str = until.strftime("%d.%m.%Y %H:%M UTC")
            data["ticket_bans"][uid] = {
                "reason": "AI kanalında küfür/hakaret/uygunsuz içerik",
                "until":  until.isoformat(),
                "banned_by": str(bot.user.id)
            }
            save_data(data)

            uyari = discord.Embed(
                title="🚫 Uygunsuz İçerik Tespit Edildi",
                description=(
                    f"{message.author.mention} uygunsuz içerik nedeniyle **1 ay** ticket yasağı aldı.\n"
                    "Bu kanal otomatik kapatılıyor."
                ),
                color=0xFF0000
            )
            await message.channel.send(embed=uyari)
            await send_log(
                message.guild,
                f"🚫 Uygunsuz içerik | AI kanal kapatıldı | Kullanıcı: {message.author} | Mesaj: {message.content[:100]}"
            )
            await asyncio.sleep(3)

            del data["ai_tickets"][ch_id]
            save_data(data)
            await message.channel.delete(reason="Uygunsuz içerik – otomatik kapatıldı")
            return  # kanal silindi, process_commands gerek yok

        # Normal soru → AI'ye sor
        async with message.channel.typing():
            try:
                sunucu_bilgisi = ticket_info.get("sunucu_bilgisi", "Bilgi yok.")
                cevap = await openrouter_sor(message.content, sunucu_bilgisi)
            except Exception as ex:
                cevap = f"⚠️ API hatası: {ex}"

        embed = discord.Embed(description=cevap, color=0x5865F2)
        embed.set_author(name="AI Asistan 🤖")
        await message.channel.send(embed=embed)
        # AI kanalında da komutlar çalışsın (z!aipanelkaldir vs.)
        await bot.process_commands(message)
        return

    # Normal kanal → prefix komutları işle
    await bot.process_commands(message)


# ──────────────────────────────────────────────
#  AI PANEL KOMUTLARI
# ──────────────────────────────────────────────

# Sadece bu kullanıcı ID'si bu komutları kullanabilir
AI_YETKILI_ID = 1450895145271558245

def is_ai_yetkili():
    async def predicate(ctx):
        return ctx.author.id == AI_YETKILI_ID
    return commands.check(predicate)


@bot.command(name="aipanel")
@is_admin()
async def aipanel_cmd(ctx):
    """AI Panel mesajını gönderir."""
    embed = discord.Embed(
        title="🤖 Sunucu Hakkında Bilgi Al",
        description=(
            "Sunucumuz hakkında merak ettiğin her şeyi yapay zekamıza sorabilirsin!\n\n"
            "Aşağıdaki butona basarak özel bir kanal açabilirsin."
        ),
        color=0x5865F2
    )
    embed.set_footer(text="Uygunsuz kullanım → otomatik yasak")
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.send(embed=embed, view=AIPanelView())
    try:
        await ctx.message.delete()
    except:
        pass


@bot.command(name="aiuseryasakla")
@is_ai_yetkili()
async def aiuseryasakla_cmd(ctx, user: discord.Member, *, sebep: str = "Belirtilmedi"):
    """Kullanıcıya süresiz AI panel yasağı uygular."""
    data = load_data()
    uid  = str(user.id)

    data["ticket_bans"][uid] = {
        "reason": sebep,
        "until": "permanent",
        "banned_by": str(ctx.author.id)
    }
    save_data(data)

    embed = discord.Embed(
        title="🚫 AI Panel Yasağı Uygulandı",
        color=0xFF4444,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Kullanıcı", value=f"{user.mention} (`{user.id}`)", inline=False)
    embed.add_field(name="Sebep",     value=sebep,             inline=False)
    embed.add_field(name="Süre",      value="Süresiz",         inline=False)
    embed.add_field(name="Yetkili",   value=ctx.author.mention, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)

    await ctx.send(embed=embed)
    await send_log(
        ctx.guild,
        f"🚫 AI panel yasağı | Kullanıcı: {user} | Sebep: {sebep} | Süresiz | Yetkili: {ctx.author}"
    )


@bot.command(name="aipanelkaldir")
@is_ai_yetkili()
async def aipanelkaldir_cmd(ctx, user: discord.Member):
    """AI panel yasağını kaldırır."""
    data = load_data()
    uid  = str(user.id)

    if uid not in data["ticket_bans"]:
        return await ctx.send(f"❌ {user.mention} zaten yasakta değil.")

    del data["ticket_bans"][uid]
    save_data(data)

    embed = discord.Embed(
        title="✅ Yasak Kaldırıldı",
        description=f"{user.mention} kullanıcısının yasağı kaldırıldı.",
        color=0x57F287
    )
    await ctx.send(embed=embed)
    await send_log(ctx.guild, f"✅ Yasak kaldırıldı | Kullanıcı: {user} | Yetkili: {ctx.author}")



# ──────────────────────────────────────────────
#  ÇEKİLİŞ SİSTEMİ
# ──────────────────────────────────────────────
import re as _re

def emoji_id_bul_ve_donustur(guild: discord.Guild, metin: str) -> str:
    """Metindeki (emoji_id) kalıplarını gerçek emojiye dönüştürür."""
    def replace(m):
        eid = int(m.group(1))
        e = guild.get_emoji(eid)
        return str(e) if e else m.group(0)
    return _re.sub(r"\((\d{15,20})\)", replace, metin)


class CekilisModal(discord.ui.Modal, title="🎉 Çekiliş Oluştur"):
    odul_ismi = discord.ui.TextInput(
        label="Ödül İsmi",
        placeholder="örn: Nitro 1 Ay",
        max_length=100
    )
    odul_aciklama = discord.ui.TextInput(
        label="Ödül Açıklaması",
        placeholder="Açıklamaya emoji eklemek için: (emoji_id)",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        isim  = self.odul_ismi.value.strip()
        acik  = emoji_id_bul_ve_donustur(guild, self.odul_aciklama.value.strip())

        data = load_data()
        if "cekilisler" not in data:
            data["cekilisler"] = {}

        cekilis_id = str(interaction.channel_id) + "_" + str(int(datetime.utcnow().timestamp()))

        embed = discord.Embed(
            title=f"🎉 {isim}",
            description=acik,
            color=0xFFD700,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Çekiliş ID: {cekilis_id}")
        embed.add_field(name="Katılımcı", value="0", inline=True)

        view = CekilisView(cekilis_id)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        data["cekilisler"][cekilis_id] = {
            "isim": isim,
            "aciklama": acik,
            "katilimcilar": [],
            "kanal_id": interaction.channel_id,
            "mesaj_id": msg.id,
            "olusturan": interaction.user.id
        }
        save_data(data)


class CekilisView(discord.ui.View):
    def __init__(self, cekilis_id: str):
        super().__init__(timeout=None)
        self.cekilis_id = cekilis_id

    @discord.ui.button(label="Katıl 🎉", style=discord.ButtonStyle.success, custom_id="cekilis_katil")
    async def katil(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        c    = data.get("cekilisler", {}).get(self.cekilis_id)
        if not c:
            return await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)

        uid = str(interaction.user.id)
        if uid not in c["katilimcilar"]:
            c["katilimcilar"].append(uid)
            save_data(data)

        toplam = len(c["katilimcilar"])
        sans   = round(100 / toplam, 2) if toplam > 0 else 100.0

        embed = discord.Embed(
            title="✅ Çekilişe Katıldın!",
            description="Kazanmaya şansın var gibi görünüyor.",
            color=0x57F287
        )
        embed.add_field(name="Toplam Katılımcı", value=str(toplam), inline=True)
        embed.add_field(name="Kazanma Şansın",   value=f"%{sans}",  inline=True)

        await interaction.response.send_message(
            embed=embed,
            view=CekilisKatilimciView(self.cekilis_id),
            ephemeral=True
        )

    @discord.ui.button(label="Katılanları Göster 👥", style=discord.ButtonStyle.secondary, custom_id="cekilis_liste")
    async def liste(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        c    = data.get("cekilisler", {}).get(self.cekilis_id)
        if not c:
            return await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)

        katilimcilar = c["katilimcilar"]
        if not katilimcilar:
            return await interaction.response.send_message("Henüz katılımcı yok.", ephemeral=True)

        toplam = len(katilimcilar)
        sans   = round(100 / toplam, 2)

        satirlar = []
        for i, uid in enumerate(katilimcilar, 1):
            member = interaction.guild.get_member(int(uid))
            isim   = member.display_name if member else f"<@{uid}>"
            satirlar.append(f"`{i}.` {isim}")

        embed = discord.Embed(
            title=f"👥 Katılımcılar — {c['isim']}",
            description="\n".join(satirlar),
            color=0x5865F2
        )
        embed.set_footer(text=f"Toplam: {toplam} katılımcı | Eşit şans: %{sans}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CekilisKatilimciView(discord.ui.View):
    def __init__(self, cekilis_id: str):
        super().__init__(timeout=None)
        self.cekilis_id = cekilis_id

    @discord.ui.button(label="Çekilişten Ayrıl", style=discord.ButtonStyle.danger,   custom_id="cekilis_ayril")
    async def ayril(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        c    = data.get("cekilisler", {}).get(self.cekilis_id)
        if not c:
            return await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)

        uid = str(interaction.user.id)
        if uid in c["katilimcilar"]:
            c["katilimcilar"].remove(uid)
            save_data(data)

        await interaction.response.send_message("✅ Çekilişten ayrıldın.", ephemeral=True)

    @discord.ui.button(label="Verileri Güncelle 🔄", style=discord.ButtonStyle.secondary, custom_id="cekilis_guncelle")
    async def guncelle(self, interaction: discord.Interaction, button: discord.ui.Button):
        data    = load_data()
        c       = data.get("cekilisler", {}).get(self.cekilis_id)
        if not c:
            return await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)

        toplam = len(c["katilimcilar"])
        sans   = round(100 / toplam, 2) if toplam > 0 else 100.0
        uid    = str(interaction.user.id)
        katildi = uid in c["katilimcilar"]

        embed = discord.Embed(
            title="✅ Çekilişe Katıldın!" if katildi else "ℹ️ Çekiliş Bilgisi",
            description="Kazanmaya şansın var gibi görünüyor." if katildi else "Bu çekilişe katılmadın.",
            color=0x57F287 if katildi else 0xAAAAAA
        )
        embed.add_field(name="Toplam Katılımcı", value=str(toplam), inline=True)
        embed.add_field(name="Kazanma Şansın",   value=f"%{sans}",  inline=True)
        await interaction.response.edit_message(embed=embed, view=self)


class CekilisBaslatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Çekiliş Oluştur 🎉", style=discord.ButtonStyle.primary, custom_id="cekilis_olustur")
    async def olustur(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        is_staff   = staff_role in interaction.user.roles if staff_role else False
        if not is_staff:
            return await interaction.response.send_message("❌ Yetkiniz yok.", ephemeral=True)
        await interaction.response.send_modal(CekilisModal())


@bot.command(name="cekilis")
@is_admin()
async def cekilis_cmd(ctx):
    """Çekiliş paneli gönderir."""
    embed = discord.Embed(
        title="🎉 Çekiliş Sistemi",
        description="Yeni bir çekiliş başlatmak için aşağıdaki butona bas.",
        color=0xFFD700
    )
    await ctx.send(embed=embed, view=CekilisBaslatView())
    try:
        await ctx.message.delete()
    except:
        pass


# ──────────────────────────────────────────────
#  AYARLAR SİSTEMİ
# ──────────────────────────────────────────────

AYAR_LABELS = {
    "GUILD_ID":           ("🏠 Guild ID",            "int"),
    "STAFF_ROLE_ID":      ("👮 Staff Rol ID",        "int"),
    "TICKET_CATEGORY_ID": ("📁 Ticket Kategori ID",  "int"),
    "VOICE_CATEGORY_ID":  ("🔊 Sesli Kategori ID",   "int"),
    "LOG_CHANNEL_ID":     ("📋 Log Kanal ID",        "int"),
    "OPENROUTER_API_KEY": ("🤖 OpenRouter API Key",  "str"),
}

class AyarModal(discord.ui.Modal):
    def __init__(self, key: str):
        self.key = key
        label, typ = AYAR_LABELS[key]
        super().__init__(title=f"⚙️ {label} Ayarla")
        cfg = load_config()
        mevcut = str(cfg.get(key, ""))
        if key == "OPENROUTER_API_KEY" and mevcut:
            gosterilen = mevcut[:6] + "..." + mevcut[-4:] if len(mevcut) > 10 else mevcut
        else:
            gosterilen = mevcut
        self.deger = discord.ui.TextInput(
            label="Yeni Değer",
            placeholder=f"Mevcut: {gosterilen or 'Ayarlanmamış'}",
            required=True,
            max_length=500
        )
        self.add_item(self.deger)

    async def on_submit(self, interaction: discord.Interaction):
        cfg = load_config()
        yeni = self.deger.value.strip()
        label, typ = AYAR_LABELS[self.key]

        if typ == "int":
            try:
                int(yeni)
            except ValueError:
                return await interaction.response.send_message(
                    f"❌ **{label}** için geçerli bir sayı gir.", ephemeral=True
                )

        cfg[self.key] = yeni
        save_config(cfg)

        global GUILD_ID, STAFF_ROLE_ID, TICKET_CATEGORY_ID, VOICE_CATEGORY_ID, LOG_CHANNEL_ID, OPENROUTER_API_KEY
        if self.key == "GUILD_ID":           GUILD_ID           = int(yeni)
        elif self.key == "STAFF_ROLE_ID":      STAFF_ROLE_ID      = int(yeni)
        elif self.key == "TICKET_CATEGORY_ID": TICKET_CATEGORY_ID = int(yeni)
        elif self.key == "VOICE_CATEGORY_ID":  VOICE_CATEGORY_ID  = int(yeni)
        elif self.key == "LOG_CHANNEL_ID":     LOG_CHANNEL_ID     = int(yeni)
        elif self.key == "OPENROUTER_API_KEY": OPENROUTER_API_KEY = yeni

        gizli = yeni[:6] + "..." + yeni[-4:] if self.key == "OPENROUTER_API_KEY" and len(yeni) > 10 else yeni
        embed = discord.Embed(
            description=(
                f"✅ **{label}** güncellendi: `{gizli}`\n\n"
            ),
            color=0x57F287
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AyarDropdown(discord.ui.Select):
    def __init__(self):
        cfg = load_config()
        options = []
        for key, (label, typ) in AYAR_LABELS.items():
            val = str(cfg.get(key, ""))
            if key == "OPENROUTER_API_KEY" and val:
                ozet = val[:6] + "..." + val[-4:] if len(val) > 10 else "Ayarlandı"
            else:
                ozet = val[:30] if val else "Ayarlanmamış"
            options.append(discord.SelectOption(
                label=label,
                value=key,
                description=f"Mevcut: {ozet}"
            ))
        super().__init__(
            placeholder="Ayarlamak istediğin değeri seç...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ayar_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AyarModal(self.values[0]))


class AyarlarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(AyarDropdown())


@bot.command(name="ayarlar")
@is_admin()
async def ayarlar_cmd(ctx):
    """Bot ayarlarini dropdown ile duzenle."""
    cfg = load_config()

    def mask(k, v):
        if k == "OPENROUTER_API_KEY" and v and len(v) > 10:
            return v[:6] + "..." + v[-4:]
        return v or "Ayarlanmamis"

    satirlar = "\n".join(
        f"**{label}:** `{mask(k, str(cfg.get(k, '')))}`"
        for k, (label, _) in AYAR_LABELS.items()
    )
    embed = discord.Embed(
        title="⚙️ Bot Ayarları",
        description=f"{satirlar}\n\nAşağıdan değiştirmek istediğin ayarı seç:",
        color=0x5865F2
    )
    await ctx.send(embed=embed, view=AyarlarView())
    try:
        await ctx.message.delete()
    except:
        pass


# ──────────────────────────────────────────────
#  DROP SİSTEMİ
# ──────────────────────────────────────────────
drop_sessions = {}  # channel_id -> drop bilgisi

def parse_sure(sure_str: str):
    """1h, 2d, 30m gibi süreyi saniyeye çevirir. None dönerse geçersiz."""
    match = re.fullmatch(r"(\d+)([smhd])", sure_str.strip().lower())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    return val * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]

def random_kelime(uzunluk=6):
    return "".join(rnd.choices(string.ascii_lowercase, k=uzunluk))


class DropKurulumModal(discord.ui.Modal, title="🎁 Drop Kurulumu"):
    odul = discord.ui.TextInput(label="Ödül İsmi", placeholder="Örn: Netflix Premium", required=True, max_length=100)
    tepki_esik = discord.ui.TextInput(label="Kaç tepkide başlasın?", placeholder="Örn: 20", required=True, max_length=5)
    sure = discord.ui.TextInput(label="Süre (1h / 2d / 30m)", placeholder="Örn: 2h — süre bitince drop iptal", required=True, max_length=10)
    email = discord.ui.TextInput(label="E-posta", placeholder="example@gmail.com", required=True, max_length=200)
    sifre = discord.ui.TextInput(label="Şifre", placeholder="Ödülün şifresi", required=True, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        # Tepki eşiği doğrula
        try:
            esik = int(self.tepki_esik.value.strip())
            if esik < 1:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Tepki sayısı geçerli bir sayı olmalı.", ephemeral=True)

        # Süre doğrula
        sure_sn = parse_sure(self.sure.value)
        if sure_sn is None:
            return await interaction.response.send_message("❌ Süre formatı yanlış. Örn: `1h`, `2d`, `30m`", ephemeral=True)

        kanal = interaction.channel
        kelime = random_kelime()

        # Drop embed
        embed = discord.Embed(
            title="🎁 DROP SPAWNED!",
            description=(
                f"**Ödül:** `{self.odul.value}`\n\n"
                f"Bu mesaja **{esik} tepki** geldiğinde kanal açılacak ve drop başlayacak!\n"
                f"⏰ **Süre:** `{self.sure.value}` — süre biterse drop iptal olur.\n\n"
                f"Tepki atmak için 👇"
            ),
            color=0xFFD700
        )
        embed.set_footer(text="İlk tepkiyi at, dropu kazan!")

        await interaction.response.send_message("✅ Drop oluşturuldu!", ephemeral=True)
        msg = await kanal.send(embed=embed)
        await msg.add_reaction("🎁")

        # Oturumu kaydet
        drop_sessions[kanal.id] = {
            "msg_id": msg.id,
            "odul": self.odul.value,
            "esik": esik,
            "email": self.email.value,
            "sifre": self.sifre.value,
            "kelime": kelime,
            "aktif": True,
            "basladi": False,
            "kazanan_id": None,
            "kuran_id": interaction.user.id,
        }

        # Süre bitiminde iptal task'ı
        async def iptal_task():
            await asyncio.sleep(sure_sn)
            s = drop_sessions.get(kanal.id)
            if s and s["aktif"] and not s["basladi"]:
                s["aktif"] = False
                iptal_embed = discord.Embed(
                    description="❌ Drop süresi doldu ve kimse kazanamadı.",
                    color=0xED4245
                )
                try:
                    await kanal.send(embed=iptal_embed)
                    drop_msg = await kanal.fetch_message(s["msg_id"])
                    await drop_msg.edit(embed=discord.Embed(
                        title="🎁 DROP — İPTAL",
                        description="Süre doldu. Drop iptal edildi.",
                        color=0xED4245
                    ))
                except:
                    pass
                drop_sessions.pop(kanal.id, None)

        bot.loop.create_task(iptal_task())


class DropKurulumView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🎁 Drop Kur", style=discord.ButtonStyle.success)
    async def kur_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DropKurulumModal())


@bot.command(name="drop")
@is_admin()
async def drop_cmd(ctx):
    """Drop başlatmak için buton gönderir."""
    embed = discord.Embed(
        title="🎁 Drop Sistemi",
        description="Aşağıdaki butona tıklayarak drop ayarlarını doldur.",
        color=0x5865F2
    )
    await ctx.send(embed=embed, view=DropKurulumView())
    try:
        await ctx.message.delete()
    except:
        pass


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Bot kendi tepkisini sayma
    if payload.user_id == bot.user.id:
        return

    s = drop_sessions.get(payload.channel_id)
    if not s or not s["aktif"] or s["basladi"]:
        return

    if str(payload.emoji) != "🎁":
        return

    kanal = bot.get_channel(payload.channel_id)
    if not kanal:
        return

    try:
        msg = await kanal.fetch_message(s["msg_id"])
    except:
        return

    # Tepki sayısını say (botu çıkar)
    tepki_sayisi = 0
    for r in msg.reactions:
        if str(r.emoji) == "🎁":
            tepki_sayisi = r.count - 1  # bot kendi tepkisini çıkar
            break

    if tepki_sayisi >= s["esik"]:
        s["basladi"] = True

        # Kanalı kilitle
        guild = kanal.guild
        await kanal.set_permissions(guild.default_role, send_messages=False)

        kelime = s["kelime"]

        # Drop başladı embed
        basladi_embed = discord.Embed(
            title="🔓 DROP BAŞLADI!",
            description=(
                f"**Ödül:** `{s['odul']}`\n\n"
                f"Kanal **{tepki_sayisi} tepki** ile açıldı!\n\n"
                f"🎯 **İlk yazan kazanır!**\n"
                f"Yazman gereken kelime: **`{kelime}`**"
            ),
            color=0x57F287
        )
        basladi_embed.set_footer(text="Hızlı ol! İlk yazan kazanır.")
        await kanal.set_permissions(guild.default_role, send_messages=True)
        await kanal.send(embed=basladi_embed)

        # İlk mesajı bekle
        def check(m):
            return m.channel.id == kanal.id and not m.author.bot and m.content.strip().lower() == kelime.lower()

        try:
            kazanan_msg = await bot.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            s["aktif"] = False
            await kanal.send(embed=discord.Embed(
                description="❌ 5 dakika içinde kimse doğru kelimeyi yazamadı. Drop iptal.",
                color=0xED4245
            ))
            await kanal.set_permissions(guild.default_role, send_messages=False)
            drop_sessions.pop(kanal.id, None)
            return

        kazanan = kazanan_msg.author
        s["aktif"] = False
        s["kazanan_id"] = kazanan.id

        # Kanalı kilitle
        await kanal.set_permissions(guild.default_role, send_messages=False)

        # Kazanan embed (kanala)
        kazandi_embed = discord.Embed(
            title="🏆 Drop Kazanıldı!",
            description=(
                f"🎉 {kazanan.mention} dropu kazandı!\n\n"
                f"**Ödül:** `{s['odul']}`\n"
                f"Bilgiler DM'den gönderildi."
            ),
            color=0xFFD700
        )
        await kanal.send(embed=kazandi_embed)

        # DM gönder
        dm_embed = discord.Embed(
            title="🎁 Drop Kazandın!",
            description=(
                f"Tebrikler! **{s['odul']}** dropunu kazandın.\n\n"
                f"📧 **E-posta:** `{s['email']}`\n"
                f"🔑 **Şifre:** `{s['sifre']}`\n\n"
                f"Herhangi bir sorun için sunucudan ticket aç."
            ),
            color=0xFFD700
        )
        try:
            await kazanan.send(embed=dm_embed)
        except discord.Forbidden:
            await kanal.send(f"⚠️ {kazanan.mention} DM'leri kapalı, bilgileri ticket üzerinden ilet.")

        drop_sessions.pop(kanal.id, None)



# ──────────────────────────────────────────────
#  BAKİYE SİSTEMİ
# ──────────────────────────────────────────────

def get_bakiye(uid: str) -> float:
    data = load_data()
    return data.get("bakiyeler", {}).get(uid, 0.0)

def set_bakiye(uid: str, miktar: float):
    data = load_data()
    if "bakiyeler" not in data:
        data["bakiyeler"] = {}
    data["bakiyeler"][uid] = round(miktar, 2)
    save_data(data)


@bot.command(name="bakiyem")
async def bakiyem_cmd(ctx):
    uid = str(ctx.author.id)
    bakiye = get_bakiye(uid)
    embed = discord.Embed(
        title="💰 Bakiyem",
        color=0xFFD700
    )
    embed.add_field(name="Kullanıcı", value=ctx.author.mention, inline=False)
    embed.add_field(name="Bakiye",    value=f"**{bakiye} ₺**",   inline=False)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)


class AdminParaEkleModal(discord.ui.Modal, title="💸 Para Ekle"):
    user_id = discord.ui.TextInput(label="Kullanıcı ID", placeholder="123456789012345678")
    miktar  = discord.ui.TextInput(label="Miktar (₺)",   placeholder="100")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid  = self.user_id.value.strip()
            mikt = float(self.miktar.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Geçersiz değer.", ephemeral=True)

        yeni = get_bakiye(uid) + mikt
        set_bakiye(uid, yeni)

        member = interaction.guild.get_member(int(uid))
        isim   = member.mention if member else f"`{uid}`"

        embed = discord.Embed(title="✅ Para Eklendi", color=0x57F287)
        embed.add_field(name="Kullanıcı", value=isim,           inline=True)
        embed.add_field(name="Eklenen",   value=f"+{mikt} ₺",   inline=True)
        embed.add_field(name="Yeni Bakiye", value=f"{yeni} ₺",  inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(interaction.guild, f"💸 Para eklendi | {isim} | +{mikt} ₺ | Yeni: {yeni} ₺ | Yetkili: {interaction.user}")


class AdminParaSilModal(discord.ui.Modal, title="🗑️ Para Sil"):
    user_id = discord.ui.TextInput(label="Kullanıcı ID", placeholder="123456789012345678")
    miktar  = discord.ui.TextInput(label="Miktar (₺)",   placeholder="50")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid  = self.user_id.value.strip()
            mikt = float(self.miktar.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Geçersiz değer.", ephemeral=True)

        mevcut = get_bakiye(uid)
        yeni   = max(0.0, mevcut - mikt)
        set_bakiye(uid, yeni)

        member = interaction.guild.get_member(int(uid))
        isim   = member.mention if member else f"`{uid}`"

        embed = discord.Embed(title="🗑️ Para Silindi", color=0xFF4444)
        embed.add_field(name="Kullanıcı", value=isim,           inline=True)
        embed.add_field(name="Silinen",   value=f"-{mikt} ₺",   inline=True)
        embed.add_field(name="Yeni Bakiye", value=f"{yeni} ₺",  inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(interaction.guild, f"🗑️ Para silindi | {isim} | -{mikt} ₺ | Yeni: {yeni} ₺ | Yetkili: {interaction.user}")


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💸 Para Ekle", style=discord.ButtonStyle.success, custom_id="admin_para_ekle")
    async def para_ekle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminParaEkleModal())

    @discord.ui.button(label="🗑️ Para Sil", style=discord.ButtonStyle.danger, custom_id="admin_para_sil")
    async def para_sil(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminParaSilModal())


@bot.command(name="adminpanel")
@is_admin()
async def adminpanel_cmd(ctx):
    embed = discord.Embed(
        title="⚙️ Admin Panel",
        description="Bakiye yönetimi için aşağıdaki butonları kullan.",
        color=0x5865F2
    )
    await ctx.send(embed=embed, view=AdminPanelView())
    try:
        await ctx.message.delete()
    except:
        pass


bot.run(TOKEN)
