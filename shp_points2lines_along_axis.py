#!/usr/bin/env python
"""
@brief:
Cette routine permet d'identifier des profils et de classer des points dans ces derniers
en fonction de la distance dans un semis de point shp à partir de la localisation d'un axe hydraulique
Tous les fichiers sont au format shp.

Les profils sont décrits de la rive gauche à la rive droite (l'axe définit l'amont et l'aval).
"""
import argparse
import fiona
from fiona.crs import from_epsg
import numpy as np
from shapely.geometry import LineString, Point, mapping
import sys


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("inname_point", help="Semis de point d'entree au format shp")
parser.add_argument("inname_axe", help="Axe hydraulique d'entree au format shp")
parser.add_argument("outname_profil", help="Fichier shp de sortie en LineStringZ")
group_points = parser.add_mutually_exclusive_group(required=True)
group_points.add_argument("--field_profil_id", help="champ contenant les n° de profils (flottants ou entiers)")
group_points.add_argument("--profil_max_dist", help="distance maximale pour regrouper les points par profils",
                          type=float)
args = parser.parse_args()


DIST_VECT_DIR_AXE = 1.0
FIELD = args.field_profil_id if args.field_profil_id is not None else 'Profil'


def subset_data(data, id_profil):
    subdata = []
    for pt in data:
        if pt.id_profil == id_profil:
            subdata.append(pt)
    return subdata


def signe(number):
    """-1 if negative, 1 else"""
    try:
        return number/abs(number)
    except ZeroDivisionError:
        return 1


class Pt:
    def __init__(self, coord, id_profil):
        self.coord = coord
        self.geom = Point(self.coord)
        self.id_profil = id_profil
        self.abs_axe = geom_axe.project(self.geom)
        self.geom_proj = geom_axe.interpolate(self.abs_axe)
        self.dist = geom_axe.distance(self.geom)

    def __repr__(self):
        return "Pt: {}, ".format(self.id_profil) + str(self.coord)


class Profil:
    def __init__(self, id_profil, np_coord):
        self.id_profil = id_profil
        self.coord = np_coord
        if np_coord.shape[0] > 1:
            self.geom = LineString(np_coord)
        else:
            sys.exit("Profil #{} ne contient qu'un point !".format(id_profil))

    def __repr__(self):
        return "Profil {} ({} points)".format(self.id_profil, len(self.coord))

    def compute_Xt(self):
        Xt = np.sqrt(np.power(np.ediff1d(self.coord[:, 0], to_begin=0.), 2) +
                     np.power(np.ediff1d(self.coord[:, 1], to_begin=0.), 2))
        return Xt.cumsum()


# Axe hydraulique
coord = []
with fiona.open(args.inname_axe, 'r') as in_axe:
    for i, record in enumerate(in_axe):
        if i != 0:
            sys.exit("Le fichier d'axe contient plus qu'un objet")
        if record['geometry']['type'] == 'LineString':
            coord = record['geometry']['coordinates']
        else:
            sys.exit("Le fichier d'axe n'est pas de type `LineString`")
if not coord:
    sys.exit("Le fichier d'axe est vide")
geom_axe = LineString(coord)


# Points décrivant les profils en travers
data = []
with fiona.open(args.inname_point, 'r') as in_pts:
    if in_pts.schema['geometry'] != 'Point':  #FIXME: it should be written 3D Point but fiona does not although it has Z values
        sys.exit("Le fichier de points n'est pas de type `Point`")
    for record in in_pts:
        x, y, z = record['geometry']['coordinates']
        attr = None
        if args.field_profil_id is not None:
            try:
                attr = str(record['properties'][args.field_profil_id])
            except KeyError:
                sys.exit("L'attribut %s n'existe pas" % args.field_profil_id)
        pt = Pt((x, y, z), attr)
        data.append(pt)


# Regroupement par profil
if args.profil_max_dist is not None:
    # Avec un critère de "saut maximum" d'abscisse le long de l'axe
    data = sorted(data, key=lambda p: p.abs_axe)
    i_profil = 0
    prev_abs_axe = data[0].abs_axe
    for pt in data:
        if pt.abs_axe - prev_abs_axe > args.profil_max_dist:
            i_profil += 1
        pt.id_profil = i_profil
        prev_abs_axe = pt.abs_axe
else:
    # Avec l'attribut déjà lu précédemment
    pass

# Extraction de la liste des noms de profils
id_profils = []
for pt in data:
    if pt.id_profil not in id_profils:
        id_profils.append(pt.id_profil)

profils = []
for id_profil in sorted(id_profils):
    subdata = subset_data(data, id_profil)

    for pt in subdata:
        # Vecteur directeur axe au niveau de la projection du point
        pt_axe_avant = geom_axe.interpolate(pt.abs_axe - DIST_VECT_DIR_AXE)
        pt_axe_apres = geom_axe.interpolate(pt.abs_axe + DIST_VECT_DIR_AXE)
        dX_vect_dir_axe = pt_axe_apres.x - pt_axe_avant.x
        dY_vect_dir_axe = pt_axe_apres.y - pt_axe_avant.y

        # Vecteur de la projection au point
        dX_vect_norm_axe = pt.geom.x - pt.geom_proj.x
        dY_vect_norm_axe = pt.geom.y - pt.geom_proj.y

        det = dX_vect_dir_axe*dY_vect_norm_axe - dY_vect_dir_axe*dX_vect_norm_axe
        pt.dist = -signe(det)*pt.dist

    sorted_subdata = sorted(subdata, key=lambda p: p.dist)
    np_coord = np.array([pt.coord for pt in sorted_subdata])
    profil = Profil(id_profil, np_coord)
    profils.append(profil)


schema = {'geometry': '3D LineString', 'properties': {FIELD: 'str:32'}}
with fiona.open(args.outname_profil, 'w', 'ESRI Shapefile', schema, crs=from_epsg(3945)) as layer:
    for profil in profils:
        print("Profil #{}".format(profil))

        elem = {}
        elem['geometry'] = mapping(profil.geom)
        elem['properties'] = {FIELD: profil.id_profil}
        layer.write(elem)
