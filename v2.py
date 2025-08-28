import os
import json
import time
import requests
import asyncio
from typing import Dict, Any, Optional, List
import discord
from discord.ext import commands

# =======================
# CONFIG — EDIT THESE
# =======================
BOT_TOKEN = ""
PANEL_URL = "https://panel.fluidmc.fun"
PANEL_API_KEY = "ptla_fy1H6oRdi8fNziZhj3Yk7DrOxXDblOHhaikV35ZtvNW"
PANEL_NODE_ID = "12"
DEFAULT_ALLOCATION_ID = "23"
# Admin role names or IDs that should be allowed (role names; you can also use data["admins"])
ADMIN_ROLE_NAMES = {"Admin", "Owner", "Management"}

# Bot branding
BOT_VERSION = "27.6v"
MADE_BY = "Gamerzhacker"
SERVER_LOCATION = "India"
PLANS_IMAGE_URL = ""  # optional image url used in *plans

# Files
DATA_FILE = "v2_data.json"

# Prefix and intents
PREFIX = "*"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# =======================
# Persistence: load/save data
# =======================
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {"admins": [], "invites": {}, "panel_users": {}, "client_keys": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

data = load_data()

# =======================
# Panel helpers (Application API)
# =======================
APP_HEADERS = {
    "Authorization": f"Bearer {PANEL_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.pterodactyl.v1+json",
}

def app_url(path: str) -> str:
    return f"{PANEL_URL}/api/application{path}"

def app_get(path: str, params: dict = None, timeout=20) -> requests.Response:
    return requests.get(app_url(path), headers=APP_HEADERS, params=params or {}, timeout=timeout)

def app_post(path: str, payload: dict, timeout=60) -> requests.Response:
    return requests.post(app_url(path), headers=APP_HEADERS, json=payload, timeout=timeout)

def app_delete(path: str, timeout=30) -> requests.Response:
    return requests.delete(app_url(path), headers=APP_HEADERS, timeout=timeout)

# Get free allocation on a node (returns allocation id or None)
def get_free_allocation(node_id: int) -> Optional[int]:
    try:
        r = app_get(f"/nodes/{node_id}/allocations")
        r.raise_for_status()
        for item in r.json().get("data", []):
            attr = item.get("attributes", {})
            # Unassigned allocations often have "assigned": False
            if not attr.get("assigned", False):
                # attr id is the allocation record id; some panels expect allocation id or dict — we use id from panel's attributes.id
                return int(attr.get("id"))
        return None
    except Exception:
        return None

# Lookup panel user id by email (Application API)
def get_panel_user_id_by_email(email: str) -> Optional[int]:
    try:
        r = app_get("/users")
        if r.status_code != 200:
            return None
        for item in r.json().get("data", []):
            attr = item.get("attributes", {})
            if attr.get("email", "").lower() == email.lower():
                return int(attr.get("id"))
        return None
    except Exception:
        return None

# Create panel user (Application API)
def create_panel_user(email: str, username: str, password: Optional[str] = None, first_name: str = "Discord", last_name: str = "User") -> Optional[int]:
    payload = {
        "email": email,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        # Panel sometimes requires password or generates one — pass None if API allows it
    }
    if password:
        payload["password"] = password
    try:
        r = app_post("/users", payload)
        # If created, panel returns 201/200
        if r.status_code in (200, 201):
            return int(r.json().get("attributes", {}).get("id"))
        # If already exists, try to query by filter
        if r.status_code == 422:
            rr = app_get("/users", params={"filter[email]": email})
            if rr.ok and rr.json().get("data"):
                return int(rr.json()["data"][0]["attributes"]["id"])
        return None
    except Exception:
        return None

# Delete panel user id (Application API)
def delete_panel_user(user_id: int) -> bool:
    try:
        r = app_delete(f"/users/{user_id}")
        return r.status_code in (200, 204)
    except Exception:
        return False

# Delete server (Application API)
def delete_panel_server(server_id: int) -> bool:
    try:
        r = app_delete(f"/servers/{server_id}")
        return r.status_code in (200, 204)
    except Exception:
        return False

# List servers (Application API) — returns list of dicts with attributes
def list_panel_servers() -> List[Dict[str, Any]]:
    try:
        r = app_get("/servers")
        if not r.ok:
            return []
        out = []
        for d in r.json().get("data", []):
            a = d.get("attributes", {})
            out.append({"id": a.get("id"), "name": a.get("name"), "identifier": a.get("identifier"), "limits": a.get("limits", {})})
        return out
    except Exception:
        return []

# =======================
# Default env + Egg catalog
# =======================
DEFAULT_ENV = {
    "SERVER_JARFILE": "server.jar",
    "EULA": "TRUE",
    "VERSION": "latest",
    "BUILD_NUMBER": "1",
    "SPONGE_VERSION": "stable-7",
    "FORGE_VERSION": "latest",
    "MINECRAFT_VERSION": "latest"
}

# NOTE: Replace egg_id / nest_id / docker_image / startup for your real panel eggs if different.
EGG_CATALOG: Dict[str, Dict[str, Any]] = {
    "paper": {
        "display": "Minecraft: Paper",
        "nest_id": 1,
        "egg_id": 3,  # your paper egg ID (you said paper egg is 3)
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}} nogui",
        "environment": {"SERVER_JARFILE": "server.jar", "EULA": "TRUE", "BUILD_NUMBER": "1"}
    },
    "vanilla": {
        "display": "Minecraft: Vanilla",
        "nest_id": 1,
        "egg_id": 1,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar nogui",
        "environment": {"SERVER_JARFILE": "server.jar", "EULA": "TRUE"}
    },
    "forge": {
        "display": "Minecraft: Forge",
        "nest_id": 1,
        "egg_id": 4,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}} nogui",
        "environment": {"SERVER_JARFILE": "forge.jar", "FORGE_VERSION": "latest", "MINECRAFT_VERSION": "latest"}
    },
    "sponge": {
        "display": "Minecraft: Sponge",
        "nest_id": 1,
        "egg_id": 6,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_11",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}} nogui",
        "environment": {"SERVER_JARFILE": "sponge.jar", "SPONGE_VERSION": "stable-7", "MINECRAFT_VERSION": "1.12.2"}
    },
    "nodejs": {
        "display": "Node.js App",
        "nest_id": 5,
        "egg_id": 16,
        "docker_image": "ghcr.io/pterodactyl/yolks:nodejs_18",
        "startup": "node index.js",
        "environment": {"STARTUP_FILE": "index.js"}
    },
    "python": {
        "display": "Python App",
        "nest_id": 5,
        "egg_id": 17,
        "docker_image": "ghcr.io/pterodactyl/yolks:python_3.11",
        "startup": "python3 main.py",
        "environment": {"STARTUP_FILE": "main.py"}
    },
    "fivem": {
        "display": "GTA FiveM",
        "nest_id": 3,
        "egg_id": 18,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "./run.sh +exec server.cfg",
        "environment": {"SERVER_JARFILE": "server.cfg"}
    },
    "rust": {
        "display": "Rust",
        "nest_id": 4,
        "egg_id": 19,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "./RustDedicated -batchmode -nographics -server.ip 0.0.0.0 -server.port {{SERVER_PORT}}",
        "environment": {}
    },
    "mariadb": {
        "display": "MariaDB",
        "nest_id": 7,
        "egg_id": 20,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "mysqld --defaults-file=/mnt/server/my.cnf",
        "environment": {"MYSQL_ROOT_PASSWORD": "root"}
    }
}

