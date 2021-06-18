from json import load, dump
import discord
from time import time
import db_manager
import logging
from threading import Lock as ThreadingLock

# Main handler
main_logger = logging.getLogger(__name__)
dbg_handler = logging.FileHandler(filename="./data/logs/main_dbg.log", encoding="utf-8", mode="a")
main_handler = logging.FileHandler(filename="./data/logs/main.log", encoding="utf-8", mode="a")
dbg_handler.setLevel(logging.DEBUG)
main_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
dbg_handler.setFormatter(formatter)
main_handler.setFormatter(formatter)
main_logger.addHandler(dbg_handler)
main_logger.addHandler(main_handler)

# Discord py handler
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="./data/logs/discord.log", encoding="utf-8", mode="a")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
discord_logger.addHandler(handler)

config_file = open("./data/config.json")
config = load(config_file)
del config_file
# Load json config

MARKET_ITEMS_PER_PAGE = 10
FOOTER_TEXT = "DM the bot and your feedback will be passed on the maintainer"

last_update_time = time()
update_interval = 60
server_status = {}
# ud: unplanned down
# pd: planned down
# d: down
# u: up

config_lock = ThreadingLock()


def update_blocked_users(uid):
    global config, config_file
    main_logger.debug("Waiting for config lock to update blocked users")
    config_lock.acquire()
    main_logger.debug("Blocking user with id "+str(uid))

    config_file = open("./data/config.json")
    config = load(config_file)
    del config_file
    config["blocked"].append(uid)
    file = open("./data/config.json", "w")
    dump(config, file, indent=4)
    file.close()

    main_logger.info("Blocked user with id "+str(uid))
    config_lock.release()
    main_logger.debug("Released config lock")


def update_stored_cookie(new_cookie):
    main_logger.debug("Waiting for config lock to update app-sid")
    config_lock.acquire()
    main_logger.debug("Updating cookie to "+new_cookie)

    config["surviv_app_sid"] = new_cookie
    file = open("./data/config.json", "w")
    dump(config, file, indent=4)
    file.close()
    # Write app-sid cookie

    main_logger.debug("Updated cookie to "+new_cookie)
    config_lock.release()
    main_logger.debug("Released config lock")


def update_server_status():
    global last_update_time
    last_update_time = time()
    from requests import get, exceptions
    try:
        resp = get("https://surviv.io", timeout=10)
        main_logger.debug("Got frontend response " + str(resp) + " " + resp.text)
    except exceptions.ConnectionError:
        server_status["Main"] = "ud"
        main_logger.info("Surviv frontend down")
        return

    if resp.status_code == 503:
        server_status["Main"] = "pd"
        main_logger.info("Surviv frontend down")
        return
    elif resp.status_code == 502:
        server_status["Main"] = "ud"
        main_logger.info("Surviv frontend down")
    else:
        server_status["main"] = "u"
        main_logger.info("Surviv frontend up")

    try:
        get("https://surviv.io/api/games_modes", timeout=10)
        main_logger.debug("Got gamemodes response " + str(resp) + " " + resp.text)
    except exceptions.ConnectionError:
        server_status["API"] = "d"
        main_logger.info("Surviv api down")
        return
    else:
        server_status["API"] = "u"
        main_logger.info("Surviv api up")
    return


def make_down_embed():
    embed = discord.Embed(title="Server status")
    abbrev_to_full = {
        "ud": "down, unplanned",
        "pd": "down, planned",
        "d": "down",
        "u": "up"
    }
    embed.add_field(name="Website status", value=abbrev_to_full[server_status["main"]])
    if server_status["main"] == "u":
        embed.add_field(name="API status", value=abbrev_to_full[server_status["API"]])
    embed.set_footer(text=FOOTER_TEXT)
    return embed


async def check_update_server_status():
    if time() > last_update_time + update_interval:
        update_server_status()
        embed = make_down_embed()
        for item in server_status.items():
            if item != "u":
                for sid in db_manager.get_servers():
                    server = bot.get_guild(sid[0])
                    settings = db_manager.get_server(sid[0])
                    if settings["server_status_channel"]:
                        await server.get_channel(settings["server_status_channel"]).send(embed=embed)
                break


update_server_status()


async def syntax_error_message(message):
    await message.reply("Invalid arguments, try again")


