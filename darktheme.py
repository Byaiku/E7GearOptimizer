import sys

from PyQt5.QtCore import QMetaObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from resources.style import resources

STYLESHEET = 'resources/style/style.qss'
DARK_WINDOW_STYLESHEET = 'resources/style/stylesheet.css'


class TitleBar(QWidget):
    double_clicked = pyqtSignal()

    def __init__(self, window, parent=None):
        QWidget.__init__(self, parent)

        self.__window = window
        self.__window_pos = None

        self.__mouse_pos = None
        self.__mouse_clicked = False

    def mousePressEvent(self, event):
        self.__mouse_clicked = True
        self.__mouse_pos = event.globalPos()
        self.__window_pos = self.__window.pos()

    def mouseMoveEvent(self, event):
        if self.__mouse_clicked:
            self.__window.move(self.__window_pos + (event.globalPos() - self.__mouse_pos))

    def mouseReleaseEvent(self, event):
        self.__mouse_clicked = False

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()


class DarkWindow(QWidget):
    def __init__(self, application, window_content, parent=None):
        QWidget.__init__(self, parent)

        self.content = window_content

        self.setup_ui()
        self.setup_palette(application)
        self.setup_events()

    def setup_ui(self):
        self.dark_layout = QVBoxLayout(self)
        self.dark_layout.setContentsMargins(0, 0, 0, 0)

        self.window_frame = QWidget(self)
        self.window_frame.setObjectName('window_frame')

        self.window_layout = QVBoxLayout(self.window_frame)
        self.window_layout.setContentsMargins(0, 0, 0, 0)

        self.title_bar = TitleBar(self, self.window_frame)
        self.title_bar.setObjectName('title_bar')
        self.title_bar.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed))

        self.window_title = QLabel()
        self.window_title.setObjectName('window_title')
        self.window_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_minimize = QToolButton()
        self.btn_minimize.setObjectName('btn_minimize')
        self.btn_minimize.setIcon(QIcon(':/minimize.png'))
        self.btn_minimize.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.btn_restore = QToolButton()
        self.btn_restore.setObjectName('btn_restore')
        self.btn_restore.setIcon(QIcon(':/restore.png'))
        self.btn_restore.setVisible(False)
        self.btn_restore.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.btn_maximize = QToolButton()
        self.btn_maximize.setObjectName('btn_maximize')
        self.btn_maximize.setIcon(QIcon(':/maximize.png'))
        self.btn_maximize.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.btn_close = QToolButton()
        self.btn_close.setObjectName('btn_close')
        self.btn_close.setIcon(QIcon(':/close.png'))
        self.btn_close.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_layout.setSpacing(0)
        self.title_bar_layout.addWidget(self.window_title)
        self.title_bar_layout.addWidget(self.btn_minimize)
        self.title_bar_layout.addWidget(self.btn_maximize)
        self.title_bar_layout.addWidget(self.btn_restore)
        self.title_bar_layout.addWidget(self.btn_close)

        self.window_layout.addWidget(self.title_bar)
        self.window_content = QWidget(self.window_frame)
        self.window_content.setObjectName('window_content')
        self.window_layout.addWidget(self.window_content)

        self.dark_layout.addWidget(self.window_frame)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.content)
        self.window_content.setLayout(content_layout)

        self.setWindowTitle(self.content.windowTitle())
        self.setGeometry(self.content.geometry())

        # set window flags
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # set stylesheet
        with open(DARK_WINDOW_STYLESHEET) as stylesheet:
            self.setStyleSheet(stylesheet.read())

        # connect slots
        QMetaObject.connectSlotsByName(self)

    def setup_palette(self, app):
        app.setStyle('Fusion')
        with open(STYLESHEET) as stylesheet:
            self.setStyleSheet(stylesheet.read())

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)

        # disabled
        palette.setColor(QPalette.Disabled, QPalette.WindowText,
                         QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.Text,
                         QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText,
                         QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.Highlight,
                         QColor(80, 80, 80))
        palette.setColor(QPalette.Disabled, QPalette.HighlightedText,
                         QColor(127, 127, 127))

        app.setPalette(palette)

    def setup_events(self):
        self.content.close = self.close
        self.closeEvent = self.content.closeEvent

    def setWindowTitle(self, p_str):
        self.window_title.setText(p_str)

    @pyqtSlot()
    def on_btn_minimize_clicked(self):
        self.setWindowState(Qt.WindowMinimized)

    @pyqtSlot()
    def on_btn_restore_clicked(self):
        self.btn_restore.setVisible(False)
        self.btn_maximize.setVisible(True)

        self.setWindowState(Qt.WindowNoState)

    @pyqtSlot()
    def on_btn_maximize_clicked(self):
        self.btn_restore.setVisible(True)
        self.btn_maximize.setVisible(False)

        self.setWindowState(Qt.WindowMaximized)

    @pyqtSlot()
    def on_btn_close_clicked(self):
        self.close()

    @pyqtSlot()
    def on_title_bar_doubleClicked(self):
        if self.btn_maximize.isVisible():
            self.on_btn_maximize_clicked()
        else:
            self.on_btn_restore_clicked()


if __name__ == '__main__':
    app = QApplication([])
    test = QWidget()

    gui = DarkWindow(app, test)
    gui.setWindowTitle('E7 Gear Optimizer')
    gui.show()

    sys.exit(app.exec_())
