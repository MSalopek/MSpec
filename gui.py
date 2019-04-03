import json
import logging
from os import path
from pprint import pformat
import traceback

from PyQt5 import Qt, QtGui, QtCore
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMenu, QMenuBar, QPushButton, QSpinBox,
                             QTextEdit, QVBoxLayout)
import pyqtgraph as pg
import numpy as np

from . import ms_utils
from .worker import worker

# app = QtGui.QApplication([])

# make table clickable
# add toolbar to app
# add menubar to app


class ScanWindow(QtGui.QMainWindow):
    """ScanWindow opens on click"""

    def __init__(self, peak_num, mz_arr, int_arr, ret_time, logger, db):
        super().__init__()
        self.title = "Scan @" + str(ret_time)
        self.selectedPeaks = []
        self.clicked = 0
        self.xDataPos1 = 0
        self.xDataPos2 = 0
        self.ctrlClicked = 0
        self.ctrlXPos1 = 0
        self.ctrlXPos2 = 0
        self.textItems = []  # keeps textitems refs
        self.lastRMBtnClick = 0
        self.mz_arr = mz_arr
        self.int_arr = int_arr
        self.ret_time = ret_time
        self.peak_num = peak_num
        self.int_max = max(int_arr)
        self.mz_max = int(mz_arr[-1])
        self.logger = logger
        self.db = db
        self.top = 100
        self.left = 100
        self.width = 900
        self.height = 500
        self.initScanUI()
        self.initScanWindow()

    def initScanWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.top, self.left, self.width, self.height)
        self.show()

    def initScanUI(self):
        self.widget = QtGui.QWidget()
        self.table = QtGui.QTableWidget(0, 2)
        self.header_labels = ["mz", "Charge"]
        self.table.setHorizontalHeaderLabels(self.header_labels)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(20)

        # Create graph window
        self.graph = pg.GraphicsWindow()
        self.graph.setBackground('w')
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.label = pg.LabelItem(justify='center')
        self.graph.addItem(self.label)
        self.ScanPlot = self.graph.addPlot(row=1, col=0)
        self.ScanPlot.setMouseEnabled(x=False, y=False)

        self.ScanPlot.setLabel('left', "Intensity")
        self.ScanPlot.setMenuEnabled(
            False)  # disables default Right mouse btn menu
        self.ScanPlotRelAxis = pg.ViewBox()
        self.ScanPlot.showAxis('right')
        self.ScanPlot.scene().addItem(self.ScanPlotRelAxis)
        self.ScanPlot.getAxis('right').linkToView(self.ScanPlotRelAxis)
        self.ScanPlotRelAxis.setXLink(self.ScanPlot)
        self.ScanPlot.hideButtons()
        self.vLines = []
        self._addVLines()

        # Add widgets to the layout in chosen proper positions
        layout = QtGui.QGridLayout()
        self.widget.setLayout(layout)

        layout.addWidget(
            self.table,
            0,
            0,
        )  # table widget goes left
        layout.addWidget(self.graph, 0, 1)  # plot goes on right side

        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 3)

        # Add widget to main win
        self.setCentralWidget(self.widget)

        # plot the scan as stem
        self.logger.debug(f"Opening Scan at {self.ret_time}.")
        self.ScanPlot.plot(
            np.repeat(self.mz_arr, 2),
            np.dstack((np.zeros(self.int_arr.shape[0], dtype=int),
                       self.int_arr)).flatten(),
            pen=pg.mkPen('r', width=1.2),
            connect='pairs',
            name=f"Spectrum: {self.ret_time}")
        self.ScanPlot.setYRange(
            0, self.int_max + self.int_max * 0.1, padding=0)
        self.ScanPlot.setXRange(0, self.mz_max + 100, padding=0)
        self.ScanPlot.setLimits(xMin=75, xMax=self.mz_max + 100)
        self.annotateViewWithText()
        self.proxy = pg.SignalProxy(
            self.ScanPlot.scene().sigMouseClicked, slot=self.mouseClicked)

    def _addPeakToPeaklist(self, mass, charge):
        mass = round(float(mass), 4)
        charge = int(charge)
        self.selectedPeaks.append((self.peak_num, mass, charge))
        self.logger.debug(
            f"Added {mass}, {charge} results for peak: {self.peak_num}")

    def _clearVLines(self):
        try:
            for i in self.vLines:
                self.ScanPlot.removeItem(i)
            self.vLines = []
        except Exception:
            self.logger.error(
                f"Failed clearing vLines:\n{traceback.format_exc()}")

    def _addVLines(self):
        self.vLines.append(pg.InfiniteLine(angle=90, movable=False))
        self.vLines.append(pg.InfiniteLine(angle=90, movable=False))
        self.ScanPlot.addItem(self.vLines[0], ignoreBounds=False)
        self.ScanPlot.addItem(self.vLines[1], ignoreBounds=False)

    def changeXRange(self, start, end):
        self._clearTextItems()
        self._clearVLines()
        self.ScanPlot.setXRange(start, end)
        self._addVLines()
        self.annotateViewWithText()

    def _handleCtrlClick(self, position):
        if self.ctrlClicked == 0:
            self.ctrlXPos1 = ms_utils.get_closest_point(
                position.x(), list(self.mz_arr))
            self.ctrlClicked = 1
        else:
            self.ctrlXPos2 = ms_utils.get_closest_point(
                position.x(), list(self.mz_arr))
            self.ctrlClicked = 0
        if self.ctrlXPos1 and self.ctrlXPos2:
            if self.ctrlXPos2 < self.ctrlXPos1:
                self.logger.warning(
                    f"First mz > second mz. Switcing positions.")
                largerNum = self.ctrlXPos1
                self.ctrlXPos1 = self.xDataPos2
                self.ctrlXPos2 = largerNum
            start_indx = np.where(
                self.mz_arr == self.ctrlXPos1)[0][0]  # (array([X]),)
            end_indx = np.where(
                self.mz_arr == self.ctrlXPos2)[0][0]  # (array([X]),)
            mz_sub_arr = self.mz_arr[start_indx:end_indx + 1]
            charge = ms_utils.check_charge_state_centroid(
                mz_sub_arr, self.ctrlXPos1)
            rowPosition = self.table.rowCount()
            self.table.insertRow(rowPosition)
            self.table.setItem(
                rowPosition, 0,
                QtGui.QTableWidgetItem(str(round(self.ctrlXPos1, 4))))
            self.table.setItem(rowPosition, 1,
                               QtGui.QTableWidgetItem(str(charge)))
            self._addPeakToPeaklist(self.ctrlXPos1, charge)
            print(pformat(self.selectedPeaks))
            self.ctrlXPos1 = 0
            self.ctrlXPos2 = 0

    def mouseClicked(self, event):
        try:
            btn = event[0].button()
            position = self.ScanPlot.vb.mapToView(event[0].pos())
            modifiers = QtGui.QApplication.keyboardModifiers()
            if btn == QtCore.Qt.LeftButton:
                if modifiers == QtCore.Qt.ControlModifier:
                    self._handleCtrlClick(position)
                    return
                if self.clicked == 0:
                    self.xDataPos1 = ms_utils.get_closest_point(
                        position.x(), list(self.mz_arr))
                    self.clicked = 1
                    if self.vLines:
                        self.vLines[0].setPos(position.x())
                    else:
                        self._addVLines()
                        self.vLines[0].setPos(position.x())
                else:
                    self.xDataPos2 = ms_utils.get_closest_point(
                        position.x(), list(self.mz_arr))
                    self.clicked = 0
                    if self.vLines:
                        self.vLines[1].setPos(position.x())
                    else:
                        self._addVLines()
                        self.vLines[1].setPos(position.x())
                    self.changeXRange(self.xDataPos1, self.xDataPos2)
                # rowPosition = self.table.rowCount()

            elif btn == QtCore.Qt.RightButton:
                self.xDataPos1 = 0
                self.xDataPos2 = 0
                self.ctrlXPos1 = 0
                self.ctrlXPos2 = 0
                self.ctrlClicked = 0
                self.changeXRange(0, self.mz_max + 100)
        except Exception:
            self.logger.error(
                f"Error peak picking; click: {self.clicked} X1: {self.xDataPos1}; X2: {self.xDataPos2}\n##TRACE\n{traceback.format_exc()}"
            )

    def _setBinSizeCentroid(self, x_range):
        delta = x_range[1] - x_range[0]
        if delta < 50:
            return 0
        elif delta < 100:
            return 10
        elif delta < 200:
            return 25
        elif delta < 500:
            return 50
        else:
            return 100

    def _clearTextItems(self):
        try:
            for i in self.textItems:
                self.ScanPlot.removeItem(i)
            self.textItems = []
        except Exception:
            self.logger.error(
                f"Failed clearing TextItems:\n{traceback.format_exc()}")

    def _annotateCentroidData(self, x_range):
        lastBin = x_range[0]
        paddedArrMax = x_range[1]
        binSize = self._setBinSizeCentroid(x_range)
        currBin = 0
        xPoints = []
        yPoints = []
        # if zero, assume annotate all
        if binSize > 0:
            while lastBin < paddedArrMax:
                currBin = lastBin + binSize
                # np.where returns an arr of indxs
                xRangeIndx = np.where(
                    np.logical_and(self.mz_arr > lastBin,
                                   self.mz_arr <= currBin))[0]
                if len(xRangeIndx):
                    buff = self.int_arr[xRangeIndx[0]:xRangeIndx[-1] + 1]
                    yMax = max(buff)
                    correspondingXpos = self.mz_arr[np.where(
                        self.int_arr == yMax)[0][0]]
                    xPoints.append(round(correspondingXpos, 4))
                    yPoints.append(yMax)
                lastBin = currBin
        else:
            xRangeIndx = np.where(
                np.logical_and(self.mz_arr > x_range[0],
                               self.mz_arr <= x_range[1]))[0]
            for i in xRangeIndx:
                xPoints.append(round(self.mz_arr[i], 4))
                yPoints.append(self.int_arr[i])

        for i in zip(xPoints, yPoints):
            # try with html
            text = pg.TextItem(
                text=str(i[0]),
                color=(0, 0, 0),
                anchor=(0, 0.5),
                angle=90,
            )
            text.setPos(i[0], i[1] + 10)
            self.textItems.append(text)
            self.ScanPlot.addItem(text)

    def annotateViewWithText(self):
        xrng = self.ScanPlot.vb.viewRange()[0]
        self.logger.debug(f"SHOWING X RANGE: {xrng}")
        try:
            self._annotateCentroidData(xrng)
        except Exception as e:
            self.logger.error(
                f"##failed annotating view:\n{traceback.format_exc()}")

    def closeEvent(self, event):
        close = QtGui.QMessageBox.question(
            self, "QUIT", "Do you wish to save results?",
            QtGui.QMessageBox.Cancel | QtGui.QMessageBox.Yes
            | QtGui.QMessageBox.No)
        if close == QtGui.QMessageBox.Yes:
            if self.selectedPeaks:
                self.db.insert_many_masses_into_curr(self.selectedPeaks)
                self.logger.debug(
                    f"Saved {len(self.selectedPeaks)} results for peak: {self.peak_num}"
                )
            event.accept()
        elif close == QtGui.QMessageBox.No:
            self.logger.debug(
                f"Exited Scan at {self.ret_time} without saving.")
            event.accept()
        else:
            event.ignore()