async def web_error_message(message):
    await message.reply("Something went wrong internally, trying again later might help")


async def permissions_error_message(message):
    await message.reply("You do not have sufficient permissions to make this change")


async def get_server_status(message):
    update_server_status()
    embed = make_down_embed()
    await message.reply(embed=embed)


async def get_market_items(message):
    from requests import session
    from requests.cookies import cookiejar_from_dict
    from json import JSONDecodeError
    if not config["market_enabled"]:
        await message.reply("The hoster of this bot instance has disabled this feature")
        return

    def make_embed(items, page_num):
        rarities_reverse = {
            5: "Legendary",
            4: "Mythic",
            3: "Epic",
            2: "Uncommon",
            1: "Common"
        }
        embed = discord.Embed(title="Page " + str(page_num) + " of " + str(int(len(items) / MARKET_ITEMS_PER_PAGE)))
        for item in items[(page_num-1) * MARKET_ITEMS_PER_PAGE:page_num * MARKET_ITEMS_PER_PAGE]:
            item_str = "Item: " + item["item"]
            item_str += "\nType: " + item["type"]
            item_str += "\nPrice: " + str(item["price"])
            item_str += "\nRarity: " + str(rarities_reverse[item["rarity"]])
            item_str += "\nMakr: " + item["makr"]
            item_str += "\nKills: " + str(item["kills"])
            item_str += "\nLevels: " + str(item["levels"])
            item_str += "\nWins: " + str(item["wins"])
            embed.add_field(name="Item " + str(items.index(item)+1), value=item_str)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    session = session()
    session.cookies = cookiejar_from_dict({"app-sid": config["surviv_app_sid"]})

    argv = message.content.split(" ")
    if len(argv) != 4:
        await syntax_error_message(message)
        return

    rarities = {
        "5": "5",
        "4": "4",
        "3": "3",
        "2": "2",
        "1": "1",
        "0": "all",
        "l": "5",
        "legend": "5",
        "legendary": "5",
        "a": "all",
        "all": "all",
        "m": "4",
        "mythic": "4",
        "e": "3",
        "epic": "3",
        "u": "2",
        "uncommon": "2",
        "c": "1",
        "common": "1"
    }
    types = {
        "a": "all",
        "all": "all",
        "outfit": "outfit",
        "skin": "outfit",
        "melee": "melee",
        "fists": "melee",
        "emote": "emote",
        "emoji": "emote",
        "heal": "heal_effect",
        "boost": "boost_effect",
        "adren": "boost_effect",
        "adrenaline": "boost_effect",
        "death": "deathEffect",
        "deatheffect": "deathEffect",
        "deathEffect": "deathEffect",
    }
    try:
        int(argv[3])
    except ValueError:
        await syntax_error_message(message)
        return
    if argv[1] not in rarities or argv[2] not in types:
        await syntax_error_message(message)
        return
    # Throw an error if args are bad

    rarity = rarities[argv[1]]
    item_type = types[argv[2]]
    page = int(argv[3])

    req = {
        "rarity": rarity,
        "type": item_type,
        "userId": config["surviv_id"]
    }
    resp = session.post("https://surviv.io/api/user/market/get_market_available_items", json=req)
    main_logger.debug("Got market response " + str(resp) + " " + resp.text)
    cookies = resp.cookies.get_dict()
    if cookies and "app-sid" in cookies:
        update_stored_cookie(cookies["app-sid"])
    # Make the request

    if resp.status_code != 200:
        await web_error_message(message)
        return
    try:
        resp = resp.json()
    except JSONDecodeError:
        await web_error_message(message)
        return
    if not resp["success"]:
        await web_error_message(message)
        return
    # Throw an error if there's a bad response or something
    await message.reply(embed=make_embed(resp["items"], page))


