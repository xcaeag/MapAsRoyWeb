import sys
import os
import uuid
import zipfile
from datetime import datetime

from qgis.PyQt.QtCore import QSizeF, QTimer, QEventLoop, QSettings
from qgis.PyQt.QtGui import QFontDatabase

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsProcessingUtils,
    QgsCoordinateReferenceSystem,
    QgsLayoutExporter,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsRectangle,
    QgsCoordinateTransform,
)

sys.path.append("src")
sys.path.append("../src")
sys.path.append("/app")
sys.path.append("/usr/share/qgis/python/plugins")

from mytools import tools
from conf import MapConf

from consts import PREFIX_PATH, TEMPLATE_QGIS

global qgsapp
qgsapp = None


def qgisInitOffscreen(installPath):
    global qgsapp
    global prj

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QgsApplication.setPrefixPath(sys.prefix, True)
    QgsApplication.setPrefixPath(installPath, True)

    if qgsapp is None:
        qgsapp = QgsApplication([], False)
        qgsapp.initQgis()

    qfontdatabase = QFontDatabase()
    fonts_dir = os.path.abspath(os.path.join(".", "resources", "fonts"))

    if os.path.isdir(fonts_dir):
        for root, _, files in os.walk(fonts_dir):
            for fname in files:
                if fname.lower().endswith((".otf", ".ttf")):
                    try:
                        qfontdatabase.addApplicationFont(
                            os.path.join("./resources/fonts/", fname)
                        )
                    except Exception:
                        # ignorer une fonte problématique
                        pass

    svg_paths = [os.path.abspath(os.path.join(".", "resources", "svg"))]

    QSettings().setValue("svg/searchPathsForSVG", svg_paths)


def qgisOpenProject(prj, filename):
    prj.read(filename)


def qgisClose():
    global qgsapp
    if qgsapp is not None:
        qgsapp.exit()
    qgsapp = None


def wait_for_rendering():
    loop = QEventLoop()
    QTimer.singleShot(3000, loop.quit)  # Attendre un peu
    loop.exec_()


def qgisPrintLayout(
    prj,
    layoutName,
    outFile,
    svgFile=None,
    variables={},
    map="map",
    extent=None,
    size: QSizeF = None,
):
    print("qgisPrintLayout")

    # https://gis.stackexchange.com/questions/153648/accessing-layers-visibility-presets
    projectLayoutManager = prj.layoutManager()

    vars = prj.customVariables()
    for k, v in variables.items():
        vars[k] = v
    prj.setCustomVariables(vars)

    layout = projectLayoutManager.layoutByName(layoutName)
    if layout is None:
        raise Exception(f"Layout {layoutName} absent")

    # redimensionner la page (en proportion)
    if size is not None:
        fxy = size.width() / size.height()
        pw = layout.pageCollection().page(0).pageSize().width()
        ph = layout.pageCollection().page(0).pageSize().height()
        layout.pageCollection().page(0).setPageSize(
            QgsLayoutSize(QSizeF(pw * fxy, ph), layout.units())
        )

    exporter = QgsLayoutExporter(layout)

    if map:
        print("Map layout ok")
        map_item = layout.itemById(map)
        if map_item is not None:
            print("Map item ok")
            # redimensionner la carte
            if size is not None:
                map_item.setRect(0, 0, size.width(), size.height())
                map_item.attemptMove(
                    QgsLayoutPoint(0, 0, map_item.sizeWithUnits().units())
                )
                map_item.attemptResize(
                    QgsLayoutSize(
                        map_item.sizeWithUnits().width() * fxy,
                        map_item.sizeWithUnits().width(),
                        map_item.sizeWithUnits().units(),
                    )
                )

            if extent:
                map_item.zoomToExtent(extent)

    print("triggerRepaint")
    for layer in QgsProject.instance().mapLayers().values():
        layer.triggerRepaint()

    print("wait_for_rendering")
    wait_for_rendering()

    print(outFile)
    settings = exporter.ImageExportSettings()
    exporter.exportToImage(outFile, settings)

    if svgFile is not None:
        print("SvgExportSettings")
        settings = exporter.SvgExportSettings()
        # settings.forceVectorOutput = True
        exporter.exportToSvg(svgFile, settings)