# Helper to pretty list eggs
def egg_list_text() -> str:
    lines = []
    for idx, (key, val) in enumerate(EGG_CATALOG.items(), start=1):
        lines.append(f"{idx}. {val['display']} (`{key}`)")
    return "\n".join(lines)

# =======================
# Admin check helpers
# =======================
def is_requester_admin_member(member: discord.Member) -> bool:
    # Server admin permission
    try:
        if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
            return True
    except Exception:
        pass
    # Role name match
    try:
        names = {r.name for r in getattr(member, "roles", [])}
        if ADMIN_ROLE_NAMES.intersection(names):
            return True
    except Exception:
        pass
    # Stored IDs in data
    if str(member.id) in set(data.get("admins", [])):
        return True
    return False

async def require_admin_ctx(ctx: commands.Context) -> bool:
    if not is_requester_admin_member(ctx.author):
        await ctx.reply("🔒 You are not authorized to use admin commands.")
        return False
    return True

# =======================
# Utility: merge env defaults
# =======================
def build_env_for_egg(egg_key: str) -> Dict[str, Any]:
    env = {}
    env.update(DEFAULT_ENV)
    egg_env = EGG_CATALOG.get(egg_key, {}).get("environment", {})
    env.update(egg_env)
    # Ensure minimal defaults
    required_defaults = {
        "BUILD_NUMBER": "1",
        "SERVER_JARFILE": "server.jar",
        "EULA": "TRUE",
        "VERSION": "latest",
        "SPONGE_VERSION": "stable-7",
        "FORGE_VERSION": "latest",
        "MINECRAFT_VERSION": "latest"
    }
    for k, v in required_defaults.items():
        if env.get(k) in (None, ""):
            env[k] = v
    return env

