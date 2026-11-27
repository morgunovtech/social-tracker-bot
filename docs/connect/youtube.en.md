# ▶️ YouTube

🇷🇺 [По-русски](youtube.md) · [All connections](../SETUP.en.md#the-other-connections)

Once a day the bot reads your channel's subscriber count, and every half hour it compares the channel's title, description, avatar and video count — vanished videos and a stranger's link in the description are often the first signs of a hijack.

## How long it takes and what you need

About 5 minutes, a Google account and your channel id. The YouTube key is free: Google's daily quota is far more than the bot needs.

## Steps

1. **Channel id.** [studio.youtube.com](https://studio.youtube.com) → «Settings» → «Channel» → «Advanced settings» → «Channel ID»: 24 characters starting with `UC`. A link like `youtube.com/channel/UC…` works too.
2. **A Google Cloud project.** Open [console.cloud.google.com](https://console.cloud.google.com/), the project picker at the top → «New project», any name → «Create».
3. **Enable the API.** Type «YouTube Data API v3» into the search at the top, open it and press «Enable».
4. **The key.** «APIs & Services» → «Credentials» → «Create credentials» → «API key». Copy the key.
5. **Restrict the key** (recommended): in the key's window, «Edit API key» → «API restrictions» → «Restrict key» → tick only «YouTube Data API v3» → «Save». A leaked key is then good for nothing else.
6. **In the bot:** 🔌 Connections → «➕ YouTube» → send the channel id, then the key. The bot checks the pair with a live request to your channel, deletes the message with the key at once and starts collecting.

## What the bot reads and where it goes

Once a day, your channel's statistics with your key (`googleapis.com`); every half hour, the title, description, avatar and video count. The key is kept in the bot's database and never reaches the backup or the log.

## How to switch it off and remove it

🔌 Connections → «✏️ YouTube» → send «-». Delete the key in Google Cloud: «APIs & Services» → «Credentials» → the key → «Delete»; or delete the whole project.
