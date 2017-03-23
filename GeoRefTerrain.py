"""
Géoréférencer des photos

Par défaut, les photos sont géoréférencées à l'aide des méta-données du fichier et cela fonctionne uniquement si l'appareil photgraphique utilise le GPS.
Dans le cas contrainte, il faut utiliser l'option `--interpolation` qui recalcule les coordonnées à l'aide d'une trace GPS et de l'horodatage de l'image.

L'horodatage des photos utilisé est la date de prise de vue.
Ce comportement peut être changé si nécessaire avec l'option `--date_type` (en spécifiant un entier)
En général, on utilisera l'argument `--decal_temps` pour faire correspondre les dates du GPS et de l'appareil photo.

Les exports possibles sont :
* `kml` : trace GPS et géolocalisation des photos
* `shp`
** Semis de points : géolocalisation des photos
** Polylignes : trace GPS
"""
import datetime
import fiona
from jinja2 import Environment, FileSystemLoader
from glob import glob
import logging
import numpy as np
import os.path
from PIL import Image
from PIL.ExifTags import TAGS
import shapely.geometry as geom
from shapely.geometry import mapping
import sys
import xml.etree.ElementTree as ET

from common.read_gps_medatadata import get_exif_data, get_lat_lon


# Lowercase only because corresponding uppercase extensions are appended automatically by glob
EXTENSIONS = ['jpg', 'jpeg', 'png']

logger = logging.getLogger(__name__)


class Point:
    """
    Attributs:
    lat, lon, ele, date, time? => string
    """
    def __init__(self):
        self.lat = None
        self.lon = None
        self.ele = None
        self.date = None

    def set_coord(self, lat, lon, ele):
        self.lat = lat
        self.lon = lon
        self.ele = ele

    def set_date(self, date):
        self.date = date

    def time_from_date(self, date):
        """Compute difference in seconds"""
        return (self.date - date).total_seconds()

    def __repr__(self):
        return "POINT: Coord=({}, {}, {}) Date={}".format(self.lat, self.lon, self.ele, self.date)


class Picture:
    """
    Handle Picture
    Attributes :
    * path = local or absolute path to picture
    * point = Point location
    """
    code_DateTimeDigitized = None
    DATE_TYPES = {
        # Dict format: id, (label, method name)
        1: ('Date de création', 'get_creation_date'),
        2: ('Date de modification', 'get_modification_date'),
        3: ('Date de prise de vue', 'get_date_taken')
    }

    @staticmethod
    def get_date_type(label2find):
        # Rebuild date_type number from label string
        for id, (label, _) in Picture.DATE_TYPES.items():
            if label == label2find:
                return id
        sys.exit("Le type de date '{}' n'est pas reconstituable".format(label2find))

    def __init__(self, path, point, link, label):
        self.path = path
        self.point = point
        self.link = link
        self.label = label
        self.abs_path = os.path.abspath(self.path)

        if not Picture.code_DateTimeDigitized:
            Picture.find_DateTimeDigitized_code()

    @staticmethod
    def find_DateTimeDigitized_code():
        """Find which code corresponds to the TAG `DateTimeDigitized`"""
        for c, value in TAGS.items():
            if value=='DateTimeDigitized':
                Picture.code_DateTimeDigitized = c
                break

    def set_position_from_gps_metadata(self):
        image = Image.open(self.path)
        exif_data = get_exif_data(image)
        lat, lon = get_lat_lon(exif_data)
        if not lat or not lon:
            logger.critical("Aucune coordonnée GPS renseignée dans le fichier '{}'".format(self.path))
            sys.exit(1)
        ele = 0  #FIXME!: elevation from GPS metadata
        self.point.set_coord(lat, lon, ele)

    def get_date_taken(self):
        try:
            info = Image.open(self.path)._getexif()
            return datetime.datetime.strptime(info[Picture.code_DateTimeDigitized], '%Y:%m:%d %H:%M:%S')
        except (KeyError, AttributeError):
            logger.critical("Aucune date de prise de vue pour le fichier '{}'".format(self.path))
            sys.exit(1)

    def get_modification_date(self):
        return datetime.datetime.fromtimestamp(round(os.path.getmtime(self.path), 0))

    def get_creation_date(self):
        return datetime.datetime.fromtimestamp(round(os.path.getctime(self.path), 0))

    def get_date(self, date_type):
        if date_type in Picture.DATE_TYPES.keys():
            return getattr(self, Picture.DATE_TYPES[date_type][1])()
        else:
            sys.exit("Type de date '{}' inconnu".format(date_type))


    def set_date(self, date_type):
        self.point.set_date(self.get_date(date_type))

    def __repr__(self):
        return "PICTURE: {} ({})".format(self.path, self.point)


