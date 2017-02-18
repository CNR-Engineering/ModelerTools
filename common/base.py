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


class QtHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        record = self.format(record)
        if record: XStream.stdout().write("{}\n".format(record))


class XStream(QtCore.QObject):
    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)
    def flush(self):
        pass
    def fileno(self):
        return -1
    def write(self, msg):
        if (not self.signalsBlocked()):
            #LDN#self.messageWritten.emit(unicode(msg))  # Py2
            self.messageWritten.emit(msg)  # Py3
    @staticmethod
    def stdout():
        if (not XStream._stdout):
            XStream._stdout = XStream()
            sys.stdout = XStream._stdout
        return XStream._stdout
    @staticmethod
    def stderr():
        if (not XStream._stderr):
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr
        return XStream._stderr
