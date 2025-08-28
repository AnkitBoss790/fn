import os
import json
import time
import asyncio
from typing import Dict, Any, Optional, List

import discord
from discord.ext import commands
import requests

# -----------------------------
# CONFIG
# -----------------------------
PREFIX = "*"
BOT_VERSION = "27.6v"
MADE_BY = "Gamerzhacker"

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_DISCORD_BOT_TOKEN")

# Pterodactyl Application API (Admin key)
PANEL_URL = os.getenv("PANEL_URL", "https://panel.example.com")  # no trailing slash
PANEL_API_KEY = os.getenv("PANEL_API_KEY", "PTRO_APP_KEY")       # Application key (not client key)
PANEL_NODE_ID = int(os.getenv("PANEL_NODE_ID", "1"))             # default node id
DEFAULT_ALLOCATION_ID = os.getenv("DEFAULT_ALLOCATION_ID")        # optional fallback

# Optional: CDN image for *plans (your screenshot URL)
PLANS_IMAGE_URL = os.getenv("PLANS_IMAGE_URL", "")

# File to persist data
DATA_FILE = "data.json"

# Roles required to use admin commands (IDs or names)
ADMIN_ROLE_NAMES = {"Admin", "Owner", "Management", "Node"}

# Invite tiers (from your screenshots)
TIERS = [
    {"name": "Basic",    "inv": 0,  "ram": 4096,  "cpu": 150, "disk": 10000},
    {"name": "Advanced", "inv": 4,  "ram": 6144,  "cpu": 200, "disk": 15000},
    {"name": "Pro",      "inv": 6,  "ram": 7168,  "cpu": 230, "disk": 20000},
    {"name": "Premium",  "inv": 8,  "ram": 9216,  "cpu": 270, "disk": 25000},
    {"name": "Elite",    "inv": 15, "ram": 12288, "cpu": 320, "disk": 30000},
    {"name": "Ultimate", "inv": 20, "ram": 16384, "cpu": 400, "disk": 35000},
]

# -----------------------------
# Extended Egg Catalog (adjust IDs & startup for your panel eggs)
# -----------------------------
EGG_CATALOG: Dict[str, Dict[str, Any]] = {
    # Minecraft family
    "minecraft_paper": {
        "display": "Minecraft: Paper",
        "nest_id": 1,
        "egg_id": 1,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
        "environment": {
            "SERVER_JARFILE": "server.jar",
            "BUILD_NUMBER": "1",
            "VERSION": "latest",
            "EULA": "TRUE"
        }
    },
    "minecraft_vanilla": {
        "display": "Minecraft: Vanilla",
        "nest_id": 1,
        "egg_id": 2,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar",
        "environment": {"EULA": "TRUE", "BUILD_NUMBER": "1"}
    },
    "minecraft_forge": {
        "display": "Minecraft: Forge",
        "nest_id": 1,
        "egg_id": 3,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar forge-{{VERSION}}.jar",
        "environment": {"SERVER_JARFILE": "server.jar", "VERSION": "1.20.1", "BUILD_NUMBER": "1", "EULA": "TRUE"}
    },
    "minecraft_fabric": {
        "display": "Minecraft: Fabric",
        "nest_id": 1,
        "egg_id": 4,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar fabric-server-launch.jar",
        "environment": {"EULA": "TRUE", "BUILD_NUMBER": "1"}
    },
    "minecraft_bungeecord": {
        "display": "Minecraft: Bungeecord",
        "nest_id": 2,
        "egg_id": 5,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar BungeeCord.jar",
        "environment": {"BUILD_NUMBER": "1"}
    },
    "minecraft_waterfall": {
        "display": "Minecraft: Waterfall",
        "nest_id": 2,
        "egg_id": 6,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar Waterfall.jar",
        "environment": {"BUILD_NUMBER": "1"}
    },
    # Apps
    "nodejs": {
        "display": "Node.js App",
        "nest_id": 5,
        "egg_id": 7,
        "docker_image": "ghcr.io/pterodactyl/yolks:nodejs_18",
        "startup": "npm start",
        "environment": {"STARTUP_FILE": "index.js"}
    },
    "python": {
        "display": "Python App",
        "nest_id": 5,
        "egg_id": 8,
        "docker_image": "ghcr.io/pterodactyl/yolks:python_3.11",
        "startup": "python3 main.py",
        "environment": {"STARTUP_FILE": "main.py"}
    },
    # Popular games
    "fivem": {
        "display": "GTA FiveM",
        "nest_id": 3,
        "egg_id": 9,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "./run.sh +exec server.cfg",
        "environment": {"BUILD_NUMBER": "1"}
    },
    "rust": {
        "display": "Rust Server",
        "nest_id": 4,
        "egg_id": 10,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "./RustDedicated -batchmode -nographics -server.ip 0.0.0.0 -server.port {{SERVER_PORT}}",
        "environment": {}
    },
    "csgo": {
        "display": "CS:GO Server",
        "nest_id": 4,
        "egg_id": 11,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "./srcds_run -game csgo -console -port {{SERVER_PORT}} +map de_dust2",
        "environment": {}
    },
    # Databases
    "mariadb": {
        "display": "MariaDB",
        "nest_id": 7,
        "egg_id": 12,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "mysqld --defaults-file=/mnt/server/my.cnf",
        "environment": {"MYSQL_ROOT_PASSWORD": "root"}
    },
    "redis": {
        "display": "Redis",
        "nest_id": 7,
        "egg_id": 13,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "redis-server /mnt/server/redis.conf",
        "environment": {}
    },
}