class MapExporter:
    """
    Returns:
        dict: l'ensemble des noms de fichiers produits
    """

    TOP, BOTTOM, LEFT, RIGHT = "T", "B", "L", "R"

    def __init__(self, wdir=None, jobid=None, conf=None):
        print("MapExporter.init")
        self.WDIR = wdir if wdir is not None else QgsProcessingUtils.tempFolder()
        self.pluginPath = QgsApplication.qgisSettingsDirPath()
        self.project_template = TEMPLATE_QGIS
        self.prj = QgsProject.instance()
        self.jobid = jobid
        self.layers = []

        self.mapConf = conf

        self.rectExt = QgsRectangle(
            *[
                self.mapConf.xmin,
                self.mapConf.ymin,
                self.mapConf.xmax,
                self.mapConf.ymax,
            ]
        )

        if self.rectExt.xMinimum() <= 180 and self.rectExt.xMaximum() > 180:
            self.destCrs = QgsCoordinateReferenceSystem("EPSG:3832")
        else:
            self.destCrs = QgsCoordinateReferenceSystem("EPSG:3857")

        self.srcCrs = QgsCoordinateReferenceSystem("EPSG:4326")
        X = QgsCoordinateTransform(self.srcCrs, self.destCrs, QgsProject.instance())
        self.rectExt = X.transform(self.rectExt)

        if not os.path.exists(wdir):
            raise Exception(f"Le répertoire de travail {wdir} n'existe pas")

    def progress(self, p, message=""):
        # sauver progression (fichier au format json) pour suivi
        percent = int(p)

        # sauver dans un fichier json
        tools.saveJson(
            {
                "status": "processing",
                "percent": percent,
                "message": message,
                "date": datetime.now().isoformat(),
            },
            f"{self.WDIR}/{self.jobid}/progress.json",
        )

    def progressError(self, p, message=""):
        # sauver progression (fichier au format json) pour suivi
        percent = int(p)

        # sauver dans un fichier json
        tools.saveJson(
            {
                "status": "error",
                "percent": percent,
                "message": message,
                "date": datetime.now().isoformat(),
            },
            f"{self.WDIR}/{self.jobid}/progress.json",
        )

    def run(self):
        print("run")
        try:
            self.progress(5, "qq préparations")
            out = {}
            tools.purgeOldDirs(self.WDIR, 1)

            if not os.path.exists(f"{self.WDIR}/{self.jobid}"):
                os.makedirs(f"{self.WDIR}/{self.jobid}")

            # exporter une version image de la carte
            print(self.project_template)
            if os.path.exists(self.project_template):
                self.progress(10, "qq préparations")
                qgisOpenProject(self.prj, self.project_template)
                self.prj.setCrs(self.destCrs)

                self.progress(30, "export de la carte")

                qgisPrintLayout(
                    self.prj,
                    "carre",
                    f"{self.WDIR}/{self.jobid}/map.jpg",
                    svgFile=f"{self.WDIR}/{self.jobid}/map.svg",
                    map="map",
                    extent=self.rectExt,
                )

                self.progress(60, "un zoom")
                self.rectExt.scale(0.2)
                qgisPrintLayout(
                    self.prj,
                    "carre",
                    f"{self.WDIR}/{self.jobid}/zoom.jpg",
                    map="map",
                    extent=self.rectExt,
                )

                out["svg"] = "map.svg"
                out["jpg"] = "map.jpg"
                out["zoom"] = "zoom.jpg"

            # ZIP
            self.progress(80, "export zip")
            try:
                with zipfile.ZipFile(
                    f"{self.WDIR}/{self.jobid}/mapasroy.zip", mode="w"
                ) as archive:
                    for nf in out.values():
                        if nf is not None:
                            archive.write(f"{self.WDIR}/{self.jobid}/{nf}", nf)

                    archive.write(
                        os.path.join(
                            os.path.dirname(self.project_template), "lisezmoi.txt"
                        ),
                        "lisezmoi.txt",
                    )

                out["zip"] = "mapasroy.zip"
            except Exception:
                pass

            tools.saveJson(
                {
                    "status": "done",
                    "percent": 100,
                    "message": "FIN  :-)",
                    "date": datetime.now().isoformat(),
                    "out": out,
                },
                f"{self.WDIR}/{self.jobid}/progress.json",
            )

        except Exception as e:
            self.progressError(0, f"{e}")
            raise e

        return out


def mapAsRoy(jobid, wdir, conf):
    try:
        print("mapAsRoy")
        algo = MapExporter(jobid=jobid, wdir=wdir, conf=conf)
        r = algo.run()
    except Exception as e:
        print(f"{e}")
    finally:
        qgisClose()

    return r


if __name__ == "__main__":
    wdir = sys.argv[1]
    jobid = sys.argv[2] or uuid.uuid4().hex

    if len(sys.argv) < 4:
        conf = MapConf.from_file(f"{wdir}/{jobid}/conf.json")
    else:
        conf = MapConf()
        conf.baseLayer = sys.argv[3]  # osm_standard osm_topo
        conf.width = int(sys.argv[4]) if len(sys.argv) > 4 else 350
        conf.xmin = float(sys.argv[5]) if len(sys.argv) > 5 else -0.1
        conf.ymin = float(sys.argv[6]) if len(sys.argv) > 6 else 42
        conf.xmax = float(sys.argv[7]) if len(sys.argv) > 7 else 0.9
        conf.ymax = float(sys.argv[8]) if len(sys.argv) > 8 else 42.8

    qgisInitOffscreen(PREFIX_PATH)
    r = mapAsRoy(jobid, wdir, conf)
