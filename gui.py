import os
from threading import Thread

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QPoint, QRect
from PyQt5.QtGui import QIcon, QPixmap, QFont, QIntValidator
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QGridLayout, QLabel, QGroupBox, QWidget, \
    QCompleter, QLineEdit, QFrame, QListWidget, QTableWidget, QTableWidgetItem, QFileDialog, \
    QItemDelegate, QAbstractItemView, QStackedWidget, QHBoxLayout, QTabBar, QTabWidget, QStylePainter, QStyleOptionTab,\
    QStyle, QProxyStyle, QSizePolicy
from requests import get

from gear import *
from optimizer import E7GearOptimizer
import re

QLAYER_STYLESHEET = 'resources/style/qlayer.qss'


class TabBar(QTabBar):
    def tabSizeHint(self, index):
        s = QTabBar.tabSizeHint(self, index)
        s.transpose()
        return s

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionTab()
        opt.initFrom(self)

        for i in range(self.count()):
            self.initStyleOption(opt, i)
            painter.drawControl(QStyle.CE_TabBarTabShape, opt)
            painter.save()

            s = opt.rect.size()
            s.transpose()
            r = QRect(QPoint(), s)
            r.moveCenter(opt.rect.center())
            opt.rect = r

            c = self.tabRect(i).center()
            painter.translate(c)
            painter.rotate(90)
            painter.translate(-c)
            painter.drawControl(QStyle.CE_TabBarTabLabel, opt)
            painter.restore()


class TabWidget(QTabWidget):
    def __init__(self, *args, **kwargs):
        QTabWidget.__init__(self, *args, **kwargs)
        self.setTabBar(TabBar(self))
        self.setTabPosition(QTabWidget.West)


class ProxyStyle(QProxyStyle):
    def drawControl(self, element, opt, painter, widget):
        if element == QStyle.CE_TabBarTabLabel:
            ic = self.pixelMetric(QStyle.PM_TabBarIconSize)
            r = QRect(opt.rect)
            w = 0 if opt.icon.isNull() else opt.rect.width() + self.pixelMetric(QStyle.PM_TabBarIconSize)
            r.setHeight(opt.fontMetrics.width(opt.text) + w)
            r.moveBottom(opt.rect.bottom())
            opt.rect = r
        QProxyStyle.drawControl(self, element, opt, painter, widget)


class QLayer(QWidget):
    def __init__(self, p_str, content, layer=1, parent=None):
        super().__init__(parent)
        self.setObjectName('layer{}'.format(layer))
        self.setStyleSheet('background-color: #FF0000;')

        self.frame = QFrame()
        self.frame.setObjectName('qlayer_frame')

        self.title = QLabel()
        self.title.setText(p_str)
        self.title.setObjectName('qlayer_title')

        self.content_layout = QVBoxLayout(self.frame)
        self.content_layout.addWidget(content)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.frame)
        self.setLayout(self.layout)

        # set stylesheet
        with open(QLAYER_STYLESHEET) as stylesheet:
            self.setStyleSheet(stylesheet.read())

    def setWindowTitle(self, p_str):
        self.title.setText(p_str)


class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class QVLine(QFrame):
    def __init__(self):
        super(QVLine, self).__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)


class CenterAlignDelegate(QItemDelegate):
    def paint(self, painter, option, index):
        option.displayAlignment = Qt.AlignCenter
        QItemDelegate.paint(self, painter, option, index)


class OptimizerWidget(QObject, E7GearOptimizer):
    optimizer_done_signal = pyqtSignal()
    gear_added_signal = pyqtSignal()

    def __init__(self):
        QObject.__init__(self, None)
        E7GearOptimizer.__init__(self)

    def import_gear(self, image_paths):
        super(OptimizerWidget, self).import_gear(image_paths)
        self.gear_added_signal.emit(self.gears)

    def optimize(self, priorities, required_sets, min_max_constraints):
        super(OptimizerWidget, self).optimize(priorities, required_sets, min_max_constraints)
        self.optimizer_done_signal.emit()


