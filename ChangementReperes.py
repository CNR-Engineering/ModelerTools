#!/usr/bin/env python3
"""
Changement de repère d'un semis de points

Un fichier d'entrée (au format CSV) contenant l'ensemble des points à traiter est lu. Ce fichier contient au moins 2 colonnes correspond aux coordonnées selon les axes X et Y, les autres colonnes étant simplement copiées sans modification. À partir de ce fichier décrivant les transformations nécessaires pour un ou plusieurs changements de repères, tous changements de repère indirects, dérivés et inverses sont déduits et pourront être demandés par l'utilisateur.
"""
# TODO?
#* ne pas ecraser les colonnes d'origine
#* erreur conversion en float

import csv
import functools
import logging
import math
import networkx as nx
import sys
import xml.etree.ElementTree as ET

LOG_FORMAT = "%(message)s"
LOG_POINT_FREQUENCY = 10000


# Change function representation
# Inspiration from: http://stackoverflow.com/questions/10875442/possible-to-change-a-functions-repr-in-python
class reprwrapper(object):
    def __init__(self, repr, func):
        self._repr = repr
        self._func = func
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kw):
        return self._func(*args, **kw)

    def __repr__(self):
        return self._repr(self._func)


def withrepr(reprfun):
    def _wrap(func):
        return reprwrapper(reprfun, func)
    return _wrap


class Point:
    """
    Point
    Attributes:
    * x = x coordinate
    * y = y coordinate
    * [z = z coordinate]
    """
    def __init__(self, x, y, z=None):
        """
        >>> Point(10, 50)
        <Point (10, 50)>
        >>> Point(10, 50).x
        10
        """
        self.x = x
        self.y = y
        if z is not None:
            self.z = z
        else:
            self.z = None

    def translate(self, dx, dy, dz=0):
        """
        Translate point with vector (dx, dy)

        >>> Point(10, 50).translate(20, 4)
        """
        self.x = self.x + dx
        self.y = self.y + dy
        if self.z:  # has z
            self.z = self.z + dz

    def rotate(self, angle_deg, xc, yc):
        """
        >>> Point(10, 50).rotate(50, 0, 10)
        """
        angle_rad = math.radians(angle_deg)
        x = xc + (self.x - xc)*math.cos(angle_rad) - (self.y - yc)*math.sin(angle_rad)  # temporary variable
        self.y = yc + (self.x - xc)*math.sin(angle_rad) + (self.y - yc)*math.cos(angle_rad)
        self.x = x

    def homothecy(self, kh, kv, xc, yc):
        """Homothety"""
        self.x = xc + kh*(self.x - xc)
        self.y = yc + kh*(self.y - yc)
        if self.z:
            self.z = kv*self.z

    def __repr__(self):
        return "<Point ({}, {})>".format(self.x, self.y)

    @staticmethod
    def auto_fun(method_name, args, kwargs={}):
        @withrepr(lambda x: "<Transformation: {} ({})>".format(method_name, args))
        def fun(point):
            """point <Point>"""
            return getattr(point, method_name)(*args, **kwargs)
        return fun