# =======================
# Core server create function (used by *create and admin create)
# =======================
def panel_create_server(name: str, owner_panel_id: int, egg_key: str, memory: int, cpu: int, disk: int, allocation_id: Optional[int] = None) -> Dict[str, Any]:
    if egg_key not in EGG_CATALOG:
        raise ValueError("Unknown egg key")
    egg_def = EGG_CATALOG[egg_key]

    # pick allocation if not provided
    alloc = allocation_id
    if not alloc:
        alloc = get_free_allocation(PANEL_NODE_ID)
    if not alloc and DEFAULT_ALLOCATION_ID:
        try:
            alloc = int(DEFAULT_ALLOCATION_ID)
        except Exception:
            alloc = None

    if not alloc:
        raise RuntimeError("No free allocation on node and no DEFAULT_ALLOCATION_ID set")

    env = build_env_for_egg(egg_key)

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
        "environment": env
    }

    r = app_post("/servers", payload)
    if not r.ok:
        # raise with body for debugging
        raise RuntimeError(f"Panel error {r.status_code}: {r.text}")
    return r.json()

# =======================
# Commands
# =======================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | Prefix: {PREFIX}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {BOT_VERSION}"))

# HELP
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    em = discord.Embed(title="Bot Help", color=discord.Color.blurple())
    em.description = (
        f"Prefix `{PREFIX}` commands — Panel: {PANEL_URL}\n\n"
        "**User:**\n"
        f"`{PREFIX}plans` — show invite plans\n"
        f"`{PREFIX}i [@user]` — show invites/tier\n"
        f"`{PREFIX}register <email> <password>` — link/create panel account\n"
        f"`{PREFIX}create` — interactive create (select egg, give RAM/CPU/DISK)\n"
        f"`{PREFIX}manage` — manage a server using your client API key\n"
        "\n**Admin:**\n"
        f"`{PREFIX}admin add_i @user <amount>` — add invites\n"
        f"`{PREFIX}admin remove_i @user <amount>` — remove invites\n"
        f"`{PREFIX}admin add_a @user` — add bot admin\n"
        f"`{PREFIX}admin rm_a @user` — remove bot admin\n"
        f"`{PREFIX}admin create_a @user <email> <password>` — create panel user and link\n"
        f"`{PREFIX}admin create_s <owner_email> <egg_key> <name> <ram> <cpu> <disk>` — create server\n"
        f"`{PREFIX}admin delete_s <server_id>` — delete server\n"
        f"`{PREFIX}admin serverlist` — list servers\n"
        f"`{PREFIX}admin newmsg <channel_id> <text>` — broadcast\n"
        f"`{PREFIX}admin lock` / `{PREFIX}admin unlock` — lock/unlock current channel\n"
        f"`{PREFIX}clear <amount>` — purge messages\n"
    )
    await ctx.reply(embed=em)

