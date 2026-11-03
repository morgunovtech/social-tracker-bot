# Security

Please report vulnerabilities privately: on GitHub open **Security → Report a vulnerability** in this repository. Don't open a public issue for them.

What the bot holds and how it treats it:

- **Bot token, API keys** live only in environment variables. The httpx logger is kept at WARNING: at INFO it prints every Bot API URL, and those contain the token.
- **LinkedIn `li_at` cookie** is stored in the SQLite DB when set with `/setcookie`. The message carrying it is deleted from the chat right away, and the weekly backup the bot sends to the chat is made without it.
- **Access**: every command and button checks that the user is `ADMIN_CHAT_ID`; everyone else is refused.
