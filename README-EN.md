[![Static Badge](https://img.shields.io/badge/Telegram-Bot%20Link-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/qlyukerbot/start?startapp=bro-1197825376)
[![Static Badge](https://img.shields.io/badge/Telegram-Channel-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/CyberToolz)


#  Bot for Qlyuker


# 🔥🔥 PYTHON version must be 3.10 - 3.11.5 🔥🔥

> README на русском языке доступно [здесь](README.md)

## Features
|                    Feature                    |   Supported    |
|:---------------------------------------------:|:-------------  -:|
|                Multithreading                 |       ✔️         |
|         Proxy binding to the session          |       ✔️         |
| Auto-registration of the account via ref link |       ✔️         |
|          Automatic booster upgrades           |       ✔️         |
|        Pyrogram .session file support         |       ✔️         |


## [Settings](https://github.com/Mffff4/qlyukerbot/blob/main/.env-example/)
|           Setting           |                                      Description                                       |
|:---------------------------:|:--------------------------------------------------------------------------------------:|
|    **API_ID / API_HASH**    | Data from the platform where the Telegram session will be launched (default - android) |
|   **MIN_TAPS / MAX_TAPS**   |                   Number of taps per cycle (default from 10 to 100)                    |
| **MIN_SLEEP_BETWEEN_TAPS**  |                    Minimum delay between taps (default - 1 second)                     |
| **MAX_SLEEP_BETWEEN_TAPS**  |                    Maximum delay between taps (default - 3 seconds)                    |
|    **ENERGY_THRESHOLD**     |                     Energy threshold for actions (default - 0.05)                      |
|   **SLEEP_ON_LOW_ENERGY**   |                  Waiting time with low energy (default - 15 minutes)                   |
|   **SLEEP_AFTER_UPGRADE**   |                       Delay after upgrading (default - 1 second)                       |
|    **SLEEP_AFTER_TAPS**     |                  Delay after all taps are done (default - 0 seconds)                   |
| **MIN_DELAY_BETWEEN_TASKS** |            Minimum delay time between task executions (default - 3 seconds)            |
| **MAX_DELAY_BETWEEN_TASKS** |      Maximum delay time between task executions (default - 15 seconds)                 |
|   **USE_PROXY_FROM_FILE**   |                 Use proxy from `bot/config/proxies.txt` (True / False)                 |


## Quick Start 📚

To fast install libraries and run bot - open `run.bat` on **Windows** or `run.sh` on **Linux**

## Prerequisites
Before you begin, make sure you have the following installed:
- [**Python**](https://www.python.org/downloads/release/python-3100/) **version 3.10**

## Obtaining API Keys
1. Go to [**my.telegram.org**](https://my.telegram.org/auth) and log in using your phone number.
2. Select `API development tools` and fill out the form to register a new application.
3. Record the `API_ID` and `API_HASH` provided after registering your application in the `.env` file.

## Installation
You can download the [**repository**](https://github.com/Cybertat1on/Qlyuker) by cloning it to your system and installing the necessary dependencies:
```shell
git clone https://github.com/Cybertat1on/Qlyuker.git
cd Qlyuker
```

Then you can do automatic installation by typing:

Windows:
```shell
run.bat
```

Linux:
```shell
run.sh
```

# Linux manual installation
```shell
sudo sh install.sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env-example .env
nano .env  # Here you must specify your API_ID and API_HASH, the rest is taken by default
python3 main.py
```

You can also use arguments for quick start, for example:
```shell
~/Qlyuker >>> python3 main.py --action (1/2)
# Or
~/Qlyuker >>> python3 main.py -a (1/2)

# 1 - Run clicker
# 2 - Creates a session
```

# Windows manual installation
```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env-example .env
# Here you must specify your API_ID and API_HASH, the rest is taken by default
python main.py
```

You can also use arguments for quick start, for example:
```shell
~/Qlyuker >>> python main.py --action (1/2)
# Or
~/Qlyuker >>> python main.py -a (1/2)

# 1 - Run clicker
# 2 - Creates a session
```
