"""One-time Garmin Connect login.

Run it yourself in a terminal (in Claude Code, type:  ! .venv/bin/python login.py).
Your password is typed into a hidden prompt, used once, and never saved.
Only Garmin's login token is saved, to ~/.garminconnect (or $GARMINTOKENS),
so sync.py can run later without asking for your password again.
"""

import getpass
import os
import sys
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

TOKENSTORE = os.getenv("GARMINTOKENS", str(Path.home() / ".garminconnect"))


def main() -> int:
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password (hidden as you type): ")

    def ask_mfa() -> str:
        return input("Garmin sent you a verification code. Enter it: ").strip()

    garmin = Garmin(email=email, password=password, prompt_mfa=ask_mfa)
    del password
    try:
        garmin.login(TOKENSTORE)
    except GarminConnectAuthenticationError:
        print("Login failed: Garmin rejected the email, password, or code. Try again.")
        return 1
    except GarminConnectTooManyRequestsError:
        print("Garmin is rate-limiting logins right now. Wait an hour and try again.")
        return 1
    except GarminConnectConnectionError as e:
        print(f"Could not reach Garmin: {e}")
        return 1

    # The library writes the token file owner-only (0600); nothing else to do.
    print(f"Logged in as {garmin.get_full_name()}. Token saved; you won't need to log in again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
