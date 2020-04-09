import sys
from PyQt5.Qt import QApplication

from gui import GUI
from darktheme import DarkWindow

import multiprocessing as mp


def main():
    app = QApplication([])
    gui = GUI()
    gui = DarkWindow(app, gui)
    gui.setWindowTitle('E7 Gear Optimizer')
    gui.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    mp.freeze_support()
    main()