async def get_stats(message):
    from requests import post
    from json import JSONDecodeError
    argv = message.content.split(" ")

    if len(argv) not in (2, 3):
        await syntax_error_message(message)
        return

    req = {
        "interval": "all",
        "mapIdFilter": "-1",
        "slug": argv[1]
    }
    resp = post("https://surviv.io/api/user_stats", json=req)
    main_logger.debug("Got stats response " + str(resp) + " " + resp.text)

    if resp.status_code != 200:
        await web_error_message(message)
        return
    try:
        resp = resp.json()
    except JSONDecodeError:
        await web_error_message(message)
        return

    if not resp:
        await message.reply("Could not find player")
        return

    if len(argv) == 2:
        embed = discord.Embed(title=resp["username"])
        embed.add_field(name="Banned: ", value="Yes" if resp["banned"] else "No", inline=True)
        embed.add_field(name="Games: ", value=str(resp["games"]))
        embed.add_field(name="Kills: ", value=str(resp["kills"]))
        embed.add_field(name="Wins: ", value=str(resp["wins"]))
        embed.add_field(name="KPG: ", value=resp["kpg"])
        
        embed.set_footer(text=FOOTER_TEXT)
        await message.reply(embed=embed)
        return

    arg_to_type = {
        "solo": 0,
        "solos": 0,
        "duo": 1,
        "duos": 1,
        "squad": 2,
        "squads": 2
    }
    if argv[2] not in arg_to_type.keys():
        await syntax_error_message(message)
        return

    index = arg_to_type[argv[2]]
    embed = discord.Embed(title=resp["username"]+" " + (argv[2][:-1] if argv[2].endswith("s") else argv[2]) + " game stats")
    embed.add_field(name="Games: ", value=str(resp["modes"][index]["games"]))
    embed.add_field(name="Kills: ", value=str(resp["modes"][index]["kills"]))
    embed.add_field(name="KPG: ", value=str(resp["modes"][index]["kpg"]))
    embed.add_field(name="Wins: ", value=str(resp["modes"][index]["wins"]))
    embed.add_field(name="Win percentage: ", value=str(resp["modes"][index]["winPct"]))
    embed.add_field(name="Average damage: ", value=resp["modes"][index]["avgDamage"])
    embed.add_field(name="Average time alive: ", value=str(resp["modes"][index]["avgTimeAlive"]))
    embed.add_field(name="Highest damage: ", value=str(resp["modes"][index]["mostDamage"]))
    embed.add_field(name="Highest kills: ", value=str(resp["modes"][index]["mostKills"]))
    embed.set_footer(text=FOOTER_TEXT)

    await message.reply(embed=embed)
    return


async def set_manager_role(message):
    if message.author.id != message.guild.owner_id:
        await permissions_error_message(message)
        return
    argv = message.content.split(" ")
    if len(argv) != 2:
        await syntax_error_message(message)
    try:
        int(argv[1])
    except ValueError:
        await syntax_error_message(message)
    if not message.guild.get_role(int(argv[1])):
        await syntax_error_message(message)
    # Input validation

    settings = db_manager.get_server(message.guild.id)
    settings["manager_role_id"] = int(argv[1])
    db_manager.update_server(message.guild.id, settings)
    role = message.guild.get_role(int(argv[1]))
    await message.reply("Bot management role set to: " + str(role))


async def leave(message):
    if not message.author.guild_permissions.kick_members:
        await permissions_error_message(message)
        return
    await message.reply("Leaving server")
    db_manager.del_server(message.guild.id)
    await message.guild.leave()


async def change_pre(message):
    settings = db_manager.get_server(message.guild.id)
    if not (message.author.id == message.guild.owner_id or message.guild.get_role(settings["manager_role_id"]) in message.author.roles):
        await permissions_error_message(message)
        return
    # Input validation

    argv = message.content.split(" ")
    if len(argv) != 2:
        await syntax_error_message(message)
        return
    old_prefix = settings["prefix"]
    settings["prefix"] = argv[1]
    db_manager.update_server(message.guild.id, settings)
    await message.reply("Prefix changed from " + old_prefix + " to " + settings["prefix"])


async def change_down_channel(message):
    settings = db_manager.get_server(message.guild.id)
    if not (message.author.id == message.guild.owner_id or message.guild.get_role(settings["manager_role_id"]) in message.author.roles):
        await permissions_error_message(message)
        return

    argv = message.content.split(" ")
    try:
        int(argv[1])
    except ValueError:
        await syntax_error_message(message)
        return

    channel = message.guild.get_channel(int(argv[1]))
    if not channel and int(argv[1]) != 0:
        await syntax_error_message(message)
        return
    settings["server_status_channel"] = int(argv[1])
    # Input validation + processing

    db_manager.update_server(message.guild.id, settings)
    await message.reply("Server status channel set to " + str(channel))


