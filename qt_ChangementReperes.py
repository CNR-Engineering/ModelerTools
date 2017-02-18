#!/usr/bin/env python3
"""
TODO:
* fix bug with attribute isValid (on QLineEdit)
"""

from csv import DictReader
import logging
import os.path
from PyQt4 import QtGui, QtCore
import sys

from common.qt_log_in_textbrowser import MyQWidget, ConsoleWindowLogHandler

from ChangementReperes import ReferenceFrameConfig, launch_main


NO_VALUE = "(aucun)"


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
        self.resize(650, 500)
        self.center()
        self.setWindowTitle("Changement de repères")

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


class Main(MyQWidget):
    """
    Fenêtre principale avec le choix des fichiers/options
    """
    # RGB Colors
    RED = "color: rgb(128, 0, 0);"
    GREEN = "color: rgb(0, 128, 0);"

    def __init__(self):
        super(Main, self).__init__()
        self.initUI()

    @staticmethod
    def HLine():
        """Horizontal line"""
        HLine = QtGui.QFrame()
        HLine.setFrameShape(QtGui.QFrame.HLine)
        HLine.setFrameShadow(QtGui.QFrame.Sunken)
        return HLine

    def add_path_hbox(self, label, extension, mode):
        """
        Line with 3 objets: QLabel, QLineEdit, QPushButton
        Only QLineEdit is returned
        """
        path_lbl = QtGui.QLabel(label)
        path_line = QtGui.QLineEdit()
        path_browse = QtGui.QPushButton('Parcourir', self)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(path_lbl)
        hbox.addWidget(path_line)
        hbox.addWidget(path_browse)
        self.vbox.addLayout(hbox)

        def check_path_exists():
            """Switch color of `path_line` whether the path exists"""
            if mode == 'r':
                exists, no_file = (Main.GREEN, Main.RED)
            else:
                exists, no_file = (Main.RED, Main.GREEN)
            path_line.isValid = False
            if os.path.exists(path_line.text()):
                path_line.setStyleSheet(exists)
                if mode == 'r': path_line.isValid = True
            else:
                path_line.setStyleSheet(no_file)
                if mode == 'w': path_line.isValid = True

        self.connect(path_line, QtCore.SIGNAL("textChanged(QString)"), check_path_exists)

        def select_file():
            if mode == 'r':
                getfile = QtGui.QFileDialog.getOpenFileName
            else:
                getfile = QtGui.QFileDialog.getSaveFileName

            if extension == 'shp':
                fname = getfile(self, 'Choisir un fichier shape', path_line.text(), "Fichiers Shape (*.shp)")
            elif extension == 'csv':
                fname = getfile(self, 'Choisir un fichier csv', path_line.text(), "Fichiers csv (*.csv)")
            elif extension == 'xml':
                fname = getfile(self, 'Choisir un fichier xml', path_line.text(), "Fichiers xml (*.xml)")
            elif extension is None:
                # FIXME: save directory if mode=='w'?
                fname = QtGui.QFileDialog.getExistingDirectory(self, 'Sélectionner un dossier', None, QtGui.QFileDialog.ShowDirsOnly)
            else:
                sys.exit("Extension '{}' is unknown".format(extension))
            if fname:
                path_line.setText(fname)

        self.connect(path_browse, QtCore.SIGNAL('clicked()'), select_file)

        return path_line

    def initUI(self):
        # Window parameters
        self.resize(700, 200)
        self.center()
        self.setWindowTitle("Changement de repères")

        self.vbox = QtGui.QVBoxLayout()

        # Path
        self.inname_csv = self.add_path_hbox("Fichier d'entrée", 'csv', 'r')
        self.outname_csv = self.add_path_hbox("Fichier de sortie", 'csv', 'w')
        self.config_xml = self.add_path_hbox("Fichier de configuration", 'xml', 'r')

        # Reference frames
        ## Input
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Repère en entrée")
        hbox.addWidget(lbl)
        self.source = QtGui.QComboBox()
        self.source.setMinimumWidth(200)
        hbox.addWidget(self.source)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        ## Output
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Repère en sortie")
        hbox.addWidget(lbl)
        self.target = QtGui.QComboBox()
        self.target.setMinimumWidth(200)
        hbox.addWidget(self.target)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        # separator
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Séparateur de colonnes")
        hbox.addWidget(lbl)
        self.sep = QtGui.QLineEdit()
        self.sep.setFixedWidth(40)
        hbox.addWidget(self.sep)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        # digits
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Nombre de chiffres après la virgule")
        hbox.addWidget(lbl)
        self.digits = QtGui.QLineEdit()
        self.digits.setFixedWidth(40)
        hbox.addWidget(self.digits)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        # Set default values
        self.digits.setText("4")
        self.sep.setText(';')

        # Fieldnames
        ## x
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Colonne coord. selon X")
        hbox.addWidget(lbl)
        self.x = QtGui.QComboBox()
        self.x.setMinimumWidth(200)
        hbox.addWidget(self.x)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        ## y
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Colonne coord. selon Y")
        hbox.addWidget(lbl)
        self.y = QtGui.QComboBox()
        self.y.setMinimumWidth(200)
        hbox.addWidget(self.y)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        ## z
        hbox = QtGui.QHBoxLayout()
        lbl = QtGui.QLabel("Colonne coord. selon Z")
        hbox.addWidget(lbl)
        self.z = QtGui.QComboBox()
        self.z.setMinimumWidth(200)
        hbox.addWidget(self.z)
        hbox.addStretch(1)
        self.vbox.addLayout(hbox)

        self.connect(self.inname_csv, QtCore.SIGNAL("textChanged(QString)"), self.find_fieldnames)
        self.connect(self.config_xml, QtCore.SIGNAL("textChanged(QString)"), self.find_reference_frames)

        # if True:  #DEBUG
        #     self.inname_csv.setText("T:/_OUTILS/scripts/validation/ModelerTools/ChangementReperes/pts_covadis_P.csv")
        #     self.outname_csv.setText("T:/_OUTILS/scripts/validation/ModelerTools/ChangementReperes/out/pts_calcules_T.csv")
        #     self.config_xml.setText("T:/_OUTILS/scripts/validation/ModelerTools/ChangementReperes/Ref_Loire.xml")

        # LAUNCH
        self.launch_button = QtGui.QPushButton('Lancer', self)
        hbox = QtGui.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.launch_button)
        self.vbox.addLayout(hbox)

        # Enable or not launch button
        self.launch_button.setEnabled(False)
        self.connect(self.inname_csv, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.outname_csv, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)
        self.connect(self.config_xml, QtCore.SIGNAL("textChanged(QString)"), self.launch_possible)

        self.connect(self.launch_button, QtCore.SIGNAL('clicked()'), self.open_popup)

        self.setLayout(self.vbox)
        self.show()

    def launch_possible(self):
        """Enable self.launch_button if all path arguments are valid"""
        if self.inname_csv.isValid and self.outname_csv.isValid and self.config_xml.isValid:
            self.launch_button.setEnabled(True)
        else:
            self.launch_button.setEnabled(False)

    def find_fieldnames(self):
        """Find fieldnames in CSV and fill in x and y QComboBox"""
        self.x.clear()
        self.y.clear()
        self.z.clear()
        self.z.addItem(NO_VALUE)

        if self.inname_csv.isValid:
            with open(self.inname_csv.text(), 'r') as filein:
                reader = DictReader(filein, delimiter=';')
                for col in reader.fieldnames:
                    self.x.addItem(col)
                    self.y.addItem(col)
                    self.z.addItem(col)

                try:
                    # Set default values if it exists
                    self.x.setCurrentIndex(reader.fieldnames.index('x'))
                except ValueError:
                    pass

                try:
                    # Set default values if it exists
                    self.y.setCurrentIndex(reader.fieldnames.index('y'))
                except ValueError:
                    pass

    def find_reference_frames(self):
        self.ref_frame_config = ReferenceFrameConfig(self.config_xml.text(), logger)

        # Source
        self.source.clear()
        for abbr, label in self.ref_frame_config.reference_frames_dict.items():
            self.source.addItem(label)
        self.source.setCurrentIndex(0)

        # Target
        self.target.clear()
        for abbr, label in self.ref_frame_config.reference_frames_dict.items():
            self.target.addItem(label)
        self.target.setCurrentIndex(len(self.ref_frame_config.reference_frames_dict)-1)

    def get_abbr_from_text(self, text):
        for abbr, label in self.ref_frame_config.reference_frames_dict.items():
            if text==label:
                return abbr
        sys.exit("Aucun référentiel '{}' trouvé".format(text))


    def open_popup(self):
        class args:
            pass
        args.inname_csv = self.inname_csv.text()
        args.outname_csv = self.outname_csv.text()
        args.config_xml = self.config_xml.text()
        args.source = self.get_abbr_from_text(self.source.currentText())
        args.target = self.get_abbr_from_text(self.target.currentText())
        args.sep = ';'
        args.x = self.x.currentText()
        args.y = self.y.currentText()
        if self.z.currentText() != NO_VALUE:
            args.z = self.z.currentText()
        else:
            args.z = None
        args.digits = 4
        args.verbose = True
        args.force = False

        try:
            self.w = ExecutingWindow(args)
            self.w.show()
        except SystemExit as e:
            logger.fatal(e)
            logger.fatal("L'exécution a échoué à cause de l'erreur ci-dessus")


def main():
    app = QtGui.QApplication(sys.argv)
    Main()
    sys.exit(app.exec_())


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    main()