class Gpx:
    """
    Attributes:
    * track: list of Point objects
    """
    PREFFIX = '{http://www.topografix.com/GPX/1/1}'
    DATEFORMAT = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, gpx_path):
        self._root = ET.parse(gpx_path).getroot()
        self._trk_child = None
        self.track = []

    def track_starting_date(self):
        return self.track[0].date

    def track_ending_date(self):
        return self.track[-1].date

    def _set_trk(self):
        if self._trk_child is None:
            self._trk_child = self._root.find(self.PREFFIX+'trk')

    def get_trk_name(self):
        self._set_trk()
        return self._trk_child.find(self.PREFFIX+'name').text

    def get_starting_time(self):
        self._set_trk()
        trkpt = self._trk_child.find(self.PREFFIX+'trkseg')[0]
        time = trkpt.find(self.PREFFIX+'time').text
        return datetime.datetime.strptime(time, self.DATEFORMAT)

    def iter_on_first_trkseg(self):
        self._set_trk()
        starting_date = self.get_starting_time()
        logger.debug("Starting date = {}".format(starting_date))

        for trkpt in self._trk_child.find(self.PREFFIX+'trkseg'):
            point = Point()
            pt_dict = trkpt.attrib  # create 'lat' and 'lon' keys

            # Get coordinates
            lat = float(pt_dict['lat'])
            lon = float(pt_dict['lon'])
            ele = float(trkpt.find(self.PREFFIX+'ele').text)
            point.set_coord(lat, lon, ele)

            # Get date
            date_str = trkpt.find(self.PREFFIX+'time').text
            date = datetime.datetime.strptime(date_str, self.DATEFORMAT)
            # time = (pt_dict['date'] - starting_date).total_seconds()
            point.set_date(date)

            # logger.debug(point)
            self.track.append(point)

    # def iter_images_on_first_trkseg(self):
    #     self._set_trk()

    #     for trkpt in self._trk_child.find(self.PREFFIX+'trkseg'):
    #         time = trkpt.find(self.PREFFIX+'time').text
    #         date = datetime.datetime.strptime(time, self.DATEFORMAT)

    #         image.set_coordinates(
    #             lat=trkpt.attrib['lat'],
    #             lon=trkpt.attrib['lat'],
    #             ele=trkpt.find(self.PREFFIX+'ele').text
    #         )


class TrackAndWayPoint:
    def __init__(self, track=[], images=[]):
        """
        :param track: list of Point objects
        :param images: list of Image objects
        """
        self.track = track
        self.images = images
        self.array_lat = None
        self.array_lon = None
        self.array_ele = None
        self.array_time = None
        self.zero_date = None

    def set_zero(self, date):
        self.zero_date = date

    def compute_arrays(self, timedelta=0):
        self.array_lat = np.array([pt.lat for pt in self.track])
        self.array_lon = np.array([pt.lon for pt in self.track])
        self.array_ele = np.array([pt.ele for pt in self.track])
        # self.array_date = np.array([pt.date for pt in self.track])
        self.array_time = np.array([(pt.date - self.zero_date).total_seconds() + timedelta for pt in self.track])
        self.min_time = np.amin(self.array_time)
        self.max_time = np.amax(self.array_time)

    def append_image(self, image):
        self.images.append(image)

    def write_kml(self, outpath):
        env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')))
        template = env.get_template('template_jinja_kml.xml')

        with open(outpath, 'w') as fileout:
            fileout.write(template.render(
                images=self.images,
                points=self.track,
                color="d2ffe1",
                opacity="ff",
            ))

    def write_shp_points(self, outpath):
        schema = {'geometry': '3D Point', 'properties': {'image_name': 'str', 'image_link': 'str', 'image_absp': 'str'}}
        with fiona.open(outpath, 'w', 'ESRI Shapefile', schema) as layer:
            for image in self.images:
                point = geom.Point(image.point.lon, image.point.lat, image.point.ele)
                elem = {}
                elem['geometry'] = mapping(point)
                elem['properties'] = {
                    'image_name': image.label,
                    'image_link': image.link,
                    'image_absp': image.abs_path
                }
                layer.write(elem)

    def write_shp_lines(self, outpath):
        schema = {'geometry': '3D LineString', 'properties': {'FID': 'int'}}
        with fiona.open(outpath, 'w', 'ESRI Shapefile', schema) as layer:
            linestring = geom.LineString([(pt.lon, pt.lat, pt.ele) for pt in self.track])
            elem = {}
            elem['geometry'] = mapping(linestring)
            elem['properties'] = {'FID': 0}
            layer.write(elem)