class App(QtGui.QMainWindow):
    def __init__(self, path, chrom_data, db, worker=None):
        super().__init__()
        self.title = "MSpec"
        self.top = 100
        self.left = 100
        self.width = 900
        self.height = 500
        self.scanWin = None
        self.curPeak = 1
        self.click_count = 1
        self.customParams = None
        self.paramsDialog = None
        self.path = path
        self.chrom_data = chrom_data
        self.worker = worker
        self.db = db
        self.logger = logging.getLogger("GUI")
        self.initUI()
        self.initWindow()
        self.logger.debug("Initialized app.")

    def initWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.top, self.left, self.width, self.height)
        self.show()

    def initUI(self):
        self.widget = QtGui.QWidget()
        # TODO make separate functions
        self.paramsButton = QtGui.QPushButton("Params")
        self.nextPeakButton = QtGui.QPushButton("Add Peak")
        self.refreshButton = QtGui.QPushButton("Refresh")
        self.clearButton = QtGui.QPushButton("Clear")
        self.runButton = QtGui.QPushButton("Run")
        self.table = QtGui.QTableWidget(0, 3)
        self.header_labels = ['Peak #', "mz", "Charge"]
        self.table.setHorizontalHeaderLabels(self.header_labels)
        header = self.table.horizontalHeader()  #.setDefaultSectionSize(100)
        header.setDefaultSectionSize(75)
        header.setResizeMode(QtGui.QHeaderView.Stretch)
        # header.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        # header.setStretchLastSection(True)
        # self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.statusBar().showMessage(f"Current peak: {self.curPeak}")

        # Create graph window
        self.graph = pg.GraphicsWindow()
        self.graph.setBackground('w')
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.label = pg.LabelItem(justify='center')
        self.graph.addItem(self.label)

        # Add plots
        self.TicPlot = self.graph.addPlot(row=1, col=0, title="TIC")
        self.TicPlot.enableAutoRange(axis='y')
        self.TicPlot.setMouseEnabled(x=True, y=False)
        self.TicPlot.setLabel('left', "Intensity")
        self.TicPlot.setLimits(
            xMin=0, xMax=self.chrom_data["retention_times"][-1])
        self.proxy = pg.SignalProxy(
            self.TicPlot.scene().sigMouseClicked, slot=self.mouseClicked)
        self.moved_proxy = pg.SignalProxy(
            self.TicPlot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.mouseMoved)
        self.BpcPlot = self.graph.addPlot(row=2, col=0, title="BPC")
        self.BpcPlot.enableAutoRange(axis='y')
        self.BpcPlot.setMouseEnabled(x=True, y=False)
        self.BpcPlot.setLabel('left', "Intensity")
        self.BpcPlot.setLimits(
            xMin=0, xMax=self.chrom_data["retention_times"][-1])

        # Sync plot movements
        self.TicPlot.getViewBox().setXLink(self.BpcPlot)

        # conn relative axis to 1st plot
        self.TicRel = pg.ViewBox()
        self.TicPlot.showAxis('right')
        self.TicPlot.scene().addItem(self.TicRel)
        self.TicPlot.getAxis('right').linkToView(self.TicRel)
        self.TicRel.setXLink(self.TicPlot)
        # self.TicRel.setYRange(0, 1.1, padding=0)

        # conn relative axis to 2nd plot
        self.BpcRel = pg.ViewBox()
        self.BpcPlot.showAxis('right')
        self.BpcPlot.scene().addItem(self.BpcRel)
        self.BpcPlot.getAxis('right').linkToView(self.BpcRel)
        self.BpcRel.setXLink(self.BpcPlot)

        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        #self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.TicPlot.addItem(self.vLine, ignoreBounds=False)
        #self.TicPlot.addItem(self.hLine, ignoreBounds=True)

        # Add widgets to the layout in chosen proper positions
        layout = QtGui.QGridLayout()
        self.widget.setLayout(layout)

        layout.addWidget(
            self.table,
            0,
            0,
        )  # table widget goes left
        layout.addWidget(self.graph, 0, 1)  # plot goes on right side

        layout.addWidget(self.nextPeakButton)
        layout.addWidget(self.paramsButton)
        layout.addWidget(self.refreshButton)
        layout.addWidget(self.runButton)
        layout.addWidget(self.clearButton)
        self.paramsButton.clicked.connect(self.paramsButtonClicked)
        self.nextPeakButton.clicked.connect(self.nextPeakButtonClicked)
        self.refreshButton.clicked.connect(self.refreshButtonClicked)
        self.clearButton.clicked.connect(self.clearButtonClicked)
        self.runButton.clicked.connect(self.runButtonClicked)

        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 3)

        # Add widget to main win
        self.setCentralWidget(self.widget)

    def refreshButtonClicked(self):
        self.refreshTable()

    def runButtonClicked(self, event):
        # TODO this is broken; lots of zombie code...
        # self.customParams = self.paramsDialog.provideParamsDict()
        try:
            # with open(path.join(path.abspath(path.dirname(__file__)), "worker", "config.json"),"r") as cc:
            #     conf = json.load(cc)
            # if self.customParams == None:
            #     wk = worker.GlycomodWorker(
            #         conf,
            #         self.db,
            #         reducing_end=None,
            #         adduct="H+",
            #         adduct_extra_mass="",
            #         save_txt=False,
            #         filename="",
            #         params=None)
            # else:
            #     wk = worker.GlycomodWorker(
            #         conf,
            #         self.db,
            #         reducing_end=None,
            #         adduct="H+",
            #         adduct_extra_mass="",
            #         save_txt=False,
            #         filename="",
            #         params=self.customParams)
            # wk.run()
            close = QtGui.QMessageBox.question(
                self, "INFO", "Function is currently broken",
                QtGui.QMessageBox.Yes)
            if close == QtGui.QMessageBox.Yes:
                event.ignore()
            else:
                event.ignore()
        except Exception:
            self.logger.error(traceback.format_exc())

    def paramsButtonClicked(self):
        self.logger.debug("Params window opened")
        try:
            self.paramsDialog = ParamsDialog(self.logger)
            self.paramsDialog.show()
        except Exception:
            self.logger.error(traceback.format_exc())

    def clearButtonClicked(self):
        self.db.clear_current_masses()
        self.table.clearContents()
        self.table.setRowCount(0)

    def nextPeakButtonClicked(self):
        self.curPeak += 1
        self.statusBar().showMessage(f"Current peak: {self.curPeak}")

        self.logger.debug(f"ADDED NEW PEAK {self.curPeak}")

    def plotChroms(self, chrom_data):
        self.logger.debug("Plotting TIC and BPI chromatograms.")
        self.TicPlot.plot(
            chrom_data["retention_times"], chrom_data["TIC"], pen='r')
        self.BpcPlot.plot(
            chrom_data["retention_times"], chrom_data["BPI"], pen='g')

    def __stem_plot(self, x, y, retention_time):
        """DEPRECATED"""
        p = pg.plot(
            np.repeat(x, 2),
            np.dstack((np.zeros(y.shape[0], dtype=int), y)).flatten(),
            pen=pg.mkPen('b', width=1.2),
            connect='pairs',
            name=f"Spectrum: {retention_time}")
        mx_y = max(y)  # set set y-ax
        p.setYRange(0, mx_y + mx_y * 0.1)

        p.setMouseEnabled(y=False)
        points_to_show = ms_utils.primitive_peak_find(y)
        # WORKS
        # TODO check out viewBox.viewRAnge - plot all in range, else do primitive

        for i in points_to_show:
            text = pg.TextItem(
                text="{0:.3f}".format(x[i]),
                color=(0, 0, 0),
                anchor=(0, 0.5),
                angle=90)
            p.addItem(text)
            text.setPos(x[i], y[i])
        p.setYRange(0, mx_y + mx_y * 0.1)
        p.setMouseEnabled(y=False)

    def line_plot(self, x, y, retention_time):
        p = pg.plot(
            x,
            y,
            pen=pg.mkPen('b', width=1.2),
            name=f"Spectrum: {retention_time}")
        mx_y = max(y)
        p.setYRange(0, mx_y)

        p.setMouseEnabled(y=False)

    def mouseClicked(self, event):
        positions = self.TicPlot.vb.mapToView(event[0].pos())
        xpos = round(positions.x(), 4)
        modifiers = QtGui.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            closest_spec = ms_utils.get_closest_point(
                xpos, self.chrom_data["retention_times"])
            mz_arr, int_arr, scan_type = ms_utils.get_spectrum(
                closest_spec, self.path)
            self.scanWin = ScanWindow(self.curPeak, mz_arr, int_arr,
                                      closest_spec, self.logger, self.db)

    def mouseMoved(self, event):
        pos = event[0]
        if self.TicPlot.sceneBoundingRect().contains(pos):
            mousePoint = self.TicPlot.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            if index > 0 and index < len(self.chrom_data["retention_times"]):
                self.label.setText(
                    "<span style='font-size: 12pt'>x=%0.1f" % (mousePoint.x()))
            self.vLine.setPos(mousePoint.x())
            #self.hLine.setPos(mousePoint.y())

    def refreshTable(self):
        try:
            data_tuples = self.db.read_current_masses()
            self._populateTableRows(data_tuples)
        except Exception:
            self.logger.error(
                f"failed refreshing tables:\n{traceback.format_exc()}")

    def _populateTableRows(self, data_tuples):
        try:
            self.table.clearContents()
            self.table.setRowCount(0)
            for i in data_tuples:
                rowPosition = self.table.rowCount()
                self.table.insertRow(rowPosition)
                self.table.setItem(rowPosition, 0,
                                   QtGui.QTableWidgetItem(str(i[0])))
                self.table.setItem(rowPosition, 1,
                                   QtGui.QTableWidgetItem(str(i[1])))
                self.table.setItem(rowPosition, 2,
                                   QtGui.QTableWidgetItem(str(i[2])))
        except Exception:
            self.logger.error(
                f"Failed populating table rows:\n{traceback.format_exc()}")