# PLANS
@bot.command(name="plans")
async def plans_cmd(ctx: commands.Context):
    em = discord.Embed(title="Invite Plans", color=discord.Color.gold())
    lines = []
    for t in [
        {"name": "Basic", "inv": 0, "ram": 4096, "cpu": 150, "disk": 10000},
        {"name": "Advanced", "inv": 4, "ram": 6144, "cpu": 200, "disk": 15000},
        {"name": "Pro", "inv": 6, "ram": 7168, "cpu": 230, "disk": 20000},
        {"name": "Premium", "inv": 8, "ram": 9216, "cpu": 270, "disk": 25000},
        {"name": "Elite", "inv": 15, "ram": 12288, "cpu": 320, "disk": 30000},
        {"name": "Ultimate", "inv": 20, "ram": 16384, "cpu": 400, "disk": 35000},
    ]:
        lines.append(f"**{t['name']}** — at {t['inv']} invites\nRAM {t['ram']}MB | CPU {t['cpu']}% | Disk {t['disk']}MB")
    em.description = "\n\n".join(lines)
    if PLANS_IMAGE_URL:
        em.set_image(url=PLANS_IMAGE_URL)
    await ctx.reply(embed=em)

# INVITES info
@bot.command(name="i")
async def invites_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    target = member or ctx.author
    invites = int(data.get("invites", {}).get(str(target.id), 0))
    # choose tier
    tier = None
    for t in [{"name":"Basic","inv":0},{"name":"Advanced","inv":4},{"name":"Pro","inv":6},{"name":"Premium","inv":8},{"name":"Elite","inv":15},{"name":"Ultimate","inv":20}]:
        if invites >= t["inv"]:
            tier = t
    em = discord.Embed(title=f"Invites — {target.display_name}", color=discord.Color.blue())
    em.add_field(name="Total invites", value=str(invites))
    em.add_field(name="Tier", value=tier["name"] if tier else "Basic")
    await ctx.reply(embed=em)

# REGISTER (create or link panel user)
@bot.command(name="register")
async def register_cmd(ctx: commands.Context, email: str, password: str):
    # If already linked, tell
    uid = data.get("panel_users", {}).get(str(ctx.author.id))
    if uid:
        await ctx.reply("You already have a linked panel user.")
        return
    # create or fetch
    created_id = create_panel_user(email, username=f"u{ctx.author.id}", password=password, first_name=ctx.author.name, last_name="Discord")
    if not created_id:
        await ctx.reply("Failed to create or find panel user. Ask admin.")
        return
    data.setdefault("panel_users", {})[str(ctx.author.id)] = created_id
    save_data(data)
    await ctx.reply(f"Linked panel user id `{created_id}` to your Discord account.")

# INTERACTIVE create — choose egg, limits only
@bot.command(name="create")
async def create_interactive(ctx: commands.Context):
    uid = data.get("panel_users", {}).get(str(ctx.author.id))
    if not uid:
        await ctx.reply(f"Register first with `{PREFIX}register <email> <password>` or ask admin to link an account.")
        return
    # show eggs
    menu = egg_list_text()
    await ctx.send("Select egg by typing its key (example: `paper`, `forge`, `nodejs`):\n" + menu)
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        msg = await bot.wait_for("message", timeout=60, check=check)
        egg_key = msg.content.strip().lower()
        if egg_key not in EGG_CATALOG:
            await ctx.send("Invalid egg key.")
            return
        # prompt for name, ram, cpu, disk
        await ctx.send("Enter server name:")
        msg = await bot.wait_for("message", timeout=60, check=check)
        name = msg.content.strip()[:40]
        await ctx.send("Enter RAM in MB (e.g., 4096):")
        msg = await bot.wait_for("message", timeout=60, check=check)
        ram = int(msg.content.strip())
        await ctx.send("Enter CPU (percentage or integer):")
        msg = await bot.wait_for("message", timeout=60, check=check)
        cpu = int(msg.content.strip())
        await ctx.send("Enter disk in MB (e.g., 20000):")
        msg = await bot.wait_for("message", timeout=60, check=check)
        disk = int(msg.content.strip())
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return
    await ctx.send("Creating server... (this may take a few seconds)")
    try:
        result = panel_create_server(name=name, owner_panel_id=uid, egg_key=egg_key, memory=ram, cpu=cpu, disk=disk)
        # result is JSON from panel
        identifier = result.get("attributes", {}).get("identifier")
        await ctx.send(f"✅ Server creation queued. Identifier: `{identifier}`. Check panel for status.")
    except Exception as e:
        await ctx.send(f"❌ Error creating server: {e}")

