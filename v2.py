# v2.py — All-in-one Discord bot for Pterodactyl (prefix "*")
# pip install discord.py aiohttp

import os, json, asyncio, aiohttp, datetime
from typing import Dict, Any, Optional, List
import discord
from discord.ext import commands

# =========================
# CONFIG (EDIT THESE)
# =========================
BOT_TOKEN = 
PANEL_URL = "https://panel.fluidmc.fun/"
PANEL_API_KEY = "ptla_S47faeE3JcTChMKRllMz6ekGiJQKXQ4jkoXm0Wd550M"
PANEL_NODE_ID = "2"  # node id to pull allocations from
DEFAULT_ALLOCATION_ID = "None"
# Who is allowed to use *admin ... (IDs get persisted too; this is just bootstrap)
BOOTSTRAP_ADMIN_IDS = {2}

# Branding (for *botinfo)
BOT_VERSION = "v2"
MADE_BY = "Gamerzhacker"
SERVER_LOCATION = "India"

# =========================
# BOT SETUP
# =========================
PREFIX = "*"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

DATA_FILE = "v2_data.json"

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {
            "admins": [str(i) for i in BOOTSTRAP_ADMIN_IDS],
            "invites": {},           # user_id -> int
            "client_keys": {},       # user_id -> client api key (for manage)
            "panel_users": {},       # user_id -> panel user id
            "locked_channels": [],   # channel ids
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

data = load_data()

# =========================
# HTTP (Application API)
# =========================
APP_HEADERS = {
    "Authorization": f"Bearer {PANEL_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def app(path: str) -> str:
    return f"{PANEL_URL}/api/application{path}"

async def app_get(session: aiohttp.ClientSession, path: str, **kw):
    async with session.get(app(path), headers=APP_HEADERS, **kw) as r:
        return r

async def app_post(session: aiohttp.ClientSession, path: str, json: dict, **kw):
    async with session.post(app(path), headers=APP_HEADERS, json=json, **kw) as r:
        return r

async def app_delete(session: aiohttp.ClientSession, path: str, **kw):
    async with session.delete(app(path), headers=APP_HEADERS, **kw) as r:
        return r

# =========================
# EGG CATALOG + ENV DEFAULTS
# (update IDs/Images/Startup if your panel differs)
# =========================
DEFAULT_ENV = {
    "SERVER_JARFILE": "server.jar",
    "EULA": "TRUE",
    "VERSION": "latest",
    "BUILD_NUMBER": "latest",
    "SPONGE_VERSION": "stable-7",
    "FORGE_VERSION": "latest",
    "MINECRAFT_VERSION": "latest",
}

EGG_CATALOG: Dict[str, Dict[str, Any]] = {
    "paper": {
        "display": "Minecraft: Paper",
        "nest_id": 1,
        "egg_id": 3,  # you said Paper egg is 3
        "docker_image": "ghcr.io/pterodactyl/yolks:java_21",
        "startup": "java -Xms128M -XX:MaxRAMPercentage=95.0 -Dterminal.jline=false -Dterminal.ansi=true -jar {{SERVER_JARFILE}}",
        "environment": {
            "MINECRAFT_VERSION": "latest",
            "SERVER_JARFILE": "server.jar",
            "BUILD_NUMBER": "latest",
            "EULA": "TRUE"
        }
    },
    "forge": {
        "display": "Minecraft: Forge",
        "nest_id": 1,
        "egg_id": 4,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
        "environment": {
            "SERVER_JARFILE": "server.jar",
            "BUILD_TYPE": "recommended",
            "VERSION": "1.20.1"
        }
    },
    "sponge": {
        "display": "Minecraft: Sponge",
        "nest_id": 1,
        "egg_id": 6,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_11",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
        "environment": {
            "SERVER_JARFILE": "server.jar",
            "SPONGE_VERSION": "stable-7",
            "MINECRAFT_VERSION": "1.12.2",
            "EULA": "TRUE"
        }
    },
    "nodejs": {
        "display": "Node.js",
        "nest_id": 5,
        "egg_id": 16,
        "docker_image": "ghcr.io/pterodactyl/yolks:nodejs_18",
        "startup": "node index.js",
        "environment": {"STARTUP_FILE": "index.js"}
    },
    "python": {
        "display": "Python",
        "nest_id": 5,
        "egg_id": 17,
        "docker_image": "ghcr.io/pterodactyl/yolks:python_3.11",
        "startup": "python3 main.py",
        "environment": {"STARTUP_FILE": "main.py"}
    },
    "mariadb": {
        "display": "MariaDB",
        "nest_id": 7,
        "egg_id": 20,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "mysqld --defaults-file=/mnt/server/my.cnf",
        "environment": {"MYSQL_ROOT_PASSWORD": "root", "MYSQL_DATABASE": "panel"}
    }
}

def build_env_for_egg(egg_key: str) -> Dict[str, Any]:
    env = dict(DEFAULT_ENV)
    env.update(EGG_CATALOG.get(egg_key, {}).get("environment", {}))
    # ensure required defaults never empty
    for k, v in DEFAULT_ENV.items():
        if env.get(k) in (None, ""):
            env[k] = v
    return env

def egg_list_text() -> str:
    return "\n".join([f"- `{k}` → {v['display']}" for k, v in EGG_CATALOG.items()])

# =========================
# ADMIN CHECKS
# =========================
def is_admin(member: discord.Member) -> bool:
    if member is None:
        return False
    try:
        if member.guild_permissions.administrator:
            return True
    except Exception:
        pass
    if str(member.id) in set(data.get("admins", [])):
        return True
    return False

async def require_admin(ctx: commands.Context) -> bool:
    if not is_admin(ctx.author):
        await ctx.reply("🔒 You are not allowed to use admin commands.")
        return False
    return True

# =========================
# PANEL HELPERS
# =========================
async def get_free_allocation() -> Optional[int]:
    async with aiohttp.ClientSession() as s:
        async with app_get(s, f"/nodes/{PANEL_NODE_ID}/allocations") as r:
            if not r.ok:
                return int(DEFAULT_ALLOCATION_ID) if DEFAULT_ALLOCATION_ID else None
            js = await r.json()
            for item in js.get("data", []):
                a = item.get("attributes", {})
                if not a.get("assigned", False):
                    return int(a.get("id"))
    return int(DEFAULT_ALLOCATION_ID) if DEFAULT_ALLOCATION_ID else None

async def create_server_app(name: str, owner_panel_id: int, egg_key: str, memory: int, cpu: int, disk: int, allocation_id: Optional[int] = None) -> (bool, str):
    if egg_key not in EGG_CATALOG:
        return False, "Unknown egg key."
    egg_def = EGG_CATALOG[egg_key]
    alloc = allocation_id or await get_free_allocation()
    if not alloc:
        return False, "No free allocation on node and no DEFAULT_ALLOCATION_ID."

    payload = {
        "name": name,
        "user": owner_panel_id,
        "nest": egg_def["nest_id"],
        "egg": egg_def["egg_id"],
        "docker_image": egg_def["docker_image"],
        "startup": egg_def["startup"],
        "limits": {"memory": memory, "swap": 0, "disk": disk, "io": 500, "cpu": cpu},
        "feature_limits": {"databases": 1, "allocations": 1, "backups": 1},
        "allocation": {"default": alloc},
        "environment": build_env_for_egg(egg_key)
    }

    async with aiohttp.ClientSession() as s:
        async with app_post(s, "/servers", json=payload) as r:
            if r.status == 201:
                js = await r.json()
                ident = js.get("attributes", {}).get("identifier", "unknown")
                return True, f"✅ Server create queued. Identifier: `{ident}`"
            else:
                return False, f"❌ Panel error {r.status}: {await r.text()}"

async def delete_server_app(server_id: int) -> (bool, str):
    async with aiohttp.ClientSession() as s:
        async with app_delete(s, f"/servers/{server_id}") as r:
            if r.status in (204, 200):
                return True, "✅ Server deleted."
            return False, f"❌ Panel error {r.status}: {await r.text()}"

async def list_servers_app() -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        async with app_get(s, "/servers") as r:
            if not r.ok:
                return []
            js = await r.json()
            out = []
            for d in js.get("data", []):
                a = d.get("attributes", {})
                out.append({"id": a.get("id"), "name": a.get("name"), "identifier": a.get("identifier"), "limits": a.get("limits", {})})
            return out

async def node_allocation_stats() -> (int, int):
    free = 0
    total = 0
    async with aiohttp.ClientSession() as s:
        async with app_get(s, f"/nodes/{PANEL_NODE_ID}/allocations") as r:
            if not r.ok:
                return (0, 0)
            js = await r.json()
            for item in js.get("data", []):
                total += 1
                if not item.get("attributes", {}).get("assigned", False):
                    free += 1
    return free, total

# =========================
# CLIENT (Manage) HELPERS
# =========================
def client_headers(client_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {client_key}", "Content-Type": "application/json", "Accept": "application/json"}

async def client_power(client_key: str, ident: str, signal: str) -> (bool, str):
    url = f"{PANEL_URL}/api/client/servers/{ident}/power"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=client_headers(client_key), json={"signal": signal}) as r:
            if r.status in (204, 200):
                return True, f"✅ Power `{signal}` sent."
            return False, f"❌ Client error {r.status}: {await r.text()}"

async def client_reinstall(client_key: str, ident: str) -> (bool, str):
    url = f"{PANEL_URL}/api/client/servers/{ident}/reinstall"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=client_headers(client_key)) as r:
            if r.status in (202, 204, 200):
                return True, "✅ Reinstall queued."
            return False, f"❌ Client error {r.status}: {await r.text()}"

async def client_info(client_key: str, ident: str) -> (bool, str):
    url = f"{PANEL_URL}/api/client/servers/{ident}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=client_headers(client_key)) as r:
            if not r.ok:
                return False, f"❌ Client error {r.status}: {await r.text()}"
            js = await r.json()
            a = js.get("attributes", {})
            sftp = a.get("sftp_details", {})
            ip = sftp.get("ip", "n/a")
            port = sftp.get("port", "n/a")
            return True, f"🧩 Name: **{a.get('name')}**\nID: `{a.get('identifier')}`\nSFTP: `{ip}:{port}`"

# =========================
# EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} — Prefix: {PREFIX}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {BOT_VERSION}"))

# =========================
# HELP
# =========================
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    em = discord.Embed(title="📖 Commands", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    em.add_field(name="👤 User",
                 value=(
                    f"`{PREFIX}create <name> <ramMB> <cpu%> <diskMB> [egg]`\n"
                    f"`{PREFIX}register <email> <password>` (link panel)\n"
                    f"`{PREFIX}i [@user]` (invites/tier)\n"
                    f"`{PREFIX}plans`  `{PREFIX}upgrade`\n"
                    f"`{PREFIX}serverinfo`  `{PREFIX}botinfo`"
                 ),
                 inline=False)
    em.add_field(name="🛠 Manage (Client API)",
                 value=(
                    f"`{PREFIX}manage key <client_api_key>`\n"
                    f"`{PREFIX}manage start|stop|restart|kill <identifier>`\n"
                    f"`{PREFIX}manage reinstall <identifier>`\n"
                    f"`{PREFIX}manage info <identifier>`"
                 ),
                 inline=False)
    em.add_field(name="🧑‍⚖️ Admin",
                 value=(
                    f"`{PREFIX}admin add_i @user <amount>` / `remove_i @user <amount>`\n"
                    f"`{PREFIX}admin add_a @user` / `rm_a @user`\n"
                    f"`{PREFIX}admin create_a @user <email> <password>` (create/link panel user)\n"
                    f"`{PREFIX}admin rm_ac @user` (unlink panel user)\n"
                    f"`{PREFIX}admin create_s <owner_email> <egg> <name> <ram> <cpu> <disk>`\n"
                    f"`{PREFIX}admin delete_s <server_id>`  `serverlist`\n"
                    f"`{PREFIX}admin newmsg <channel_id> <text...>`\n"
                    f"`{PREFIX}admin lock` / `unlock`"
                 ),
                 inline=False)
    em.add_field(name="🧹 Moderation", value=f"`{PREFIX}clear <amount>`", inline=False)
    em.add_field(name="🖥 Node", value=f"`{PREFIX}node` (free/total allocations)", inline=False)
    em.set_footer(text=f"{MADE_BY} • {SERVER_LOCATION} • {BOT_VERSION}")
    await ctx.reply(embed=em, mention_author=False)

# =========================
# INFO / UTILITY
# =========================
@bot.command(name="plans")
async def plans_cmd(ctx):
    plans = [
        ("Basic", 0, 4096, 150, 10000),
        ("Advanced", 4, 6144, 200, 15000),
        ("Pro", 6, 7168, 230, 20000),
        ("Premium", 8, 9216, 270, 25000),
        ("Elite", 15, 12288, 320, 30000),
        ("Ultimate", 20, 16384, 400, 35000),
    ]
    desc = "\n\n".join([f"**{n}** — at {inv} invites\nRAM {ram}MB | CPU {cpu}% | Disk {disk}MB" for (n, inv, ram, cpu, disk) in plans])
    await ctx.reply(embed=discord.Embed(title="Invite Plans", description=desc, color=discord.Color.gold()))

@bot.command(name="i")
async def invites_cmd(ctx, member: Optional[discord.Member] = None):
    target = member or ctx.author
    invites = int(data.get("invites", {}).get(str(target.id), 0))
    tier = "Basic"
    if invites >= 20: tier = "Ultimate"
    elif invites >= 15: tier = "Elite"
    elif invites >= 8: tier = "Premium"
    elif invites >= 6: tier = "Pro"
    elif invites >= 4: tier = "Advanced"
    em = discord.Embed(title=f"Invites — {target.display_name}", color=discord.Color.blue())
    em.add_field(name="Total Invites", value=str(invites))
    em.add_field(name="Tier", value=tier)
    await ctx.reply(embed=em)

@bot.command(name="upgrade")
async def upgrade_cmd(ctx):
    await ctx.reply("DM me to upgrade tiers after reaching invite thresholds. 🎁")

@bot.command(name="serverinfo")
async def serverinfo_cmd(ctx):
    g = ctx.guild
    if not g:
        return await ctx.reply("This command is for servers only.")
    em = discord.Embed(title=f"{g.name}", color=discord.Color.green())
    em.add_field(name="Members", value=str(g.member_count))
    em.add_field(name="Owner", value=str(g.owner))
    em.add_field(name="Created", value=str(g.created_at.date()))
    await ctx.reply(embed=em)

@bot.command(name="botinfo")
async def botinfo_cmd(ctx):
    em = discord.Embed(title="Bot Info", color=discord.Color.purple())
    em.add_field(name="Version", value=BOT_VERSION)
    em.add_field(name="Made By", value=MADE_BY)
    em.add_field(name="Location", value=SERVER_LOCATION)
    await ctx.reply(embed=em)

# =========================
# CREATE (User) — owner must be linked to a panel user id
# =========================
@bot.command(name="register")
async def register_cmd(ctx, email: str, password: str):
    # Using Application API to create/find panel user
    async with aiohttp.ClientSession() as s:
        payload = {
            "email": email, "username": f"u{ctx.author.id}",
            "first_name": ctx.author.name, "last_name": "Discord",
            "password": password
        }
        async with app_post(s, "/users", json=payload) as r:
            if r.status in (200, 201):
                js = await r.json()
                uid = int(js.get("attributes", {}).get("id"))
            elif r.status == 422:
                # maybe exists; try filter
                async with app_get(s, "/users", params={"filter[email]": email}) as rr:
                    if rr.ok:
                        jj = await rr.json()
                        if jj.get("data"):
                            uid = int(jj["data"][0]["attributes"]["id"])
                        else:
                            return await ctx.reply(f"❌ Failed to find/create panel user: {await r.text()}")
                    else:
                        return await ctx.reply(f"❌ Failed to find/create panel user: {await r.text()}")
            else:
                return await ctx.reply(f"❌ Panel error {r.status}: {await r.text()}")

    data.setdefault("panel_users", {})[str(ctx.author.id)] = uid
    save_data(data)
    await ctx.reply(f"✅ Linked your panel user id `{uid}`.")

@bot.command(name="create")
async def create_cmd(ctx, name: str, ram: int, cpu: int, disk: int, egg: str = "paper"):
    uid = data.get("panel_users", {}).get(str(ctx.author.id))
    if not uid:
        return await ctx.reply(f"Link your panel account first: `{PREFIX}register <email> <password>`")
    await ctx.reply("⚙️ Creating your server... please wait.")
    ok, msg = await create_server_app(name=name, owner_panel_id=uid, egg_key=egg, memory=ram, cpu=cpu, disk=disk)
    await ctx.reply(msg)

# =========================
# MANAGE (Client API) — subcommands
# =========================
@bot.group(name="manage", invoke_without_command=True)
async def manage_grp(ctx):
    await ctx.reply(
        f"Use:\n"
        f"`{PREFIX}manage key <client_api_key>`\n"
        f"`{PREFIX}manage start|stop|restart|kill <identifier>`\n"
        f"`{PREFIX}manage reinstall <identifier>`\n"
        f"`{PREFIX}manage info <identifier>`"
    )

@manage_grp.command(name="key")
async def manage_key(ctx, client_api_key: str):
    data.setdefault("client_keys", {})[str(ctx.author.id)] = client_api_key
    save_data(data)
    await ctx.reply("✅ Saved your Client API key (local).")

async def require_client_key(ctx) -> Optional[str]:
    key = data.get("client_keys", {}).get(str(ctx.author.id))
    if not key:
        await ctx.reply(f"Add your key first: `{PREFIX}manage key <client_api_key>`")
        return None
    return key

@manage_grp.command(name="start")
async def manage_start(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_power(key, identifier, "start")
    await ctx.reply(msg)

@manage_grp.command(name="stop")
async def manage_stop(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_power(key, identifier, "stop")
    await ctx.reply(msg)

@manage_grp.command(name="restart")
async def manage_restart(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_power(key, identifier, "restart")
    await ctx.reply(msg)

@manage_grp.command(name="kill")
async def manage_kill(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_power(key, identifier, "kill")
    await ctx.reply(msg)

@manage_grp.command(name="reinstall")
async def manage_reinstall(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_reinstall(key, identifier)
    await ctx.reply(msg)

@manage_grp.command(name="info")
async def manage_info(ctx, identifier: str):
    key = await require_client_key(ctx)
    if not key: return
    ok, msg = await client_info(key, identifier)
    await ctx.reply(msg)

# =========================
# NODE
# =========================
@bot.command(name="node")
async def node_cmd(ctx):
    free, total = await node_allocation_stats()
    await ctx.reply(f"🖥 Node `{PANEL_NODE_ID}` allocations: **{free} free / {total} total**")

# =========================
# MODERATION
# =========================
@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount)
    msg = await ctx.send(f"🧹 Cleared {amount} messages.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass

# =========================
# ADMIN GROUP
# =========================
@bot.group(name="admin", invoke_without_command=True)
async def admin_grp(ctx):
    if not await require_admin(ctx): return
    await ctx.reply("Use subcommands: add_i/remove_i/add_a/rm_a/create_a/rm_ac/create_s/delete_s/serverlist/newmsg/lock/unlock")

# -- invites
@admin_grp.command(name="add_i")
async def admin_add_i(ctx, member: discord.Member, amount: int):
    if not await require_admin(ctx): return
    inv = data.setdefault("invites", {})
    inv[str(member.id)] = int(inv.get(str(member.id), 0)) + amount
    save_data(data)
    await ctx.reply(f"✅ Added {amount} invites to {member.mention} (now {inv[str(member.id)]}).")

@admin_grp.command(name="remove_i")
async def admin_remove_i(ctx, member: discord.Member, amount: int):
    if not await require_admin(ctx): return
    inv = data.setdefault("invites", {})
    inv[str(member.id)] = max(0, int(inv.get(str(member.id), 0)) - amount)
    save_data(data)
    await ctx.reply(f"✅ Removed {amount} invites from {member.mention} (now {inv[str(member.id)]}).")

# -- admins
@admin_grp.command(name="add_a")
async def admin_add_a(ctx, member: discord.Member):
    if not await require_admin(ctx): return
    admins = set(data.get("admins", []))
    admins.add(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.reply(f"✅ {member.mention} is now bot-admin.")

@admin_grp.command(name="rm_a")
async def admin_rm_a(ctx, member: discord.Member):
    if not await require_admin(ctx): return
    admins = set(data.get("admins", []))
    admins.discard(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.reply(f"✅ {member.mention} removed from bot-admins.")

# -- panel user link/unlink
@admin_grp.command(name="create_a")
async def admin_create_account(ctx, member: discord.Member, email: str, password: str):
    if not await require_admin(ctx): return
    async with aiohttp.ClientSession() as s:
        payload = {
            "email": email, "username": f"u{member.id}",
            "first_name": member.name, "last_name": "Discord",
            "password": password
        }
        async with app_post(s, "/users", json=payload) as r:
            uid = None
            if r.status in (200, 201):
                js = await r.json()
                uid = int(js.get("attributes", {}).get("id"))
            elif r.status == 422:
                async with app_get(s, "/users", params={"filter[email]": email}) as rr:
                    if rr.ok:
                        jj = await rr.json()
                        if jj.get("data"):
                            uid = int(jj["data"][0]["attributes"]["id"])
            if not uid:
                return await ctx.reply(f"❌ Failed: {r.status} {await r.text()}")

    data.setdefault("panel_users", {})[str(member.id)] = uid
    save_data(data)
    await ctx.reply(f"✅ Linked panel user `{uid}` to {member.mention}")

@admin_grp.command(name="rm_ac")
async def admin_remove_account_link(ctx, member: discord.Member):
    if not await require_admin(ctx): return
    if data.get("panel_users", {}).pop(str(member.id), None) is None:
        await ctx.reply("Nothing to unlink.")
    else:
        save_data(data)
        await ctx.reply(f"✅ Unlinked panel user from {member.mention}")

# -- server create/delete/list/broadcast
@admin_grp.command(name="create_s")
async def admin_create_s(ctx, owner_email: str, egg: str, name: str, ram: int, cpu: int, disk: int):
    if not await require_admin(ctx): return
    # find owner panel id by email
    async with aiohttp.ClientSession() as s:
        uid = None
        async with app_get(s, "/users", params={"filter[email]": owner_email}) as r:
            if r.ok:
                js = await r.json()
                if js.get("data"):
                    uid = int(js["data"][0]["attributes"]["id"])
    if not uid:
        return await ctx.reply("❌ Owner email not found on panel.")
    await ctx.reply("⚙️ Creating server...")
    ok, msg = await create_server_app(name=name, owner_panel_id=uid, egg_key=egg, memory=ram, cpu=cpu, disk=disk)
    await ctx.reply(msg)

@admin_grp.command(name="delete_s")
async def admin_delete_s(ctx, server_id: int):
    if not await require_admin(ctx): return
    ok, msg = await delete_server_app(server_id)
    await ctx.reply(msg)

@admin_grp.command(name="serverlist")
async def admin_serverlist(ctx):
    if not await require_admin(ctx): return
    servers = await list_servers_app()
    if not servers:
        return await ctx.reply("No servers found.")
    lines = [f"- ID `{s['id']}` | {s['name']} | ident `{s['identifier']}` | RAM {s['limits'].get('memory','?')}MB" for s in servers]
    await ctx.reply("\n".join(lines)[:1900])

@admin_grp.command(name="newmsg")
async def admin_newmsg(ctx, channel_id: int, *, text: str):
    if not await require_admin(ctx): return
    ch = ctx.guild.get_channel(channel_id)
    if not ch:
        return await ctx.reply("Channel not found.")
    await ch.send(text)
    await ctx.reply("✅ Sent.")

# -- lock/unlock current channel
@admin_grp.command(name="lock")
async def admin_lock(ctx):
    if not await require_admin(ctx): return
    ch: discord.TextChannel = ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    ids = set(map(int, data.get("locked_channels", [])))
    ids.add(ch.id)
    data["locked_channels"] = list(map(str, ids))
    save_data(data)
    await ctx.reply("🔒 Locked this channel (muted @everyone).")

@admin_grp.command(name="unlock")
async def admin_unlock(ctx):
    if not await require_admin(ctx): return
    ch: discord.TextChannel = ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    ids = set(map(int, data.get("locked_channels", [])))
    if ch.id in ids:
        ids.remove(ch.id)
    data["locked_channels"] = list(map(str, ids))
    save_data(data)
    await ctx.reply("🔓 Unlocked this channel.")

# =========================
# RUN
# =========================
bot.run(BOT_TOKEN)
