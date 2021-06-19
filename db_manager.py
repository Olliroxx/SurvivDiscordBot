from json import loads, dumps
import logging
from os import environ

import psycopg2

conn = None
cursor = None
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
else:
    from sqlite3 import connect

    conn = connect("./data/servers.sql")
    cursor = conn.cursor()

if "discord_token" in environ:
    logging.basicConfig(format="%(name)s - %(message)s", level=logging.INFO)
else:
    logging.basicConfig(filename="./data/logs/db.log", filemode="w", format="%(asctime)s - %(message)s", level=logging.INFO)


def setup():
    cursor.execute("""CREATE TABLE IF NOT EXISTS servers(
    server_id int PRIMARY KEY,
    config str
);
    """)
    conn.commit()
    logging.info("Set up DB")


def new_server(server_id):
    config = {
        "prefix": "sv!",
        "manager_role_id": 0,
        "server_status_channel": 0
    }
    config_str = dumps(config)
    cursor.execute("INSERT INTO servers VALUES (?, ?)", (server_id, config_str))
    conn.commit()
    logging.info("Server with id " + str(server_id) + " created")


def get_server(server_id):
    cursor.execute("SELECT * FROM servers WHERE server_id = ?", [server_id])
    return loads(cursor.fetchone()[1])


def update_server(server_id, config):
    logging.info("Server with id " + str(server_id) + " reconfigured")
    config_str = dumps(config)
    cursor.execute("UPDATE servers SET config = ? WHERE server_id = ?", (config_str, server_id))
    conn.commit()


def del_server(server_id):
    logging.info("Server with id " + str(server_id) + " deleted")
    cursor.execute("DELETE FROM servers WHERE server_id = ?", [server_id])
    conn.commit()


def add_if_not_exists(server_id):
    cursor.execute("SELECT * FROM servers WHERE server_id = ?", [server_id])
    if not cursor.fetchone():
        new_server(server_id)


def get_servers():
    cursor.execute("SELECT server_id FROM servers;")
    return cursor.fetchall()