# MANAGE - simple client-key based interactive manager (start/stop/restart/kill/reinstall/ip)
@bot.command(name="manage")
async def manage_cmd(ctx: commands.Context):
    # ask for client api key
    await ctx.send("Send your **Client API Key** (Account → API) — will be stored locally for your user.")
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        key_msg = await bot.wait_for("message", timeout=90, check=check)
        client_key = key_msg.content.strip()
        data.setdefault("client_keys", {})[str(ctx.author.id)] = client_key
        save_data(data)
    except asyncio.TimeoutError:
        await ctx.send("Timed out.")
        return
    await ctx.send("Now send the server identifier (the short code shown in the panel).")
    try:
        id_msg = await bot.wait_for("message", timeout=60, check=check)
        sid = id_msg.content.strip()
    except asyncio.TimeoutError:
        await ctx.send("Timed out.")
        return
    await ctx.send("Enter command: start / stop / restart / kill / reinstall / ip / exit")
    while True:
        try:
            cmd_msg = await bot.wait_for("message", timeout=120, check=check)
            cmd = cmd_msg.content.strip().lower()
            if cmd == "exit":
                await ctx.send("Exited manage mode.")
                break
            client_headers = {"Authorization": f"Bearer {client_key}", "Content-Type": "application/json", "Accept": "application/vnd.pterodactyl.v1+json"}
            if cmd in ("start", "stop", "restart", "kill"):
                r = requests.post(f"{PANEL_URL}/api/client/servers/{sid}/power", headers=client_headers, json={"signal": cmd})
                await ctx.send("✅ Done." if r.ok else f"❌ Failed: {r.status_code} {r.text[:200]}")
            elif cmd == "reinstall":
                r = requests.post(f"{PANEL_URL}/api/client/servers/{sid}/settings/reinstall", headers=client_headers)
                await ctx.send("✅ Reinstall queued." if r.ok else f"❌ {r.status_code}")
            elif cmd == "ip":
                r = requests.get(f"{PANEL_URL}/api/client/servers/{sid}", headers=client_headers)
                if r.ok:
                    at = r.json().get("attributes", {})
                    # attempt to show allocations
                    allocs = at.get("relationships", {}).get("allocations", {}).get("data", [])
                    if allocs:
                        # may need client API to fetch details - display generic
                        await ctx.send("Allocation info present in panel. Open panel to view exact IP:port.")
                    else:
                        await ctx.send("No allocation info.")
                else:
                    await ctx.send("Failed to fetch server info.")
            else:
                await ctx.send("Unknown command. Use start/stop/restart/kill/reinstall/ip/exit.")
        except asyncio.TimeoutError:
            await ctx.send("Manage session timed out.")
            break

# SERVERINFO (discord server)
@bot.command(name="serverinfo")
async def serverinfo_cmd(ctx: commands.Context):
    g = ctx.guild
    if not g:
        await ctx.send("This command must be run in a server.")
        return
    owner = await g.fetch_owner()
    online = sum(1 for m in g.members if m.status != discord.Status.offline)
    em = discord.Embed(title=g.name, color=discord.Color.blurple())
    if g.icon:
        try:
            em.set_thumbnail(url=g.icon.url)
        except Exception:
            pass
    em.add_field(name="Owner", value=f"{owner} ({owner.id})", inline=False)
    em.add_field(name="Server ID", value=str(g.id))
    em.add_field(name="Members", value=str(g.member_count))
    em.add_field(name="Online", value=str(online))
    em.add_field(name="Roles", value=str(len(g.roles)))
    em.add_field(name="Bot Version", value=BOT_VERSION)
    await ctx.send(embed=em)