class GUI(QWidget):
    optimizer_done_signal = pyqtSignal()
    gear_added_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.optimizer = E7GearOptimizer()

        self.side_bar = TabWidget()

        self.tab_optimizer = QWidget()
        self.tab_loadouts = QWidget()
        self.tab_gears = QWidget()

        self._init_ui()

        # Load gears
        self.optimizer.load()
        self.gear_added_signal.emit(self.optimizer.gears)

    def _init_ui(self):
        self._init_optimizer_tab()
        self._init_gears_tab()

        self.side_bar.setObjectName('tabs')
        self.side_bar.addTab(self.tab_optimizer, QIcon(':/close.png'), 'Optimizer')
        # self.side_bar.addTab(QWidget(self.side_bar), QIcon(':/close.png'), 'Loadouts')
        self.side_bar.addTab(self.tab_gears, QIcon(':/close.png'), 'Gears')
        # self.side_bar.addTab(QWidget(self.side_bar), QIcon(':/close.png'), 'Settings')

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.side_bar)

        self.setLayout(layout)

        self.update_hero_stats(None)

    def _init_optimizer_tab(self):
        group_hero = QGroupBox('Hero')
        group_loadout = QGroupBox('Loadout')

        # Hero
        hero_name = QLineEdit()
        hero_name.setObjectName('hero_name')
        autocomplete = QCompleter(self.optimizer.get_hero_list())
        autocomplete.setCaseSensitivity(Qt.CaseInsensitive)
        hero_name.setCompleter(autocomplete)

        # Hero portrait
        hero_image = QLabel()
        hero_image.setMinimumHeight(120)
        hero_image.setAlignment(Qt.AlignCenter)

        def load_hero(hero):
            pattern = re.compile('[\W_ ]+')
            hero = pattern.sub(' ', hero)
            data = get('https://assets.epicsevendb.com/hero/{}/icon.png'.format('-'.join(hero.lower().split()))).content
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            hero_image.setPixmap(pixmap)

        autocomplete.activated.connect(load_hero)

        # Hero stats
        font = QFont('Courier', 10)
        hero_stats = QLabel()
        hero_stats.setObjectName('hero_stats')
        hero_stats.setFont(font)
        autocomplete.activated.connect(self.get_stats)

        # Save loadout
        btn_save_loadout = QPushButton('Save Loadout')
        btn_save_loadout.clicked.connect(self.save_loadout)

        # Delete loadout
        btn_delete_loadout = QPushButton('Delete Loadout')
        btn_delete_loadout.clicked.connect(self.delete_loadout)

        layout_hero = QGridLayout()
        layout_hero.setAlignment(Qt.AlignCenter)
        layout_hero.addWidget(hero_name, 0, 0, 1, 2)
        layout_hero.addWidget(QHLine(), 1, 0, 1, 2)
        layout_hero.addWidget(hero_image, 2, 0, 1, 2)
        layout_hero.addWidget(QHLine(), 3, 0, 1, 2)
        layout_hero.addWidget(hero_stats, 4, 0, 1, 2)
        layout_hero.addWidget(QHLine(), 5, 0, 1, 2)
        layout_hero.addWidget(btn_save_loadout, 6, 0, 1, 1)
        layout_hero.addWidget(btn_delete_loadout, 6, 1, 1, 1)
        group_hero.setLayout(layout_hero)

        # Display loadout
        layout_loadout = QGridLayout()

        for i, gear_type in enumerate([gear_type.name for gear_type in GearType]):
            gear_label = QLabel(gear_type)
            gear_label.setObjectName(gear_type)
            type_img = QLabel()
            type_pixmap = QPixmap()
            type_pixmap.load('resources/type_images/{}.png'.format(gear_type))
            type_img.setPixmap(type_pixmap)

            set_img = QLabel()
            set_img.setObjectName('{}_set_img'.format(gear_type))
            set_img.setAlignment(Qt.AlignCenter)

            layout_loadout.addWidget(type_img, (i % 3) * 2, int(i / 3) * 3, 1, 1)
            layout_loadout.addWidget(set_img, (i % 3) * 2 + 1, int(i / 3) * 3, 1, 1)
            layout_loadout.addWidget(gear_label, (i % 3) * 2, int(i / 3) * 3 + 1, 2, 1)

        group_loadout.setMinimumWidth(450)
        group_loadout.setLayout(layout_loadout)

        # Wrap all into 1 layer group
        widget_hero = QWidget()
        layout_hero_layer = QHBoxLayout()
        layout_hero_layer.addWidget(group_hero)
        layout_hero_layer.addWidget(QVLine())
        layout_hero_layer.addWidget(group_loadout)
        widget_hero.setMinimumHeight(450)
        widget_hero.setLayout(layout_hero_layer)

        # Min-Max Constraints
        # Stat priority
        group_priorities = QGroupBox('Priorities')
        layout_priorities = QGridLayout()

        label_stats = QLabel('Stats')
        label_prioritize = QLabel('Prioritize')

        priorities_list = QListWidget()
        priorities_list.addItems([stat.name for stat in GearStat])
        priorities_list.setDragEnabled(QAbstractItemView.DragDrop)
        priorities_list.setAcceptDrops(True)
        priorities_list.setDefaultDropAction(Qt.MoveAction)

        priorities_selected = QListWidget()
        priorities_selected.setDragDropMode(QAbstractItemView.DragDrop)
        priorities_selected.setAcceptDrops(True)
        priorities_selected.setDefaultDropAction(Qt.MoveAction)

        layout_priorities.addWidget(label_stats, 0, 0, 1, 1)
        layout_priorities.addWidget(label_prioritize, 0, 1, 1, 1)
        layout_priorities.addWidget(priorities_list, 1, 0, 1, 1)
        layout_priorities.addWidget(priorities_selected, 1, 1, 1, 1)
        group_priorities.setLayout(layout_priorities)

        # Equipment required set button selections
        group_set = QGroupBox('Set')
        layout_set_buttons = QGridLayout()

        for i, eq_set in enumerate([sets.name for sets in GearSet]):
            btn = QPushButton()
            pixmap = QPixmap('resources/set_images/{}.png'.format(eq_set.lower()))
            btn.setIcon(QIcon(pixmap))
            btn.setFixedSize(pixmap.rect().size())
            btn.setCheckable(True)
            btn.setObjectName(eq_set)
            layout_set_buttons.addWidget(btn, i / 7, i % 7, 1, 1)
        group_set.setLayout(layout_set_buttons)

        # Stat min-max constraints
        group_min_max = QGroupBox('Min-Max')
        layout_min_max = QGridLayout()
        layout_min_max.addWidget(QLabel('Min'), 0, 1, 1, 1)
        layout_min_max.addWidget(QLabel('Max'), 0, 2, 1, 1)
        for i, stat in enumerate([stat.name for stat in GearStat]):
            label = QLabel('{:12}'.format(stat))
            label.setFont(QFont('Courier'))
            min = QLineEdit()
            max = QLineEdit()
            min.setValidator(QIntValidator())
            max.setValidator(QIntValidator())
            layout_min_max.addWidget(label, i + 1, 0, 1, 1)
            layout_min_max.addWidget(min, i + 1, 1, 1, 1)
            layout_min_max.addWidget(max, i + 1, 2, 1, 1)
        group_min_max.setLayout(layout_min_max)

        # Optimize button
        btn_optimize = QPushButton('Optimize')

        def start_optimizer():
            priorities = []
            for x in range(priorities_selected.count()):
                priorities.append(GearStat[priorities_selected.item(x).text()].value)

            required_set = []
            for x in range(layout_set_buttons.count()):
                set_btn = layout_set_buttons.itemAt(x).widget()
                if set_btn.isChecked():
                    required_set.append(GearSet[set_btn.objectName()].value)

            min_max = {}
            for x in range(2, layout_min_max.count(), 3):
                stat = layout_min_max.itemAt(x).widget().text().strip()
                min_stat = layout_min_max.itemAt(x + 1).widget().text()
                max_stat = layout_min_max.itemAt(x + 2).widget().text()
                min_max[stat] = (int(min_stat) if min_stat else 0, int(max_stat) if max_stat else 100000)

            thread = Thread(target=self.optimize, args=(priorities, required_set, min_max,))
            thread.daemon = True
            thread.start()

        btn_optimize.clicked.connect(start_optimizer)

        widget_constraints = QWidget()
        layout_constraints = QGridLayout()
        layout_constraints.addWidget(group_priorities, 0, 0, 2, 1)
        layout_constraints.addWidget(group_min_max, 0, 1, 3, 1)
        layout_constraints.addWidget(group_set, 2, 0, 2, 1)
        layout_constraints.addWidget(btn_optimize, 3, 1, 1, 1)
        widget_constraints.setLayout(layout_constraints)

        # Optimizer results table
        table = QTableWidget()
        table.setObjectName('results_table')
        table.setItemDelegate(CenterAlignDelegate())
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([stat.name for stat in GearStat])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setMinimumWidth(900)

        def populate_result_table():
            table.setRowCount(0)
            row_count = 0
            for final_stat, combo in self.optimizer.optimizer_output:
                table.insertRow(row_count)
                for i, stat in enumerate([stat.name for stat in GearStat]):
                    table.setItem(row_count, i, QTableWidgetItem(str(final_stat[stat])))
                row_count += 1

        self.optimizer_done_signal.connect(populate_result_table)

        def sort_results_header_click(col_index):
            self.optimizer.optimizer_output.sort(key=lambda a: a[0][GearStat(col_index).name], reverse=True)
            populate_result_table()

        table.horizontalHeader().sectionClicked.connect(sort_results_header_click)

        def update_hero_stat_from_selection(item):
            row = item.row()
            stats = self.optimizer.optimizer_output[row][0]
            self.update_hero_stats(stats)

            loadout = self.optimizer.optimizer_output[row][1]
            for i, gear in enumerate(loadout):
                gear_type_ui_text = widget_hero.findChild(QLabel, GearType(i).name)
                gear_type_ui_text.setFont(QFont('Courier'))
                gear_type_ui_text.setText(str(gear))

                gear_set_img = widget_hero.findChild(QLabel, '{}_set_img'.format(GearType(i).name))
                set_img = QPixmap('resources/set_images/{}.png'.format(GearSet(gear.set).name))
                gear_set_img.setPixmap(set_img)

        table.itemClicked.connect(update_hero_stat_from_selection)

        """layout_results = QVBoxLayout()
        layout_results.addWidget(table)
        qlayer_results.setLayout(layout_results)"""

        # Put everything together
        qlayer_hero = QLayer('Hero', widget_hero)
        qlayer_constraints = QLayer('Constraints', widget_constraints)
        qlayer_results = QLayer('Results', table)

        layout_tab = QGridLayout()
        layout_tab.addWidget(qlayer_hero, 0, 0)
        layout_tab.addWidget(qlayer_constraints, 1, 0)
        layout_tab.addWidget(qlayer_results, 0, 1, 2, 1)
        self.tab_optimizer.setLayout(layout_tab)

    def _init_gears_tab(self):
        # Import options
        btn_import_images = QPushButton('Import Images')

        def import_gear_image():
            file_dialog = QFileDialog()
            files = file_dialog.getOpenFileNames()
            if files[0]:
                self.import_gear(files[0])

        btn_import_images.clicked.connect(import_gear_image)

        # Gears
        gear_table = QTableWidget()
        gear_table.setColumnCount(7)
        gear_table.setHorizontalHeaderLabels(['Type', 'Set', 'Main Stat', 'Substat 1', 'Substat 2', 'Substat 3',
                                              'Substat 4'])
        gear_table.setItemDelegate(CenterAlignDelegate())
        gear_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        def add_gear_to_table(gears):
            gear_table.setRowCount(0)
            row_count = 0
            for gear in gears:
                gear_table.insertRow(row_count)
                gear_table.setItem(row_count, 0, QTableWidgetItem(GearType(gear.type).name))
                gear_table.setItem(row_count, 1, QTableWidgetItem(GearSet(gear.set).name))
                gear_table.setItem(row_count, 2, QTableWidgetItem(str(gear.main_stat)))
                gear_table.setItem(row_count, 3, QTableWidgetItem(str(gear.substats[0])))
                gear_table.setItem(row_count, 4, QTableWidgetItem(str(gear.substats[1])))
                gear_table.setItem(row_count, 5, QTableWidgetItem(str(gear.substats[2])))
                gear_table.setItem(row_count, 6, QTableWidgetItem(str(gear.substats[3])))
                row_count += 1

        self.gear_added_signal.connect(add_gear_to_table)

        # Putting all together
        qlayer_import = QLayer('Import', btn_import_images)
        qlayer_gears = QLayer('Equipment', gear_table)

        layout_tab = QGridLayout()
        layout_tab.addWidget(qlayer_import)
        layout_tab.addWidget(qlayer_gears)
        self.tab_gears.setLayout(layout_tab)

    def closeEvent(self, event):
        self.optimizer.save()

    def update_hero_stats(self, final_stats):
        hero_stats = self.tab_optimizer.findChild(QLabel, 'hero_stats')
        if final_stats is None:
            hero_stats.setText(
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%'.format('Attack', 0,
                                         'Defense', 0,
                                         'Health', 0,
                                         'Speed', 0,
                                         'Critical Hit Chance', 0,
                                         'Critical Hit Damage', 0,
                                         'Effectiveness', 0,
                                         'Effect Resistance', 0))
        else:
            hero_stats.setText(
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20} {:>6}\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%\n'
                '{:<20}{:>6.1f}%'.format('Attack', final_stats['Attack'],
                                         'Defense', final_stats['Defense'],
                                         'Health', final_stats['Health'],
                                         'Speed', final_stats['Speed'],
                                         'Critical Hit Chance', final_stats['Crit. C'],
                                         'Critical Hit Damage', final_stats['Crit. D'],
                                         'Effectiveness', final_stats['Eff'],
                                         'Effect Resistance', final_stats['Eff. Resist']))

    def get_stats(self, hero):
        hero = hero.strip()
        self.optimizer.hero_base_stat = self.optimizer.get_hero_stats(hero)
        if hero in self.optimizer.hero_loadouts:
            gear_ids = self.optimizer.hero_loadouts[hero.strip()]
            loadout = Loadout([self.optimizer.get_gear(gear_id) for gear_id in gear_ids])
            loadout.post_init()

            # Calculate total stats given from loadout
            total_stats = loadout.stats_given

            # Calculate hero's final stats
            stats = {}
            for stat, multipliers in total_stats.items():
                stats[stat] = int(self.optimizer.hero_base_stat[stat] * (1 + multipliers[0] / 100) + multipliers[1])

            for i, gear in enumerate(loadout):
                gear_type_ui_text = self.tab_optimizer.findChild(QLabel, GearType(i).name)
                gear_type_ui_text.setFont(QFont('Courier'))
                gear_type_ui_text.setText(str(gear))

                gear_set_img = self.tab_optimizer.findChild(QLabel, '{}_set_img'.format(GearType(i).name))
                set_img = QPixmap('resources/set_images/{}.png'.format(GearSet(gear.set).name))
                gear_set_img.setPixmap(set_img)
        else:
            #00-1-773-0101098
            stats = self.optimizer.hero_base_stat
        self.update_hero_stats(stats)

    def get_hero_name(self):
        return self.tab_optimizer.findChild(QLineEdit, 'hero_name').text()

    def save_loadout(self):
        results_table = self.tab_optimizer.findChild(QTableWidget, 'results_table')
        rows_selected = set(index.row() for index in results_table.selectedIndexes())
        if len(rows_selected) == 1:
            loadout = self.optimizer.optimizer_output[rows_selected.pop()][1]
            save_loadout = []
            for gear in loadout:
                self.optimizer.set_gear_usage(gear.id, True)
                save_loadout.append(gear.id)

            self.optimizer.hero_loadouts[self.get_hero_name().strip()] = save_loadout
            self.optimizer.save()
            print('Saved loadout for', self.get_hero_name())

    def delete_loadout(self):
        gear_loadout = self.optimizer.hero_loadouts.pop(self.get_hero_name().strip(), None)
        if gear_loadout is None:
            return

        for gear_id in gear_loadout:
            self.optimizer.set_gear_usage(gear_id, False)

        self.optimizer.save()
        print('Deleted loadout for', self.get_hero_name())

    def import_gear(self, image_paths):
        self.optimizer.import_gear(image_paths)
        self.gear_added_signal.emit(self.optimizer.gears)

    def optimize(self, priorities, required_sets, min_max_constraints):
        self.optimizer.optimize(priorities, required_sets, min_max_constraints)
        self.optimizer_done_signal.emit()
