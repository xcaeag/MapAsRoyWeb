import json
import time
import os
import shutil


def saveJson(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("ERR saveJson", filename)
        raise e


def loadJson(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def purgeOldDirs(underDir="/tmp", days=10):
    if "home" in underDir:
        return

    if "tmp" not in underDir:
        return

    numdays = 86400 * days
    now = time.time()
    for r, d, _ in os.walk(underDir):
        for dir in d:
            timestamp = os.path.getmtime(os.path.join(r, dir))
            if now - numdays >= timestamp:
                try:
                    toDelete = os.path.join(r, dir)
                    shutil.rmtree(toDelete)
                except Exception as e:
                    print(e)