# NODE status (allocations)
@bot.command(name="node")
async def node_cmd(ctx: commands.Context):
    try:
        r = app_get(f"/nodes/{PANEL_NODE_ID}")
        if not r.ok:
            await ctx.send("Failed to contact panel.")
            return
        node_attr = r.json().get("attributes", {})
        r2 = app_get(f"/nodes/{PANEL_NODE_ID}/allocations")
        total = 0
        free = 0
        if r2.ok:
            for item in r2.json().get("data", []):
                total += 1
                if not item.get("attributes", {}).get("assigned", False):
                    free += 1
        em = discord.Embed(title=f"Node: {node_attr.get('name','?')}", color=discord.Color.orange())
        em.add_field(name="FQDN", value=node_attr.get("fqdn","?"))
        em.add_field(name="Allocations", value=f"{free} free / {total} total")
        em.add_field(name="Maintenance", value=str(node_attr.get("maintenance_mode", False)))
        await ctx.send(embed=em)
    except Exception as e:
        await ctx.send(f"Error: {e}")

# ADMIN group
@bot.group(name="admin", invoke_without_command=True)
async def admin_group(ctx: commands.Context):
    if not await require_admin_ctx(ctx):
        return
    await ctx.send("Admin subcommands: add_i, remove_i, add_a, rm_a, create_a, rm_ac, create_s, delete_s, serverlist, newmsg, lock, unlock")

@admin_group.command(name="add_i")
async def admin_add_i(ctx: commands.Context, member: discord.Member, amount: int):
    if not await require_admin_ctx(ctx): return
    inv = data.setdefault("invites", {})
    inv[str(member.id)] = int(inv.get(str(member.id), 0)) + max(0, int(amount))
    save_data(data)
    await ctx.send(f"✅ Added {amount} invites to {member.mention}. Total: {inv[str(member.id)]}")

@admin_group.command(name="remove_i")
async def admin_remove_i(ctx: commands.Context, member: discord.Member, amount: int):
    if not await require_admin_ctx(ctx): return
    inv = data.setdefault("invites", {})
    cur = int(inv.get(str(member.id), 0))
    inv[str(member.id)] = max(0, cur - max(0, int(amount)))
    save_data(data)
    await ctx.send(f"✅ Removed {amount} invites from {member.mention}. Total: {inv[str(member.id)]}")

