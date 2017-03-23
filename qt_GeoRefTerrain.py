#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
TODO:
* get_ending_time
"""

import logging
import os
from PyQt4 import QtGui, QtCore
import sys

from common.qt_log_in_textbrowser import MyQWidget, ConsoleWindowLogHandler

from GeoRefTerrain import Gpx, launch_main, list_images, logger, Picture


DEBUG = True
DEFAULT_INDEX_METHOD = 2


class Worker(QtCore.QThread):
    def __init__(self, func, args):
        super(Worker, self).__init__()
        self.func = func
        self.args = args

    def run(self):
        try:
            self.func(*self.args)
        except SystemExit as e:
            logger.fatal(e)
            logger.fatal("L'exécution a échoué à cause de l'erreur ci-dessus")


class ExecutingWindow(MyQWidget):
    def __init__(self, args):
        super(ExecutingWindow, self).__init__()
        self.resize(800, 500)
        self.center()
        self.setWindowTitle("GeoRefTerrain")

        self.vbox = QtGui.QVBoxLayout()

        # Listing
        self._console = QtGui.QTextBrowser(self)
        self.vbox.addWidget(self._console)

        # Buttons
        self.button_cancel = QtGui.QPushButton('Annuler', self)
        self.button_quit = QtGui.QPushButton('Quitter', self)
        hbox = QtGui.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.button_cancel)
        hbox.addWidget(self.button_quit)
        self.vbox.addLayout(hbox)

        self.setLayout(self.vbox)

        # Connexions
        self.connect(self.button_cancel, QtCore.SIGNAL('clicked()'), self.close)
        self.connect(self.button_quit, QtCore.SIGNAL('clicked()'), QtCore.QCoreApplication.instance().quit)

        # Thread
        self.worker = Worker(launch_main, (args, logger))
        self.worker.start()

        # Console handler
        dummyEmitter = QtCore.QObject()
        self.connect(dummyEmitter, QtCore.SIGNAL("logMsg(QString)"), self._console.append)
        consoleHandler = ConsoleWindowLogHandler(dummyEmitter)
        logger.addHandler(consoleHandler)

    def scroll_down(self):
        self._console.verticalScrollBar().setValue(self._console.verticalScrollBar().maximum())


class ColorButton(QtGui.QPushButton):
    """
    ColorButton:
      QPushButton to select a color. The button background is changed automatically
    Example : my_button = ColorButton(ColorButton.RED)
    """
    RED = QtGui.QColor(255, 0, 0)
    GREEN = QtGui.QColor(0, 255, 0)

    def __init__(self, default_color):
        super(ColorButton, self).__init__()
        self._change_btn_color(default_color)
        self.clicked.connect(self.show_dialog)

    def _change_btn_color(self, col):
        self.setStyleSheet("QWidget { background-color: %s }" % col.name())

    def show_dialog(self):
        color_dialog = QtGui.QColorDialog()
        # color_dialog.setOption(QtGui.QColorDialog.ShowAlphaChannel, True)  # Unfortunately not working
        col = color_dialog.getColor()
        if col.isValid():
            self._change_btn_color(col)


class PathGroup(QtGui.QHBoxLayout):
    """
    Create a QtGui.QHBoxLayout object with a new attribute :
      path (QLabel)
    Requires multiple arguments
    """
    def __init__(self, main, label, mode, qdiag_fun, qdiag_caption, qdiag_ext=None):
        super().__init__()
        path_lbl = QtGui.QLabel(label)
        self.path = QtGui.QLineEdit()
        self.browse = QtGui.QPushButton('Parcourir', main)

        self.addWidget(path_lbl)
        self.addWidget(self.path)
        self.addWidget(self.browse)

        def check_path_exists():
            """Switch color of `self.path` whether the path exists"""
            if mode=='r':
                exists, no_file = (Main.GREEN, Main.RED)
            elif mode=='w':
                exists, no_file = (Main.RED, Main.GREEN)
            else:
                sys.exit("Mode '{}' is unknown".format(mode))
            self.path.isValid = False
            if os.path.exists(self.path.text()):
                self.path.setStyleSheet(exists)
                if mode=='r': self.path.isValid = True
            else:
                self.path.setStyleSheet(no_file)
                if mode=='w': self.path.isValid = True

        main.connect(self.path, QtCore.SIGNAL("textChanged(QString)"), check_path_exists)

        def select_file():
            if qdiag_ext:
                fname = getattr(QtGui.QFileDialog, qdiag_fun)(main, qdiag_caption, self.path.text(), qdiag_ext)
            else:
                fname = getattr(QtGui.QFileDialog, qdiag_fun)(main, qdiag_caption, self.path.text())
            if fname:
                self.path.setText(fname)

        main.connect(self.browse, QtCore.SIGNAL('clicked()'), select_file)

    def set_value(self, value):
        """Set value as new text"""
        self.path.setText(value)

    def setEnabled(self, boolean):
        self.path.setEnabled(boolean)
        self.browse.setEnabled(boolean)


class Main(MyQWidget):
    # RGB Colors
    RED = "color: rgb(128, 0, 0);"
    GREEN = "color: rgb(0, 128, 0);"

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.vbox = QtGui.QVBoxLayout()

        self.dir_images = PathGroup(self, "Dossier d'images", 'r', 'getExistingDirectory', "Sélectionner le dossier contenant les photos", None)
        self.vbox.addLayout(self.dir_images)

        # GPX
        self.gpx = PathGroup(self, "Fichier GPX", 'r', 'getOpenFileName', "Chercher une trace GPX existante", "Fichier GPX (*.gpx)")
        self.gpx.color = ColorButton(ColorButton.GREEN)
        self.gpx.addWidget(self.gpx.color)
        self.vbox.addLayout(self.gpx)

        # Interpolation
        self.interpolation = QtGui.QCheckBox("Calcul des coordonnées des images depuis la trace GPS")
        self.interpolation.setEnabled(False)
        self.vbox.addWidget(self.interpolation)

        # Horizontal line
        sep= QtGui.QFrame()
        sep.setFrameShape(QtGui.QFrame.HLine)
        self.vbox.addWidget(sep)

        # No folder
        self.no_folder = QtGui.QCheckBox("Écrire les chemins vers les images SANS les dossiers (juste le nom de l'image)")
        self.vbox.addWidget(self.no_folder)

        # KML
        self.kml = PathGroup(self, "Fichier KML", 'w', 'getSaveFileName', "Spécifier le fichier KML à générer", "Fichier KML (*.kml)")
        self.kml.color = ColorButton(ColorButton.RED)
        self.kml.addWidget(self.kml.color)
        self.vbox.addLayout(self.kml)

        # SHP
        self.shp_points = PathGroup(self, "Fichier SHP de points", 'w', 'getSaveFileName', "Spécifier le fichier shp de points à générer", "Fichier SHP (*.shp)")
        self.vbox.addLayout(self.shp_points)
        self.shp_lines = PathGroup(self, "Fichier SHP de la trace GPS", 'w', 'getSaveFileName', "Spécifier le fichier shp de polylignes à générer", "Fichier SHP (*.shp)")
        self.vbox.addLayout(self.shp_lines)

        if DEBUG:
            folder = "../validation/ModelerTools/GeoRefTerrain/data/images" #.replace('/', os.sep)
            self.gpx.set_value(os.path.join("../validation/ModelerTools/GeoRefTerrain/data", "Trace_OsmTracker.gpx"))
            self.kml.set_value(os.path.join("../validation/ModelerTools/GeoRefTerrain/out", "test_qt.kml"))
            self.dir_images.set_value(folder)

        # Launch
        self.launch_button = QtGui.QPushButton('Lancer', self)
        hbox = QtGui.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.launch_button)
        self.vbox.addLayout(hbox)

        self.setLayout(self.vbox)

        self.launch_possible()
        self.connect(self.dir_images.path, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.gpx.path, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.kml.path, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.shp_points.path, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.shp_lines.path, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)

        self.launch_button.clicked.connect(self.launch_button_clicked)

        # Window
        self.resize(600, 300)
        self.center()
        self.setWindowTitle('GeoRefTerrain')
        self.show()

    def launch_possible(self):
        """Enable self.launch_button if all path arguments are valid"""
        # Enable all
        self.kml.setEnabled(True)
        self.shp_points.setEnabled(True)
        self.shp_lines.setEnabled(True)
        self.interpolation.setEnabled(True)
        self.launch_button.setEnabled(True)

        # Disable is input are not valid
        if not self.dir_images.path.isValid:
            self.shp_points.setEnabled(False)
        if not self.gpx.path.isValid:
            self.shp_lines.setEnabled(False)

        if not self.dir_images.path.isValid and not self.gpx.path.isValid:
            self.kml.setEnabled(False)

        if not self.dir_images.path.isValid or not self.gpx.path.isValid:
            self.interpolation.setEnabled(False)

        if (self.dir_images.path.text() != "" and not self.dir_images.path.isValid) or \
           (self.gpx.path.text() != "" and not self.gpx.path.isValid) or \
           (self.kml.path.text() != "" and not self.kml.path.isValid):
            self.launch_button.setEnabled(False)

    def launch_button_clicked(self):
        class args:
            pass
        args.inname_folder = self.dir_images.path.text()
        args.gpx = self.gpx.path.text()

        args.kml = self.kml.path.text()
        args.shp_points = self.shp_points.path.text()
        args.shp_lines = self.shp_lines.path.text()

        args.no_folder = self.no_folder.isChecked()
        args.interpolation = self.interpolation.isChecked()

        args.date_type = DEFAULT_INDEX_METHOD+1
        args.decal_temps = 0.0

        if args.interpolation:
            self.w = InterpolateDialog(args)
            self.w.show()
        else:
            try:
                self.w = ExecutingWindow(args)
                self.w.show()
                logger.info("L'exécution s'est bien terminée")
            except SystemExit as e:
                logger.fatal(e)
                logger.fatal("L'exécution a échoué à cause de l'erreur ci-dessus")


class InterpolateDialog(QtGui.QWidget):
    NCOLS = 3

    def __init__(self, args=None):
        super(InterpolateDialog, self).__init__()
        self.args = args

        self.resize(700, 400)

        images = list_images(args.inname_folder, args.no_folder, args.date_type)
        nrows = len(images)

        layout = QtGui.QVBoxLayout(self)

        self.setWindowTitle("Lecture des images")

        gpx = Gpx(args.gpx)
        self.track_starting_date = gpx.get_starting_time()
        self.start_date = QtGui.QLabel("Date de début de la trace GPS : {}".format(self.track_starting_date))
        # track_ending_date = gpx.get_ending_time()
        # dt = (self.start_date - track_ending_date).total_seconds()
        #self.end_date = QtGui.QLabel("Date de fin de la trace GPS : {} (durée : {} secondes)".format(track_ending_date))
        layout.addWidget(self.start_date)

        hbox = QtGui.QHBoxLayout()
        self.decal_temps_label = QtGui.QLabel("Décalage de la trace GPS (en secondes)")
        self.decal_temps_lineedit = QtGui.QLineEdit()
        self.decal_temps_lineedit.setValidator(QtGui.QDoubleValidator())
        self.decal_temps_lineedit.setText(str(args.decal_temps))
        hbox.addWidget(self.decal_temps_label)
        hbox.addWidget(self.decal_temps_lineedit)
        layout.addLayout(hbox)

        self.method = QtGui.QComboBox()
        for name in Picture.DATE_TYPES:
            self.method.addItem(Picture.DATE_TYPES[name][0])
        self.method.setCurrentIndex(DEFAULT_INDEX_METHOD)

        slot_dates = lambda: self.update_dates(images)
        slot_time = lambda: self.update_time(images)
        self.method.currentIndexChanged.connect(slot_dates)
        self.decal_temps_lineedit.textChanged.connect(slot_time)

        layout.addWidget(self.method)

        self.table = QtGui.QTableWidget(nrows, InterpolateDialog.NCOLS, self)
        self.table.setHorizontalHeaderLabels(['Fichier', 'Date', 'Temps'])

        for row, image in enumerate(images):
            # Column 0
            item = QtGui.QTableWidgetItem(image.path)
            self.table.setItem(row, 0, item)

        # Column 1
        self.update_dates(images)

        # Column 2
        self.update_time(images)

        self.table.resizeColumnsToContents()
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)

        layout.addWidget(self.table)

        self.button_cancel = QtGui.QPushButton('Annuler', self)
        self.launch_button = QtGui.QPushButton('Lancer', self)
        hbox = QtGui.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.button_cancel)
        hbox.addWidget(self.launch_button)
        layout.addLayout(hbox)

        self.connect(self.launch_button, QtCore.SIGNAL('clicked()'), self.open_popup)
        self.connect(self.button_cancel, QtCore.SIGNAL('clicked()'), self.close)

    @QtCore.pyqtSlot(list)
    def update_dates(self, images):
        for row, image in enumerate(images):
            # Column 1
            date = str(image.get_date(Picture.get_date_type(self.method.currentText())))
            item = QtGui.QTableWidgetItem(date)
            self.table.setItem(row, 1, item)

    @QtCore.pyqtSlot(list)
    def update_time(self, images):
        for row, image in enumerate(images):
            # Column 2
            temps = image.point.time_from_date(self.track_starting_date) + float(self.decal_temps_lineedit.text())
            item = QtGui.QTableWidgetItem(str(temps))
            self.table.setItem(row, 2, item)

    def open_popup(self):
        try:
            self.w = ExecutingWindow(self.args)
            self.w.show()
            logger.info("L'exécution s'est bien terminée")
        except SystemExit as e:
            logger.fatal(e)
            logger.fatal("L'exécution a échoué à cause de l'erreur ci-dessus")


def main():

    app = QtGui.QApplication(sys.argv)
    ex = Main()
    sys.exit(app.exec_())


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    main()