def list_images(folder, no_folder, date_type):
    #FIXME: use yield?
    liste = []
    for ext in EXTENSIONS:
        for image_path in glob(os.path.join(folder, '*' + ext)):
            image_basename = os.path.basename(image_path)
            if no_folder:
                image_link = image_basename
            else:
                image_link = image_path
            image = Picture(image_path, Point(), image_link, image_basename)
            image.set_date(date_type)
            liste.append(image)
    return liste

def launch_main(args, logger):
    """Launch main"""
    if args.gpx:
        logger.info("Lecture de la trace {}".format(args.gpx))
        gpx = Gpx(args.gpx)
        gpx.iter_on_first_trkseg()
        track = gpx.track
    else:
        track = []

    mykml = TrackAndWayPoint(track=track, images=[])

    # Build list of Picture objects
    images = []
    first = True

    logger.info("Parcours du dossier : {}".format(args.inname_folder))
    for image in list_images(args.inname_folder, args.no_folder, args.date_type):

        if args.interpolation:
            if not args.gpx:
                sys.exit("La trace GPX doit être renseignée pour interpoler les coordonnées")
            if first:
                # Compute track time series and arrays
                mykml.set_zero(gpx.get_starting_time())
                mykml.compute_arrays(args.decal_temps)
                logger.info("Date d'origine des temps = {}".format(mykml.zero_date))
                logger.info("Décalage du temps de trace de {} secondes".format(args.decal_temps))

            time = image.point.time_from_date(mykml.zero_date)
            if time < mykml.min_time or time > mykml.max_time:
                # Check if time in track measure range
                logger.warn("Le temps {} n'est pas dans l'intervalle de mesure [{},{}]".format(time, mykml.min_time,
                                                                                               mykml.max_time))
            logger.info("Temps = {}s".format(time))

            # Interpolate coordinates
            lat = np.interp(time, mykml.array_time, mykml.array_lat)
            lon = np.interp(time, mykml.array_time, mykml.array_lon)
            ele = np.interp(time, mykml.array_time, mykml.array_ele)
            image.point.set_coord(lat, lon, ele)
        else:
            image.set_position_from_gps_metadata()

        mykml.append_image(image)

        logger.info(image)

        if first:
            first = False

    if args.kml:
        logger.info("Écriture du fichier kml : {}".format(args.kml))
        mykml.write_kml(args.kml)
    if args.shp_points:
        logger.info("Écriture du fichier de points : {}".format(args.shp_points))
        mykml.write_shp_points(os.path.join(args.shp_points))
    if args.shp_lines:
        logger.info("Écriture du fichier de trace : {}".format(args.shp_lines))
        mykml.write_shp_lines(os.path.join(args.shp_lines))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)  #FIXME myargparse(description=__doc__)

    # INPUTS
    ext_text = "(extensions possibles : {})".format(', '.join(EXTENSIONS))
    date_text = ""
    for i, (id, (label, _)) in enumerate(Picture.DATE_TYPES.items()):
        if i != 0: date_text = date_text + ', '
        date_text = date_text + "{}={}".format(id, label)
    parser.add_argument("inname_folder", help="dossier contenant les images "+ext_text)
    parser.add_argument("--gpx", help="fichier de traces au format GPX")
    parser.add_argument("--date_type", help="type de date utilisée : "+date_text, type=int, default=3)
    parser.add_argument("--no_folder", help="les chemins exportés ne contiennent pas de dossier", action="store_true")
    parser.add_argument("--interpolation", help="interpole les coordonnées des images à partir de la trace (dans ce cas l'argument `--decal-temps` est utilisée)", action="store_true")
    parser.add_argument("--decal_temps", help="différence temporelle entre les dates de la trace et des images (en secondes)", type=float, default=0)

    # OUTPUTS
    parser.add_argument("--kml", help="fichier KML de sortie")
    parser.add_argument("--shp_points", help="fichier SHP de points")
    parser.add_argument("--shp_lines", help="fichier SHP de lignes")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")  # format="%(levelname)s: %(message)s"

    launch_main(args, logger)
