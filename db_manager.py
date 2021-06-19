from json import loads, dumps
import logging
from os import environ

import psycopg2

conn = None
cursor = None
is_postgres = False
if "discord_token" in environ:
    from psycopg2 import connect
    conn = psycopg2.connect(
        database=environ["db_db"],
        user=environ["db_user"],
        password=environ["db_pw"],
        host=environ["db_host"],
        port=environ["db_port"]
    )
    cursor = conn.cursor()
    is_postgres = True
else:
    from sqlite3 import connect

    conn = connect("./data/servers.sql")
    cursor = conn.cursor()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if "discord_token" in environ:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("db_manager - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    handler = logging.FileHandler(filename="./data/logs/db.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.info("Starting")


def exec_query(query, values):
    if is_postgres:
        cursor.execute(query.replace("?", "%s"), values)
    else:
        cursor.execute(query, values)


def setup():
    if is_postgres:
        cursor.execute("""
CREATE TABLE IF NOT EXISTS servers (
    server_id INTEGER PRIMARY KEY,
    config TEXT
);""")
    else:
        cursor.execute("""
CREATE TABLE IF NOT EXISTS servers(
    server_id int PRIMARY KEY,
    config str
);""")
    conn.commit()
    logger.info("Set up DB")


def new_server(server_id):
    config = {
        "prefix": "sv!",
        "manager_role_id": 0,
        "server_status_channel": 0
    }
    config_str = dumps(config)
    exec_query("INSERT INTO servers VALUES (?, ?);", (server_id, config_str))
    conn.commit()
    logger.info("Server with id " + str(server_id) + " created")


def get_server(server_id):
    exec_query("SELECT * FROM servers WHERE server_id = ?;", [server_id])
    return loads(cursor.fetchone()[1])


def update_server(server_id, config):
    logger.info("Server with id " + str(server_id) + " reconfigured")
    config_str = dumps(config)
    exec_query("UPDATE servers SET config = ? WHERE server_id = ?;", (config_str, server_id))
    conn.commit()


def del_server(server_id):
    logger.info("Server with id " + str(server_id) + " deleted")
    exec_query("DELETE FROM servers WHERE server_id = ?;", [server_id])
    conn.commit()


def add_if_not_exists(server_id):
    exec_query("SELECT * FROM servers WHERE server_id = ?;", [server_id])
    if not cursor.fetchone():
        new_server(server_id)


def get_servers():
    cursor.execute("SELECT server_id FROM servers;")
    return cursor.fetchall()