@admin_group.command(name="add_a")
async def admin_add_a(ctx: commands.Context, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    admins = set(data.get("admins", []))
    admins.add(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"✅ {member.mention} added to bot admins.")

@admin_group.command(name="rm_a")
async def admin_rm_a(ctx: commands.Context, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    admins = set(data.get("admins", []))
    admins.discard(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"✅ {member.mention} removed from bot admins.")

@admin_group.command(name="create_a")
async def admin_create_a(ctx: commands.Context, member: discord.Member, email: str, password: str):
    if not await require_admin_ctx(ctx): return
    uid = create_panel_user(email=email, username=f"user{member.id}", password=password, first_name=member.display_name[:20], last_name="Discord")
    if not uid:
        await ctx.send("❌ Could not create panel user.")
        return
    data.setdefault("panel_users", {})[str(member.id)] = uid
    save_data(data)
    try:
        await member.send(f"Your panel account created!\nEmail: {email}\nPassword: {password}\nPanel: {PANEL_URL}")
    except Exception:
        pass
    await ctx.send(f"✅ Created and linked panel user id `{uid}` to {member.mention}.")

@admin_group.command(name="rm_ac")
async def admin_rm_ac(ctx: commands.Context, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    uid = data.get("panel_users", {}).get(str(member.id))
    if not uid:
        await ctx.send("No linked panel account for that user.")
        return
    # Delete user's servers (walk through panel servers and remove where user matches)
    try:
        r = app_get("/servers")
        if r.ok:
            for d in r.json().get("data", []):
                a = d.get("attributes", {})
                if a.get("user") == uid or a.get("owner", {}).get("id") == uid:
                    delete_panel_server(a.get("id"))
                    time.sleep(0.2)
    except Exception:
        pass
    ok = delete_panel_user(uid)
    if ok:
        data["panel_users"].pop(str(member.id), None)
        save_data(data)
        await ctx.send("✅ Deleted panel user and their servers.")
    else:
        await ctx.send("❌ Failed to delete panel user.")

@admin_group.command(name="create_s")
async def admin_create_s(ctx: commands.Context, owner_email: str, egg_key: str, name: str, memory: int, cpu: int, disk: int):
    if not await require_admin_ctx(ctx): return
    # find user id
    owner_uid = get_panel_user_id_by_email(owner_email)
    if not owner_uid:
        await ctx.send("❌ Owner email not found in panel. Create or link user first.")
        return
    if egg_key not in EGG_CATALOG:
        await ctx.send("❌ Unknown egg key. Use one of: " + ", ".join(EGG_CATALOG.keys()))
        return
    await ctx.send("Creating server…")
    try:
        result = panel_create_server(name=name, owner_panel_id=owner_uid, egg_key=egg_key, memory=memory, cpu=cpu, disk=disk)
        ident = result.get("attributes", {}).get("identifier")
        await ctx.send(f"✅ Server created: `{ident}`")
    except Exception as e:
        await ctx.send(f"❌ Panel error: {e}")

@admin_group.command(name="delete_s")
async def admin_delete_s(ctx: commands.Context, server_id: int):
    if not await require_admin_ctx(ctx): return
    ok = delete_panel_server(server_id)
    await ctx.send("✅ Deleted." if ok else "❌ Failed to delete.")

@admin_group.command(name="serverlist")
async def admin_serverlist(ctx: commands.Context):
    if not await require_admin_ctx(ctx): return
    servers = list_panel_servers()
    if not servers:
        await ctx.send("No servers or API error.")
        return
    lines = []
    for s in servers:
        lim = s.get("limits", {})
        lines.append(f"ID {s['id']} • {s['name']} • RAM {lim.get('memory','?')}MB CPU {lim.get('cpu','?')}% Disk {lim.get('disk','?')}MB")
    for chunk_start in range(0, len(lines), 15):
        chunk = lines[chunk_start:chunk_start+15]
        await ctx.send("```\n" + "\n".join(chunk) + "\n```")

@admin_group.command(name="newmsg")
async def admin_newmsg(ctx: commands.Context, channel_id: int, *, text: str):
    if not await require_admin_ctx(ctx): return
    ch = bot.get_channel(channel_id) or ctx.guild.get_channel(channel_id)
    if not ch:
        await ctx.send("Channel not found.")
        return
    await ch.send(text)
    await ctx.send("✅ Sent.")

@admin_group.command(name="lock")
async def admin_lock(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    if not await require_admin_ctx(ctx): return
    ch = channel or ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔒 Locked {ch.mention}")

@admin_group.command(name="unlock")
async def admin_unlock(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    if not await require_admin_ctx(ctx): return
    ch = channel or ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔓 Unlocked {ch.mention}")

# CLEAR
@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx: commands.Context, amount: int):
    deleted = await ctx.channel.purge(limit=min(max(amount,1), 500))
    msg = await ctx.send(f"🧹 Cleared {len(deleted)} messages.")
    await asyncio.sleep(3)
    await msg.delete()

# VERIFY
@bot.command(name="verify")
async def verify_cmd(ctx: commands.Context, tier: Optional[str] = None):
    inv = int(data.get("invites", {}).get(str(ctx.author.id), 0))
    if not tier:
        await ctx.send(f"You have {inv} invites.")
        return
    await ctx.send(f"You requested verify for {tier}. You have {inv} invites.")

# SCREENSHOT (embed)
@bot.command(name="screenshot")
async def screenshot_cmd(ctx: commands.Context, *, url: str):
    em = discord.Embed(title="Screenshot", description=url)
    try:
        em.set_image(url=url)
    except Exception:
        pass
    await ctx.send(embed=em)

# BOT INFO
@bot.command(name="botinfo")
async def botinfo_cmd(ctx: commands.Context):
    em = discord.Embed(title="Bot Info", color=discord.Color.blue())
    em.add_field(name="Version", value=BOT_VERSION)
    em.add_field(name="Made by", value=MADE_BY)
    em.add_field(name="Prefix", value=PREFIX)
    await ctx.send(embed=em)

# =======================
# Start bot
# =======================
bot.run(BOT_TOKEN)
