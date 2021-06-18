## To set up your own instance of the bot:

 * Set up python 3.9, install discord.py
 * Make a discord application, create bot in that application and copy the key
 * If you want to allow usage of the market command:
     * Make a surviv account, link it (to discord, google, apple, etc.). Open devtools using ctl+shift+i, go to network, and type `api` in the search bar
     * Copy down:
       * The surviv user id (look for `profile`)
       * The last usage of `app-sid` in the response headers section (of any api request)
     * Then clear cookies WHILE THE WEBSITE IS OPEN, if the `app-sid` changes (the client makes an api request), the market command won't work
 * Copy `main.py` and `db_manager.py` into the directory you want to run from
 * Make a directory inside this directory called data
 * Inside data, put `config.json`, which should contain the values:
    * `discord_token`: the token you copied in the first step
    * `discord_feedback_user_id`: the user id of the discord account that bot dms will be forwarded to
    * `discord_join_link`: the text message that will be displayed when someone uses the invite command
    * `market_enable`: `false` if you didn't set up a new surviv account, if you did then set to `true` and:
        * `surviv_id`: a `string` containing the surviv account id
        * `surviv_app_sid`: a string containing `app-sid` (not app-sid=xyz, or xyz; other-stuff, just xyz). This will update after market requests
 * Run main.py to start the bot

### Some notes

Dm the bot `shutdown` without any caps or spaces to stop main.py.  
Dm the bot `block [user id]` to stop the bot reacting the discord account with [user-id] (this includes DMs, use it if someone is spamming you).