# -----------------------------
# Persistence helpers
# -----------------------------

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {"admins": [], "invites": {}, "panel_users": {}, "user_client_keys": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


data = load_data()

# -----------------------------
# Discord bot
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# -----------------------------
# Utils
# -----------------------------

HEADERS_APP = {"Authorization": f"Bearer {PANEL_API_KEY}", "Accept": "Application/vnd.pterodactyl.v1+json", "Content-Type": "application/json"}


def app_url(path: str) -> str:
    return f"{PANEL_URL}/api/application{path}"


def client_url(path: str) -> str:
    return f"{PANEL_URL}/api/client{path}"


def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    names = {r.name for r in getattr(member, 'roles', [])}
    return any(n in names for n in ADMIN_ROLE_NAMES) or (str(member.id) in data.get("admins", []))


async def ask(ctx: commands.Context, prompt: str, timeout: int = 45, check_numeric: bool = False, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Optional[str]:
    await ctx.send(prompt)
    def _check(m: discord.Message):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        msg = await bot.wait_for("message", check=_check, timeout=timeout)
        content = msg.content.strip()
        if check_numeric:
            if not content.isdigit():
                await ctx.send("Please send a number.")
                return None
            val = int(content)
            if min_val is not None and val < min_val:
                await ctx.send(f"Minimum is {min_val}.")
                return None
            if max_val is not None and val > max_val:
                await ctx.send(f"Maximum is {max_val}.")
                return None
        return content
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return None

# -----------------------------
# Pterodactyl API helpers
# -----------------------------

def get_free_allocation(node_id: int) -> Optional[int]:
    try:
        r = requests.get(app_url(f"/nodes/{node_id}/allocations"), headers=HEADERS_APP, timeout=20)
        r.raise_for_status()
        dataj = r.json()
        # v1 returns list under data -> attributes
        for item in dataj.get("data", []):
            attr = item.get("attributes", {})
            if not attr.get("assigned", False):
                return int(attr["id"])
        return None
    except Exception:
        return None


def create_panel_user(username: str, email: str, first_name: str = "User", last_name: str = "Bot") -> Optional[int]:
    payload = {
        "email": email,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "password": None
    }
    try:
        r = requests.post(app_url("/users"), headers=HEADERS_APP, json=payload, timeout=30)
        if r.status_code == 422 and "email" in r.text:
            # already exists, fetch id
            u = requests.get(app_url(f"/users?filter[email]={email}"), headers=HEADERS_APP, timeout=20)
            if u.ok and u.json().get("data"):
                return u.json()["data"][0]["attributes"]["id"]
        r.raise_for_status()
        return r.json()["attributes"]["id"]
    except Exception as e:
        print("create_user error", e)
        return None


def delete_panel_user(user_id: int) -> bool:
    try:
        r = requests.delete(app_url(f"/users/{user_id}"), headers=HEADERS_APP, timeout=20)
        return r.status_code in (204, 200)
    except Exception:
        return False


def create_server(name: str, owner_id: int, egg_key: str, memory: int, cpu: int, disk: int, allocation_id: Optional[int]) -> Optional[str]:
    egg = EGG_CATALOG[egg_key]
    # If allocation not provided, attempt auto-pick
    if allocation_id is None:
        allocation_id = get_free_allocation(PANEL_NODE_ID)
    if allocation_id is None and DEFAULT_ALLOCATION_ID:
        allocation_id = int(DEFAULT_ALLOCATION_ID)

    payload = {
        "name": name,
        "user": owner_id,
        "nest": egg["nest_id"],
        "egg": egg["egg_id"],
        "docker_image": egg["docker_image"],
        "startup": egg["startup"],
        "limits": {"memory": memory, "swap": 0, "disk": disk, "io": 500, "cpu": cpu},
        "feature_limits": {"databases": 1, "allocations": 1, "backups": 1},
        "allocation": {"default": allocation_id},
        "environment": egg.get("environment", {})
    }

    r = requests.post(app_url("/servers"), headers=HEADERS_APP, json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Panel error {r.status_code}: {r.text}")
    return r.json()["attributes"]["identifier"]


def delete_server(server_id: int) -> bool:
    try:
        r = requests.delete(app_url(f"/servers/{server_id}"), headers=HEADERS_APP, timeout=25)
        return r.status_code in (204, 200)
    except Exception:
        return False


def list_servers() -> List[Dict[str, Any]]:
    r = requests.get(app_url("/servers"), headers=HEADERS_APP, timeout=30)
    if not r.ok:
        return []
    out = []
    for d in r.json().get("data", []):
        a = d.get("attributes", {})
        out.append({
            "id": a.get("id"),
            "name": a.get("name"),
            "identifier": a.get("identifier"),
            "limits": a.get("limits", {})
        })
    return out

# -----------------------------
# Command Helpers
# -----------------------------

def get_user_invites(uid: int) -> int:
    return int(data.get("invites", {}).get(str(uid), 0))


def set_user_invites(uid: int, amount: int):
    data.setdefault("invites", {})[str(uid)] = int(amount)
    save_data(data)


def add_user_invites(uid: int, amount: int):
    set_user_invites(uid, get_user_invites(uid) + int(amount))


def remove_user_invites(uid: int, amount: int):
    set_user_invites(uid, max(0, get_user_invites(uid) - int(amount)))


def tier_for_invites(inv_count: int) -> Dict[str, Any]:
    best = TIERS[0]
    for t in TIERS:
        if inv_count >= t["inv"]:
            best = t
    return best

# -----------------------------
# EVENTS
# -----------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | Prefix: {PREFIX}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {BOT_VERSION}"))

# -----------------------------
# HELP
# -----------------------------

@bot.command(name="help")
async def _help(ctx: commands.Context):
    em = discord.Embed(title="Pterodactyl Manager — Help", color=discord.Color.blurple())
    em.description = (
        "**User Commands**\n"
        f"`{PREFIX}plans` – Show invite/boost plans.\n"
        f"`{PREFIX}i [@user]` – Show your/other invites & tier.\n"
        f"`{PREFIX}register` – Link or create your panel account.\n"
        f"`{PREFIX}create` – Create a server (RAM/CPU/Disk only).\n"
        f"`{PREFIX}upgrade` – Show current tier limits.\n"
        f"`{PREFIX}manage` – Manage using your client API key (power, files, IP, SFTP).\n"
        f"`{PREFIX}serverinfo` – Show this Discord server info.\n"
        f"`{PREFIX}botinfo` – Bot version & credits.\n"
        f"`{PREFIX}clear <amount>` – Clear messages (needs Manage Msgs).\n\n"
        "**Admin Commands**\n"
        f"`{PREFIX}admin add_i @user <amount>` – Add invites.\n"
        f"`{PREFIX}admin remove_i @user <amount>` – Remove invites.\n"
        f"`{PREFIX}admin add_a @user` – Add as bot admin.\n"
        f"`{PREFIX}admin rm_a @user` – Remove admin.\n"
        f"`{PREFIX}admin create_a @user <email>` – Create/link panel account.\n"
        f"`{PREFIX}admin rm_ac @user` – Delete user's panel account & servers.\n"
        f"`{PREFIX}admin create_s <name> <owner_email>` – Create server via prompts.\n"
        f"`{PREFIX}admin delete_s <server_id>` – Delete server.\n"
        f"`{PREFIX}admin serverlist` – List servers with limits.\n"
        f"`{PREFIX}admin newmsg <channel_id> <text>` – Send custom message.\n"
        f"`{PREFIX}admin lock` / `{PREFIX}admin unlock` – Lock/Unlock channel.\n"
        f"`{PREFIX}node` – Show node allocation status.\n"
    )
    await ctx.send(embed=em)

# -----------------------------
# PLANS & INVITES
# -----------------------------

@bot.command()
async def plans(ctx: commands.Context):
    em = discord.Embed(title="Free Plans", color=discord.Color.gold())
    desc = []
    for t in TIERS[1:]:
        desc.append(f"**{t['inv']} Invites**\nRAM: {t['ram']//1024 if t['ram']>=1024 else t['ram']} {'GB' if t['ram']>=1024 else 'MB'}\nCPU: {t['cpu']}%\nDisk: {t['disk']//1000} GB\nRole: {t['name']}")
    em.description = "\n\n".join(desc)
    if PLANS_IMAGE_URL:
        em.set_image(url=PLANS_IMAGE_URL)
    await ctx.send(embed=em)

@bot.command(name="i")
async def invites_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    inv = get_user_invites(member.id)
    tier = tier_for_invites(inv)
    em = discord.Embed(title=f"Invite Stats – {member.display_name}", color=discord.Color.teal())
    em.add_field(name="Total Invites", value=str(inv))
    em.add_field(name="Current Tier", value=tier['name'])
    em.add_field(name="Next Tier", value=f"{tier['name']}" if tier==TIERS[-1] else f"{[t for t in TIERS if t['inv']>tier['inv']][0]['name']} at {[t for t in TIERS if t['inv']>tier['inv']][0]['inv']} invites")
    em.add_field(name="RAM", value=f"{tier['ram']//1024 if tier['ram']>=1024 else tier['ram']} {'GB' if tier['ram']>=1024 else 'MB'}")
    em.add_field(name="CPU", value=f"{tier['cpu']}%")
    em.add_field(name="Disk", value=f"{tier['disk']//1000} GB")
    await ctx.send(embed=em)

@bot.command()
async def upgrade(ctx: commands.Context):
    inv = get_user_invites(ctx.author.id)
    tier = tier_for_invites(inv)
    em = discord.Embed(title="Your Tier Benefits", color=discord.Color.green())
    em.add_field(name="Tier", value=tier['name'])
    em.add_field(name="RAM", value=f"{tier['ram']//1024 if tier['ram']>=1024 else tier['ram']} {'GB' if tier['ram']>=1024 else 'MB'}")
    em.add_field(name="CPU", value=f"{tier['cpu']}%")
    em.add_field(name="Disk", value=f"{tier['disk']//1000} GB")
    await ctx.send(embed=em)

# -----------------------------
# REGISTER / PANEL ACCOUNT LINK
# -----------------------------

@bot.command()
async def register(ctx: commands.Context):
    """User links (or creates) panel account under their Discord user."""
    user_id = str(ctx.author.id)
    if user_id in data.get("panel_users", {}):
        await ctx.send(f"Already linked: `{data['panel_users'][user_id]}`")
        return
    email = await ask(ctx, "Enter your panel email:")
    if not email:
        return
    username = f"user{ctx.author.id}"[:24]
    uid = create_panel_user(username=username, email=email, first_name=ctx.author.display_name[:20], last_name="Discord")
    if not uid:
        await ctx.send("Failed to create/link panel user. Ask admin.")
        return
    data.setdefault("panel_users", {})[user_id] = uid
    save_data(data)
    await ctx.send(f"Linked! Panel user id: `{uid}`")

# -----------------------------
# CREATE (Interactive) — RAM/CPU/DISK ONLY
# -----------------------------

@bot.command()
async def create(ctx: commands.Context):
    # Ensure user has panel account
    user_id = str(ctx.author.id)
    if user_id not in data.get("panel_users", {}):
        await ctx.send(f"Use `{PREFIX}register` first to link your panel account.")
        return
    owner_id = data["panel_users"][user_id]

    # Choose Egg
    keys = list(EGG_CATALOG.keys())
    menu = "\n".join([f"{i+1}. {EGG_CATALOG[k]['display']}" for i, k in enumerate(keys)])
    choice = await ask(ctx, f"Select server type:\n{menu}\n\nReply with number (1-{len(keys)})", check_numeric=True, min_val=1, max_val=len(keys))
    if not choice:
        return
    egg_key = keys[int(choice) - 1]

    # Server name
    name = await ask(ctx, "Enter Server Name (max 40 chars):")
    if not name:
        return
    name = name[:40]

    # Limits from user's tier
    user_inv = get_user_invites(ctx.author.id)
    tier = tier_for_invites(user_inv)

    max_ram = tier['ram']  # in MB
    max_cpu = tier['cpu']  # %
    max_disk = tier['disk']  # in MB

    ram = await ask(ctx, f"Enter RAM MB (max {max_ram}):", check_numeric=True, min_val=256, max_val=max_ram)
    if not ram:
        return
    cpu = await ask(ctx, f"Enter CPU % (max {max_cpu}):", check_numeric=True, min_val=10, max_val=max_cpu)
    if not cpu:
        return
    disk = await ask(ctx, f"Enter Disk MB (min 1000, max {max_disk}):", check_numeric=True, min_val=1000, max_val=max_disk)
    if not disk:
        return

    await ctx.send("Finding free allocation…")
    alloc_id = get_free_allocation(PANEL_NODE_ID)
    if not alloc_id and DEFAULT_ALLOCATION_ID:
        alloc_id = int(DEFAULT_ALLOCATION_ID)
    if not alloc_id:
        await ctx.send("No free allocation found on node. Ask admin to add ports.")
        return

    try:
        identifier = create_server(
            name=name,
            owner_id=owner_id,
            egg_key=egg_key,
            memory=int(ram), cpu=int(cpu), disk=int(disk),
            allocation_id=alloc_id
        )
    except Exception as e:
        await ctx.send(f"❌ Panel error: `{e}`")
        return

    em = discord.Embed(title="Server created!", color=discord.Color.green())
    em.add_field(name="Name", value=name, inline=False)
    em.add_field(name="Egg", value=EGG_CATALOG[egg_key]["display"], inline=False)
    em.add_field(name="RAM/CPU/Disk", value=f"{ram}MB / {cpu}% / {int(disk)//1000}GB", inline=False)
    em.add_field(name="Identifier", value=identifier, inline=False)
    await ctx.send(embed=em)

# -----------------------------
# ADMIN COMMANDS
# -----------------------------

@bot.group(name="admin", invoke_without_command=True)
async def admin_group(ctx: commands.Context):
    await ctx.send(f"Use `{PREFIX}help` to see admin subcommands.")

@admin_group.command(name="add_i")
async def admin_add_i(ctx: commands.Context, member: discord.Member, amount: int):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    add_user_invites(member.id, amount)
    await ctx.send(f"Added {amount} invites to {member.mention}. Total: {get_user_invites(member.id)}")

@admin_group.command(name="remove_i")
async def admin_remove_i(ctx: commands.Context, member: discord.Member, amount: int):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    remove_user_invites(member.id, amount)
    await ctx.send(f"Removed {amount} invites from {member.mention}. Total: {get_user_invites(member.id)}")

@admin_group.command(name="add_a")
async def admin_add_a(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    admins = set(data.get("admins", []))
    admins.add(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"{member.mention} is now a bot admin.")

@admin_group.command(name="rm_a")
async def admin_rm_a(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    admins = set(data.get("admins", []))
    admins.discard(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"Removed bot admin: {member.mention}")

@admin_group.command(name="create_a")
async def admin_create_a(ctx: commands.Context, member: discord.Member, email: str):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    uid = create_panel_user(username=f"user{member.id}"[:24], email=email, first_name=member.display_name[:20], last_name="Discord")
    if not uid:
        return await ctx.send("Failed to create panel user.")
    data.setdefault("panel_users", {})[str(member.id)] = uid
    save_data(data)
    await ctx.send(f"Panel user created & linked. ID: `{uid}`")

@admin_group.command(name="rm_ac")
async def admin_rm_ac(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    uid = data.get("panel_users", {}).get(str(member.id))
    if not uid:
        return await ctx.send("No linked panel account.")
    # delete all servers owned by user
    servers = list_servers()
    for s in servers:
        # We need to fetch server owner id; application list doesn't always include owner.
        # Fetch one-by-one for safety
        r = requests.get(app_url(f"/servers/{s['id']}"), headers=HEADERS_APP, timeout=20)
        if r.ok and r.json().get("attributes", {}).get("user") == uid:
            delete_server(s['id'])
            await asyncio.sleep(0.3)
    ok = delete_panel_user(uid)
    if ok:
        data["panel_users"].pop(str(member.id), None)
        save_data(data)
        await ctx.send("Deleted user's panel account and servers.")
    else:
        await ctx.send("Failed to delete panel user.")

@admin_group.command(name="create_s")
async def admin_create_s(ctx: commands.Context, name: str, owner_email: str):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    # find or create owner
    uid = create_panel_user(username=f"staff{int(time.time())}"[-6:], email=owner_email, first_name="Owner", last_name="Auto")
    if not uid:
        return await ctx.send("Could not resolve owner user.")

    # pick egg interactively
    keys = list(EGG_CATALOG.keys())
    menu = "\n".join([f"{i+1}. {EGG_CATALOG[k]['display']}" for i, k in enumerate(keys)])
    choice = await ask(ctx, f"Select server type:\n{menu}\n\nReply with number (1-{len(keys)})", check_numeric=True, min_val=1, max_val=len(keys))
    if not choice:
        return
    egg_key = keys[int(choice) - 1]

    ram = await ask(ctx, "Enter RAM MB (min 512, max 65536):", check_numeric=True, min_val=512, max_val=65536)
    if not ram:
        return
    cpu = await ask(ctx, "Enter CPU % (min 10, max 1000):", check_numeric=True, min_val=10, max_val=1000)
    if not cpu:
        return
    disk = await ask(ctx, "Enter Disk MB (min 1000, max 2097152)", check_numeric=True, min_val=1000, max_val=2097152)
    if not disk:
        return

    alloc_id = get_free_allocation(PANEL_NODE_ID)
    if not alloc_id and DEFAULT_ALLOCATION_ID:
        alloc_id = int(DEFAULT_ALLOCATION_ID)
    if not alloc_id:
        return await ctx.send("No free allocation available.")

    try:
        identifier = create_server(name=name, owner_id=uid, egg_key=egg_key, memory=int(ram), cpu=int(cpu), disk=int(disk), allocation_id=alloc_id)
    except Exception as e:
        return await ctx.send(f"❌ {e}")

    await ctx.send(f"✅ Server created: **{name}** (`{identifier}`)")

@admin_group.command(name="delete_s")
async def admin_delete_s(ctx: commands.Context, server_id: int):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    ok = delete_server(server_id)
    await ctx.send("Deleted." if ok else "Failed to delete.")

@admin_group.command(name="serverlist")
async def admin_serverlist(ctx: commands.Context):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    servers = list_servers()
    if not servers:
        return await ctx.send("No servers or API error.")
    lines = [f"ID {s['id']} • {s['name']} • RAM {s['limits'].get('memory','?')}MB CPU {s['limits'].get('cpu','?')}% DISK {s['limits'].get('disk','?')}MB" for s in servers]
    chunks = ["\n".join(lines[i:i+15]) for i in range(0, len(lines), 15)]
    for ch in chunks:
        await ctx.send(f"```
{ch}
```")

@admin_group.command(name="newmsg")
async def admin_newmsg(ctx: commands.Context, channel_id: int, *, text: str):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    ch = ctx.guild.get_channel(channel_id)
    if not ch:
        return await ctx.send("Channel not found")
    await ch.send(text)
    await ctx.send("Sent.")

@admin_group.command(name="lock")
async def admin_lock(ctx: commands.Context):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Channel locked.")

@admin_group.command(name="unlock")
async def admin_unlock(ctx: commands.Context):
    if not is_admin(ctx.author):
        return await ctx.send("No permission.")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Channel unlocked.")

# -----------------------------
# MODERATION: CLEAR
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx: commands.Context, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"Cleared {amount} messages.")
    await asyncio.sleep(2)
    await msg.delete()

# -----------------------------
# NODE STATUS
# -----------------------------

@bot.command(name="node")
async def node_status(ctx: commands.Context):
    try:
        r = requests.get(app_url(f"/nodes/{PANEL_NODE_ID}"), headers=HEADERS_APP, timeout=15)
        if not r.ok:
            return await ctx.send("API error.")
        a = r.json().get("attributes", {})
        r2 = requests.get(app_url(f"/nodes/{PANEL_NODE_ID}/allocations"), headers=HEADERS_APP, timeout=15)
        free = 0
        total = 0
        if r2.ok:
            for item in r2.json().get("data", []):
                total += 1
                if not item.get("attributes", {}).get("assigned", False):
                    free += 1
        em = discord.Embed(title="Node Status", color=discord.Color.orange())
        em.add_field(name="Name", value=a.get("name", "?"))
        em.add_field(name="FQDN", value=a.get("fqdn", "?"))
        em.add_field(name="Allocations", value=f"{free} free / {total} total")
        em.add_field(name="Maintenance", value=str(a.get("maintenance_mode", False)))
        await ctx.send(embed=em)
    except Exception as e:
        await ctx.send(f"Error: {e}")

# -----------------------------
# SERVERINFO
# -----------------------------

@bot.command()
async def serverinfo(ctx: commands.Context):
    g = ctx.guild
    if not g:
        return await ctx.send("Use in a server.")
    boosts = g.premium_subscription_count or 0
    owner = await g.fetch_owner()
    online = sum(1 for m in g.members if m.status != discord.Status.offline)
    em = discord.Embed(title=g.name, color=discord.Color.brand_green())
    if g.icon:
        em.set_thumbnail(url=g.icon.url)
    em.add_field(name="Owner", value=f"{owner} ({owner.id})", inline=False)
    em.add_field(name="Server ID", value=g.id)
    em.add_field(name="Members", value=g.member_count)
    em.add_field(name="Online", value=online)
    em.add_field(name="Boosts", value=boosts)
    em.add_field(name="Roles", value=len(g.roles))
    em.add_field(name="Region/Locale", value=str(g.preferred_locale))
    em.set_footer(text=f"Bot {BOT_VERSION} • Made by {MADE_BY}")
    await ctx.send(embed=em)

# -----------------------------
# BOTINFO
# -----------------------------

@bot.command()
async def botinfo(ctx: commands.Context):
    em = discord.Embed(title="Bot Info", color=discord.Color.blue())
    em.add_field(name="Version", value=BOT_VERSION)
    em.add_field(name="Made by", value=MADE_BY)
    em.add_field(name="Prefix", value=PREFIX)
    await ctx.send(embed=em)

# -----------------------------
# MANAGE (Client API key based quick controls)
# -----------------------------

@bot.command()
async def manage(ctx: commands.Context):
    await ctx.send("Enter your **Client API Key** from the panel (Account → API):")
    key = await ask(ctx, "Paste key here (won't be shown to others):")
    if not key:
        return
    data.setdefault("user_client_keys", {})[str(ctx.author.id)] = key.strip()
    save_data(data)
    await ctx.send("Saved! Now send server identifier to power control.")

    ident = await ask(ctx, "Enter server **identifier** (short code):")
    if not ident:
        return

    async def power(sig: str):
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "Application/vnd.pterodactyl.v1+json"}
        rr = requests.post(client_url(f"/servers/{ident}/power"), headers=headers, json={"signal": sig}, timeout=15)
        return rr.ok

    await ctx.send("Type one of: start / stop / restart / kill / reinstall / ip / sftp")
    while True:
        cmd = await ask(ctx, ">>")
        if not cmd:
            break
        cmd = cmd.lower()
        if cmd in {"start", "stop", "restart", "kill"}:
            ok = await asyncio.to_thread(power, cmd)
            await ctx.send("✅ Done" if ok else "❌ Failed")
        elif cmd == "reinstall":
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "Application/vnd.pterodactyl.v1+json"}
            rr = requests.post(client_url(f"/servers/{ident}/actions/reinstall"), headers=headers, timeout=20)
            await ctx.send("✅ Reinstall requested" if rr.ok else f"❌ {rr.status_code}")
        elif cmd == "ip":
            headers = {"Authorization": f"Bearer {key}", "Accept": "Application/vnd.pterodactyl.v1+json"}
            rr = requests.get(client_url(f"/servers/{ident}"), headers=headers, timeout=15)
            if rr.ok:
                att = rr.json().get("attributes", {})
                allocations = att.get("relationships", {}).get("allocations", {}).get("data", [])
                if allocations:
                    a = allocations[0]["attributes"]
                    await ctx.send(f"IP: {a.get('ip_alias') or a.get('ip')}:{a.get('port')}")
                else:
                    await ctx.send("No allocation info.")
            else:
                await ctx.send("API error.")
        elif cmd == "sftp":
            headers = {"Authorization": f"Bearer {key}", "Accept": "Application/vnd.pterodactyl.v1+json"}
            rr = requests.get(client_url(f"/servers/{ident}/files/list?directory=/"), headers=headers, timeout=15)
            # Not actually SFTP creds, but we can show host/username
            await ctx.send(f"SFTP Host: {PANEL_URL.replace('https://','').replace('http://','')}\nUsername: {ident}\nPassword: (your panel password)")
        elif cmd in {"exit", "quit"}:
            await ctx.send("Exited manage mode.")
            break
        else:
            await ctx.send("Unknown. Use: start/stop/restart/kill/reinstall/ip/sftp/exit")

# -----------------------------
# RUN
# -----------------------------
bot.run(TOKEN)