class ReferenceFrameConfig:
    """
    TODO
    Attributes:
    - root
    - graph
    - _logger
    """
    def __init__(self, config_xml, logger):
        """Parse xml configuration file"""
        tree = ET.parse(config_xml)
        self.root = tree.getroot()
        self.graph = nx.DiGraph()
        self._logger = logger

        reference_frames = self.root.find('ReferenceFrames')
        self.reference_frames_dict = {}
        if reference_frames:
            for i, reference_frame in enumerate(reference_frames):
                attrib = get_required_attributes(
                    "Le référentiel #{}".format(i),
                    reference_frame,
                    ['id', 'name']
                )
                self.graph.add_node(attrib['id'])
                if attrib['id'] in self.reference_frames_dict.keys():
                    sys.exit("Le référentiel '{}' existe déjà".format(attrib['id']))
                self.reference_frames_dict[attrib['id']] = attrib['name']
        else:
            sys.exit("La balise 'ReferenceFrames' est manquante ou vide")

    def get_transformations(self):
        changes_in_referece_frames = self.root.find('ChangesInReferenceFrames')
        if changes_in_referece_frames:
            for i, transformations in enumerate(changes_in_referece_frames):
                attrib = get_required_attributes(
                    "La transformation #{}".format(i),
                    transformations,
                    ['from', 'to']
                )

                function_processes = []
                reverse_function_processes = []
                for transf in transformations:
                    # Translation vector (dx, dy)
                    if transf.tag == "Translation":
                        try:
                            dx = float(transf.attrib['x'])
                        except KeyError:
                            dx = 0
                        try:
                            dy = float(transf.attrib['y'])
                        except KeyError:
                            dy = 0
                        try:
                            dz = float(transf.attrib['z'])
                        except KeyError:
                            dz = 0
                        function_processes.append(Point.auto_fun("translate", [dx, dy, dz]))
                        reverse_function_processes.append(Point.auto_fun("translate", [-dx, -dy, -dz]))

                    # Rotation of center (xc,yc) and with an angle in degree (anti-clockwise)
                    elif transf.tag == "Rotation":
                        try:
                            angle = float(transf.attrib['angle'])
                        except KeyError:
                            sys.exit("L'angle de la rotation (attribut 'angle') n'est pas renseigné")
                        try:
                            xc, yc = (float(x) for x in transf.attrib['center'].split(','))
                        except KeyError:
                            xc, yc = (0, 0)
                        function_processes.append(Point.auto_fun("rotate", [angle, xc, yc]))
                        reverse_function_processes.append(Point.auto_fun("rotate", [-angle, xc, yc]))

                    # Homothecy of center (x, yc) with a given ratio (|ratio|>1 => enlargement)
                    elif transf.tag == "Homothecy":
                        try:
                            kh = float(transf.attrib['kh'])
                        except KeyError:
                            kh = 1
                            self._logger.warn("Le rapport horizontal (attribut 'kh') de l'homothétie n'est pas renseigné. Il est pris égal à {}.".format(kh))
                        try:
                            kv = float(transf.attrib['kv'])
                        except KeyError:
                            kv = 1
                            self._logger.warn("Le rapport vertical (attribut 'kv') de l'homothétie n'est pas renseigné. Il est pris égal à {}.".format(kv))
                        try:
                            xc, yc = (float(x) for x in transf.attrib['center'].split(','))
                        except KeyError:
                            xc, yc = (0, 0)
                        function_processes.append(Point.auto_fun("homothecy", [kh, kv, xc, yc]))
                        reverse_function_processes.append(Point.auto_fun("homothecy", [1/kh, 1/kv, xc, yc]))
                    else:
                        sys.exit("La transformation '{}' est inconnue".format(transf.tag))

                # Check if nodes are in tag 'ReferenceFrames'
                # (This step is necessary because otherwise add_edge function would add nodes, but some information will be missing)
                if attrib['from'] not in self.reference_frames_dict.keys():
                    sys.exit("Le référentiel '{}' n'a pas de balise 'ReferenceFrame'".format(attrib['from']))
                if attrib['to'] not in self.reference_frames_dict.keys():
                    sys.exit("Le référentiel '{}' n'a pas de balise 'ReferenceFrame'".format(attrib['to']))

                # from -> to : stack of successive functions
                self.graph.add_edge(
                    attrib['from'],
                    attrib['to'],
                    function=function_processes
                )

                # to -> from : unstack of reverse functions
                reverse_function_processes.reverse()
                self.graph.add_edge(
                    attrib['to'],
                    attrib['from'],
                    function=reverse_function_processes
                )
        else:
            sys.exit("La balise 'ChangesInReferenceFrames' est manquante ou vide")


def get_required_attributes(instance_label, instance, attributes):
    attr_dict = {}
    for attr in attributes:
        try:
            attr_dict[attr] = instance.attrib[attr]
        except KeyError:
            sys.exit("{} n'a pas d'attribut '{}'".format(instance_label, attr))
    return attr_dict