async def get_server_count(message):
    count = len(db_manager.get_servers())
    await message.reply(str(count) + " servers are using this bot")


async def help_message(message):
    settings = db_manager.get_server(message.guild.id)
    prefix = settings["prefix"]

    embed = discord.Embed(title="Commands")
    embed.add_field(name=prefix+"stats", value="Get stats of a specific user, the name should be the same as in the stats link. You can also put solo, duos or sqauds at the end for more info")
    embed.add_field(name=prefix+"setmanagerrole", value="Set the role that can make changes to the bot, like the prefix. Arg must be a valid role ID or 0 to disable. Only the owner can perform this action")
    embed.add_field(name=prefix+"remove, "+prefix+"leave", value="Kicking/banning should have the same effect as these, only people with kick perms can use this.")
    embed.add_field(name=prefix+"prefix", value="Change the prefix which the bot responds to")
    embed.add_field(name=prefix+"server", value="Check the current status of the surviv.io servers")
    embed.add_field(name=prefix+"market", value="Get market items, arguments should be in the format [rarity] [type] [page]")
    embed.add_field(name=prefix+"serverchannel, "+prefix+"downchannel", value="The channel to send surviv server downtime messages to. Set to 0 to disable")
    embed.add_field(name=prefix+"servercount", value="Say the amount of servers this bot is in")
    embed.add_field(name=prefix+"help", value="This message")
    embed.add_field(name=prefix+"inv, "+prefix+"invite", value="The invite link for this bot")
    embed.set_footer(text=FOOTER_TEXT)

    await message.reply(embed=embed)


async def invite_message(message):
    await message.reply(config["discord_join_link"])


commands = {
    "server": get_server_status,
    "servers": get_server_status,
    "down": get_server_status,
    "market": get_market_items,
    "stats": get_stats,
    "setmanagerrole": set_manager_role,
    "remove": leave,
    "leave": leave,
    "prefix": change_pre,
    "chanepre": change_pre,
    "changeprefix": change_pre,
    "serverchannel": change_down_channel,
    "downchannel": change_down_channel,
    "servercount": get_server_count,
    "help": help_message,
    "inv": invite_message,
    "invite": invite_message,
    "link": invite_message,
}

intent = discord.Intents.none()
intent.guild_messages = True
intent.guilds = True
intent.dm_messages = True
bot = discord.Client(guild_subscriptions=False, intent=intent)


@bot.event
async def on_ready():
    db_manager.setup()


@bot.event
async def on_message(message: discord.Message):
    await check_update_server_status()
    if message.author.id in config["blocked"] or message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel) and message.author.id == config["discord_feedback_user_id"]:
        if message.content == "shutdown":
            await bot.close()
            quit()

        if "block" in message.content:
            argv = message.content.split(" ")
            if len(argv) != 2:
                await syntax_error_message(message)
                return
            try:
                int(argv[1])
            except ValueError:
                await syntax_error_message(message)
                return
            # Input validation

            update_blocked_users(int(argv[1]))
        return
        # Block command, for feedback user only

    if isinstance(message.channel, discord.DMChannel):
        feedback_user = await bot.fetch_user(config["discord_feedback_user_id"])
        feedback_channel = await feedback_user.create_dm()
        await feedback_channel.send("Message from " + str(message.author) + ": " + message.content)
        return
        # Send DMs to feedback user

    db_manager.add_if_not_exists(message.guild.id)

    settings = db_manager.get_server(message.guild.id)
    if message.content.startswith(settings["prefix"]):
        first_word = message.content.split(" ")[0]
        first_word = first_word.replace(settings["prefix"], "", 1)
        first_word = first_word.lower()
        # Process message into command
        if first_word in commands:
            await commands[first_word](message)


@bot.event
async def on_guild_join(guild):
    db_manager.new_server(guild.id)


@bot.event
async def on_guild_remove(guild):
    db_manager.del_server(guild.id)


@bot.event
async def on_guild_channel_delete(channel):
    settings = db_manager.get_server(channel.guild.id)
    if channel.id == settings["server_status_channel"]:
        settings["server_status_channel"] = 0
        db_manager.update_server(channel.guild.id, settings)


main_logger.info("Starting")
discord_logger.info("Starting")
bot.run(config["discord_token"])
