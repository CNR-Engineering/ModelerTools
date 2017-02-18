"""
Handle logging in a Message Box?
"""
from PyQt4 import QtGui, QtCore
import logging
import sys


class MyQWidget(QtGui.QWidget):

    def center(self):
        frameGm = self.frameGeometry()
        screen = QtGui.QApplication.desktop().screenNumber(QtGui.QApplication.desktop().cursor().pos())
        centerPoint = QtGui.QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())


class ConsoleWindowLogHandler(logging.Handler):
    def __init__(self, sigEmitter):
        super(ConsoleWindowLogHandler, self).__init__()
        self.sigEmitter = sigEmitter

    def emit(self, logRecord):
        message = str(logRecord.getMessage())
        self.sigEmitter.emit(QtCore.SIGNAL("logMsg(QString)"), message)
