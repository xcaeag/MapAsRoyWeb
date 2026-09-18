from flask import Flask, render_template, redirect, url_for, session
from flask import send_from_directory, send_file
from werkzeug.utils import secure_filename

import sys
import logging
import threading
import os
import uuid
import shutil
from datetime import datetime
from forms.choosemap_form import ChooseMapForm
from mytools import tools
from conf import MapConf

from consts import (
    SECRET_KEY,
    BASE_URL_FOLDER,
    PYTHON_CMD,
    TMP_FOLDER,
)

sys.path.append("/usr/share/qgis/python/plugins")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_THRESHOLD"] = 100  # 500 is default

logging.basicConfig(
    filename="./log/flask.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s",
)
logger = logging.getLogger(__name__)


class SafeThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = None

    def run(self):
        try:
            if self._target:
                self._target(*self._args, **self._kwargs)
        except Exception as e:
            self.exception = e


def process_map_async(
    wdir="/tmp",
    jobid="an_uuid",
):
    import subprocess

    cmd = f"{PYTHON_CMD} qgislogic/printLayout.py {wdir} {jobid}"
    print(cmd)
    logger.info(cmd)

    r = subprocess.Popen(cmd.split(" "))

    return r


def refresh_status():
    try:
        jobs = dict(session["jobs"])
        for jobid, job in jobs.items():
            progress_file = os.path.join(TMP_FOLDER, jobid, "progress.json")

            try:
                json = tools.loadJson(progress_file)
                session["jobs"][jobid] = json
            except Exception:
                json = {"status": "error", "percent": 0, "message": "Supprimé"}

            if "status" not in job:
                del session["jobs"][jobid]

            if not os.path.exists(os.path.join(TMP_FOLDER, jobid)):
                del session["jobs"][jobid]

            try:
                job["datestr"] = datetime.fromisoformat(job["date"]).strftime(
                    "%d-%m-%Y %H:%M"
                )
            except Exception:
                job["datestr"] = "??"

        session.modified = True

    except Exception:
        pass


@app.route(f"{BASE_URL_FOLDER}", methods=["GET"])
def index():
    """
    Affiche la page d'accueil avec la liste des jobs en cours.
    """

    # Nettoyage des jobs terminés (vérifier l'existence du dossier)
    if "jobs" not in session:
        session["jobs"] = {}

    # rafraîchir status dernier job
    refresh_status()

    return render_template("index.html", jobs=session["jobs"])


@app.route(f"{BASE_URL_FOLDER}/progress")
def progress():
    return render_template("progress.html", uuid=session["uuid"])


@app.route(f"{BASE_URL_FOLDER}/progress_status")
def progress_status():
    progress_file = os.path.join(TMP_FOLDER, session["uuid"], "progress.json")

    try:
        json = tools.loadJson(progress_file)
    except Exception:
        json = {"status": "waiting", "percent": 0, "message": "?"}

    session["jobs"][session["uuid"]] = json
    session.modified = True
    return json


@app.route(f"{BASE_URL_FOLDER}/do", methods=["GET", "POST"])
def choose_location():
    form = ChooseMapForm()
    if form.validate_on_submit():

        # Nouveau boulot
        jobid = uuid.uuid4().hex
        session["uuid"] = jobid

        if "jobs" not in session:
            session["jobs"] = {}

        session["jobs"][jobid] = {}
        session.modified = True

        conf = MapConf(
            **{
                "baseLayer": "roy",
                "width": 300,
                "xmin": float(form.xmin.data),
                "ymin": float(form.ymin.data),
                "xmax": float(form.xmax.data),
                "ymax": float(form.ymax.data),
            }
        )

        if not os.path.exists(f"{TMP_FOLDER}/{jobid}"):
            os.makedirs(f"{TMP_FOLDER}/{jobid}")

        conf.to_file(f"{TMP_FOLDER}/{jobid}/conf.json")

        logger.info("process_map_async")

        thread = SafeThread(
            target=process_map_async, args=(TMP_FOLDER, jobid), daemon=True
        )
        thread.start()
        thread.join()

        if thread.exception:
            logger.info(f"Exception détectée dans le thread : {thread.exception}")

        return redirect(url_for("progress"))

    return render_template("map.html", form=form)


@app.route(f"{BASE_URL_FOLDER}/my_static/<filename>")
def my_static(filename):
    return send_file(os.path.join("static", filename))


@app.route(f"{BASE_URL_FOLDER}/image/<filename>")
def uploaded_image(filename):
    """Retourne l'image (binaire)"""
    file_path = os.path.join(TMP_FOLDER, session["uuid"], secure_filename(filename))
    try:
        return send_file(file_path, mimetype="image/jpg")
    except Exception:
        return None


@app.route(f"{BASE_URL_FOLDER}/uuidimage/<uuid>/<filename>")
def uuid_image(uuid, filename):
    """Retourne l'image (binaire)"""
    file_path = os.path.join(TMP_FOLDER, uuid, secure_filename(filename))
    return send_file(file_path, mimetype="image/jpg")


@app.route(f"{BASE_URL_FOLDER}/download/image/<filename>")
def download_image(filename):
    return send_from_directory(
        f"{TMP_FOLDER}/{session["uuid"]}",
        f"{filename}",
        as_attachment=True,
        download_name=f"{filename}",
    )


@app.route(f"{BASE_URL_FOLDER}/remove/archive/<uuid>")
def remove_archive(uuid):
    toDelete = os.path.join(TMP_FOLDER, uuid)
    try:
        shutil.rmtree(toDelete)
    finally:
        try:
            del session["jobs"][uuid]
            session.modified = True
        except Exception:
            pass

    return redirect(url_for("index"))


@app.route(f"{BASE_URL_FOLDER}/download/archive/<uuid>")
def download_archive(uuid):
    return send_from_directory(
        f"{TMP_FOLDER}/{uuid}",
        "mapasroy.zip",
        as_attachment=True,
        download_name="mapasroy.zip",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