def launch_main(args, logger):
    ref_frame_config = ReferenceFrameConfig(args.config_xml, logger)
    ref_frame_config.get_transformations()
    ref_frame_graph = ref_frame_config.graph

    # Check if reference frames exist
    logger.info("Liste des repères: {}".format(ref_frame_graph.nodes()))
    if args.source not in ref_frame_graph.nodes():
        sys.exit("Le référentiel en entrée '{}' n'existe pas".format(args.source))
    if args.target not in ref_frame_graph.nodes():
        sys.exit("Le référentiel en sortie '{}' n'existe pas".format(args.target))

    # Find path from source to target
    all_path = list(nx.all_simple_paths(ref_frame_graph, args.source, args.target))

    if len(all_path)==0:
        # No path found
        sys.exit("Aucun changement de possible repère entre '{}' et '{}'".format(args.source, args.target))

    elif len(all_path)==1:
        # Path is unique
        path = all_path[0]
        logger.info("Recherche des transformations pour le changement de repère '{}'->'{}' :".format(args.source, args.target))
        for r1, r2 in zip(path[:-1], path[1:]):
            logger.info("> Changement '{}'->'{}'".format(r1, r2))
            for transformation in ref_frame_graph.adj[r1][r2]['function']:
                logger.info("    - {}".format(transformation))

        # Compute transformation over each line of the input file
        with open(args.inname_csv, 'r', newline='') as in_csv:
            csv_reader = csv.DictReader(in_csv, delimiter=args.sep)

            # Check x and y column existancy
            if args.x not in csv_reader.fieldnames:
                sys.exit("La colonne '{}' n'est pas dans le fichier '{}'".format(args.x, args.inname_csv))
            if args.y not in csv_reader.fieldnames:
                sys.exit("La colonne '{}' n'est pas dans le fichier '{}'".format(args.y, args.inname_csv))

            mode = 'w' if args.force else 'x'
            with open(args.outname_csv, mode, newline='') as out_csv:
                logger.info("Début écriture {}".format(args.outname_csv))
                csv_writer = csv.DictWriter(out_csv, delimiter=args.sep, fieldnames=csv_reader.fieldnames)
                csv_writer.writeheader()

                def float_from_row(row, item):
                    try:
                        row[item]
                    except ValueError:
                        sys.exit("La colonne {} n'existe pas".format(item))
                    try:
                        return float(row[item])
                    except:
                        sys.exit("La valeur {} n'est pas un flottant".format(row[item]))

                # Iterate over each line
                for i, row in enumerate(csv_reader):
                    x = float(row[args.x])
                    y = float(row[args.y])
                    if args.z:
                        z = float(row[args.z])
                        pt = Point(x, y, z)
                    else:
                        pt = Point(x, y)

                    for r1, r2 in zip(path[:-1], path[1:]):
                        for transformation in ref_frame_graph.adj[r1][r2]['function']:
                            transformation(pt)

                    fmt_str = "{:."+str(args.digits)+"f}"
                    row[args.x] = fmt_str.format(pt.x)
                    row[args.y] = fmt_str.format(pt.y)
                    if args.z:
                        row[args.z] = fmt_str.format(pt.z)

                    if i % LOG_POINT_FREQUENCY == 0:
                        logger.debug("{}: {}, {}".format(i, row[args.x], row[args.y]))
                    csv_writer.writerow(row)

                logger.info("Fin du fichier, {} points traités".format(i+1))

    else:
        # Multiple paths
        sys.exit("""Liste des chemins possibles : {}
    ERREUR: Plusieurs suites de transformations possibles pour {}->{}""".format(all_path, args.source, args.target))

    return 0


if __name__ == "__main__":
    # logging.basicConfig()  # format="%(levelname)s: %(message)s"

    from common.arg_command_line import myargparse
    parser = myargparse(description=__doc__, add_args=['force', 'verbose'], lang='fr')
    parser.add_argument("inname_csv", help="Fichier d'entrée csv")
    parser.add_argument("outname_csv", help="Fichier de sortie csv")
    parser.add_argument("config_xml", help="Fichier de configuration xml des repères")
    parser.add_argument("source", help="Repère en entrée")
    parser.add_argument("target", help="Repère en sortie")
    parser.add_argument("--x", help="Nom de la colonne x", default='x')
    parser.add_argument("--y", help="Nom de la colonne y", default='y')
    parser.add_argument("--z", help="Nom de la colonne z")
    parser.add_argument("--sep", help="Sépérateur de colonnes", default=';')
    parser.add_argument("--digits", type=int, help="Nombre de chiffres significatifs des flottants à écrire", default=4)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    else:
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logger = logging.getLogger(__name__)

    try:
        launch_main(args, logger)
    except SystemError as e:
        logger.fatal(e)
        logger.fatal("L'exécution a échoué à cause de l'erreur ci-dessus")
        sys.exit(1)

    sys.exit(0)