# TODO parse and validate text
class ParamsDialog(QDialog):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self._cBoxes = None
        self._hBoxes = None
        self._lEdits = None
        self.readiedForm = None
        self.resize(300, 500)

        self.createForm()

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok
                                     | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.processForm)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.setWindowTitle("Choose analysis parameters")

    def provideParamsDict(self):
        return self.readiedForm

    def processForm(self):
        try:
            self.readiedForm = self._parseForm()
            self._validateForm(self.readiedForm)
            self.accept()
        except Exception as e:
            self.reject()
            self.logger.error(f"FAILED PROCESSING FORM\n{e}")

    def _parseForm(self):
        paramsDict = {}
        try:
            for k, v in self._lEdits.items():
                if len(v.text()) > 0:
                    paramsDict[k] = v.text()
                else:
                    paramsDict[k] = ""
            for k, v in self._cBoxes.items():
                paramsDict[k] = v.currentText()
            for k, v in self._hBoxes.items():
                presentStr = k + "pres"
                present = ""
                lowerLim = ""
                lowerLimStr = k + "low"
                upperLim = ""
                upperLimStr = k + "high"
                for i in range(3):
                    if i == 0:
                        present = v.itemAt(i).widget().currentText()
                    elif i == 1:
                        lowerLim = v.itemAt(i).widget().text()
                    else:
                        upperLim = v.itemAt(i).widget().text()
                paramsDict[lowerLimStr] = lowerLim
                paramsDict[upperLimStr] = upperLim
                paramsDict[presentStr] = present
            return paramsDict
        except Exception as e:
            self.logger.error("Error parsing form")
            raise

    def _validateFormHelper(self, form_dict):
        listToCheck = [
            "Hex", "HexNAc", "Fuc", "NeuAc", "NeuGc", "Pent", "SO3", "PO3",
            "KDN", "HexA"
        ]
        for i in listToCheck:
            pres = i + "pres"
            low = i + "low"
            high = i + "high"
            if form_dict[pres] == "no":
                if form_dict[low] != "" and form_dict[high] != "":
                    raise ValueError(
                        f"Error validating form: {pres} set to NO but range values provided"
                    )
            else:
                if form_dict[low] != "":
                    lowInt = int(form_dict[low])
                if form_dict[high] != "":
                    highInt = int(form_dict[high])

    def _validateForm(self, form_dict):
        try:
            tolInt = float(form_dict['Tolerance'])
            if form_dict['N-form'] == 'Derivatised oligosaccharides':
                name = form_dict['Derivative name']
                mass = float(form_dict['Derivative mass'])
            else:
                if form_dict['Derivative name'] != "" and form_dict[
                        'Derivative mass'] != "":
                    raise ValueError(
                        f"Derivatized oligosaccharides NOT SELECTED but derivative properties specified"
                    )
            self._validateFormHelper(form_dict)
        except Exception:
            self.readiedForm = None
            self.logger.error(
                f"Error validating form:\n{traceback.format_exc()}FORM WAS RESET TO DEFAULTS."
            )

    def _populateCboxes(self):
        self._cBoxes = {
            k: QComboBox()
            for k in [
                "Glycan link", "N-form", "Residue property", "Unit", "Adduct",
                "Mono/Avg"
            ]
        }
        for k in self._cBoxes:
            if k == "Glycan link":
                self._cBoxes[k].addItems(["N-linked", "O-linked"])
                continue
            elif k == "N-form":
                self._cBoxes[k].addItems([
                    "Free / PNGase released oligosaccharides",
                    "Derivatised oligosaccharides", "Reduced oligosaccharides",
                    "ENDO H or ENDO F released oligosaccharides",
                    "Glycopeptides (motif N-X-S/T/C (X not P) will be used)"
                ])
                continue
            elif k == "Residue property":
                self._cBoxes[k].addItems(
                    ["underivatised", "permethylated", "peracetylated"])
                continue
            elif k == "Unit":
                self._cBoxes[k].addItems(["Da", "ppm"])
                continue
            elif k == "Adduct":
                self._cBoxes[k].addItems([
                    "H+", "Na+", "K+", "Pos_other", "H-", "M", "Ac", "TFA",
                    "Neg_other"
                ])
            elif k == "Mono/Avg":
                self._cBoxes[k].addItems(["monoisotopic", "average"])

    def _populateHBoxes(self):
        self._hBoxes = {
            k: QHBoxLayout()
            for k in [
                "Hex", "HexNAc", "Fuc", "NeuAc", "NeuGc", "Pent", "SO3", "PO3",
                "KDN", "HexA"
            ]
        }
        for i in self._hBoxes:
            cbox = QComboBox()
            cbox.addItems(["possible", "yes", "no"])
            self._hBoxes[i].addWidget(cbox)
            self._hBoxes[i].addWidget(QLineEdit())
            self._hBoxes[i].addWidget(QLineEdit())

    def _populateLEdits(self):
        self._lEdits = {
            k: QLineEdit()
            for k in ["Tolerance", "Derivative name", "Derivative mass"]
        }

    def createForm(self):
        self._populateCboxes()
        self._populateHBoxes()
        self._populateLEdits()
        self.formGroupBox = QGroupBox("Analysis parameters")
        layout = QFormLayout()
        layout.addRow(QLabel("Mono/Avg"), self._cBoxes["Mono/Avg"])
        layout.addRow(QLabel("Tolerance"), self._lEdits["Tolerance"])
        layout.addRow(QLabel("Unit"), self._cBoxes["Unit"])
        layout.addRow(QLabel("Adduct"), self._cBoxes["Adduct"])
        layout.addRow(QLabel("Glycan link"), self._cBoxes["Glycan link"])
        layout.addRow(QLabel("N-form"), self._cBoxes["N-form"])
        layout.addRow(
            QLabel("Derivative name"), self._lEdits["Derivative name"])
        layout.addRow(
            QLabel("Derivative mass"), self._lEdits["Derivative mass"])
        layout.addRow(
            QLabel("Residue property"), self._cBoxes["Residue property"])
        layout.addRow(QLabel("Hex"), self._hBoxes["Hex"])
        layout.addRow(QLabel("HexNAc"), self._hBoxes["HexNAc"])
        layout.addRow(QLabel("Fuc"), self._hBoxes["Fuc"])
        layout.addRow(QLabel("NeuAc"), self._hBoxes["NeuAc"])
        layout.addRow(QLabel("NeuGc"), self._hBoxes["NeuGc"])
        layout.addRow(QLabel("Pent"), self._hBoxes["Pent"])
        layout.addRow(QLabel("SO3"), self._hBoxes["SO3"])
        layout.addRow(QLabel("PO3"), self._hBoxes["PO3"])
        layout.addRow(QLabel("KDN"), self._hBoxes["KDN"])
        layout.addRow(QLabel("HexA"), self._hBoxes["HexA"])
        self.formGroupBox.setLayout(layout)
