import os
import threading, platform, subprocess
from os.path import abspath

from sqlalchemy import create_engine

from hayStacked.request_reports import request_reports

anisette = None

db = create_engine('sqlite:///gears.db')
auth = abspath(os.path.join("secrets", "auth.json"))
keys = abspath(os.path.join("secrets", "keys"))

def getLocations():
    """Queries the Apple server to get Tag locations. Writes locations to local database"""

    global anisette
    anisette = None
    if anisette is None:
        def start_anisette():
            global anisette
            print("started anisette")
            if platform.system() == "Windows":
                anisette = subprocess.Popen("./hayStacked/anisette-v3-server/anisette-v3-server.exe")
            else:
                anisette = subprocess.Popen("./hayStacked/anisette-v3-server/anisette-v3-server")
            output, error = anisette.communicate()
            anisette.wait()
            anisette.terminate()
            # anisette = None

        print("Attempting to start anisette...")

        threading.Thread(target=start_anisette, daemon=True).start()

        print("Anisette instance:", anisette)

        request_reports(anisette, db, auth, keys, hours=24)
        # t = threading.Timer(1, lambda: threading.Thread(target=request_reports, args=(anisette, db), daemon=True).start())
        # t.start()
    else:
        print("Hold on, another instance of anisette is running.")

getLocations()