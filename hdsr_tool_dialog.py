# -*- coding: utf-8 -*-
"""
/***************************************************************************
 HDSRToolDialog
                                 A QGIS plugin
 HDSR tool voor grondonderzoek interpretatie
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2022-02-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Breinbaas | Rob van Putten
        email                : breinbaasnl@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure, MouseButton
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtGui
from qgis.core import QgsRectangle

from .project import Project
from .settings import GRONDSOORTEN, SONDERINGEN_MAP, BORINGEN_MAP, PLOT_Y_MIN
from .helpers import case_insensitive_glob
from .soilinvestigation import SoilInvestigation, SoilInvestigationEnum
from .cpt import CPT
from .borehole import Borehole, BOREHOLE_COLORS
from .soillayer import SoilLayer

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'hdsr_tool_dialog_base.ui'))

QC_MAX = 10.0
RF_MAX = 10.0

class HDSRToolDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(HDSRToolDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)   

        self.iface = iface

        # workaround matplotlib bug
        self._figure = None   
        self._canvas = None        

        self.project = Project()
        self.soilinvestigations = []
        self._init()
        self._connect()
        self._prev_index = -1
        self.num_soilinvestigations_to_show = 4

    def _init(self):
        self.project.soiltypes_from_csvstring(GRONDSOORTEN)
        self._updateUI()
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["bovenzijde", "onderzijde", "grondsoort"])          
        

    def _connect(self):
        self.pbLocations.clicked.connect(self.onPbLocationsClicked)
        self.pbFirst.clicked.connect(self.onPbFirstClicked)
        self.pbPrevious.clicked.connect(self.onPbPreviousClicked)
        self.pbNext.clicked.connect(self.onPbNextClicked)
        self.pbLast.clicked.connect(self.onPbLastClicked)
        self.pbStart.clicked.connect(self.onPbStartClicked)
        self.pbUpdate.clicked.connect(self.onPbUpdateClicked)
        self.pbReset.clicked.connect(self.onPbResetClicked)
        self.pbExport.clicked.connect(self.onPbExportClicked)
        self.cbLocations.currentIndexChanged.connect(self.onCbLocationsCurrentIndexChanged)
        self.checkboxAuto.stateChanged.connect(self.onCheckboxAutoStateChanged)
        self.pbLoad.clicked.connect(self.onPbLoadClicked)
        self.pbSave.clicked.connect(self.onPbSaveClicked)
        self.spNumSoilinvestigations.valueChanged.connect(self.onSpNumSoilinvestigationsValueChanged)

    def onSpNumSoilinvestigationsValueChanged(self):
        self.num_soilinvestigations_to_show = self.spNumSoilinvestigations.value()

    def onPbLoadClicked(self):
        # because of the bug in matplot lib this is a fix to couple the figure to the canvas
        # if the bug is fixed this code should be added to the initialization part
        # of the plugin
        if self._figure is None:
            layout = QtWidgets.QVBoxLayout(self.frameMain)
            self._figure = Figure()
            self._figure.set_tight_layout(True)
            self._canvas = FigureCanvas(self._figure)        
            self._figure.canvas.mpl_connect('button_press_event', self.onFigureMouseClicked)
            layout.addWidget(self._canvas)

        filename = QtWidgets.QFileDialog.getOpenFileName(self, 'Load project file', "", "json files (*.json)")[0]
        if filename == "":
            return
        try:
            self.project = Project.from_file(filename)            
        except Exception as e:
            self.project = Project()

        self._updateUI()
        self.cbLocations.clear()        
        if len(self.project.locations) > 0:
            self.cbLocations.addItems([l.name for l in self.project.locations])            
            self.cbLocations.setCurrentIndex(0)        
        self._afterUpdateLocation()

    def onPbSaveClicked(self):
        if self.cbLocations.currentIndex() > -1:
            self._save_location_soillayers(self.cbLocations.currentIndex())
            
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save project file', "project.json", "json files (*.json)")[0]

        if filename != "":
            self.project.save(filename)

    def onCheckboxAutoStateChanged(self):
        self.pbStart.setEnabled(not self.checkboxAuto.isChecked())

        if self.checkboxAuto.isChecked() and self.cbLocations.currentIndex() > -1:
            self._update_closest_soilinvestigations()

    def onCbLocationsCurrentIndexChanged(self):
        # this needs a little explaining...
        # each time the user clicks on the next, prev etc buttons or selects a location
        # from the combobox this event is called but the index is already changed to 
        # the new combobox index which means that to save the data we have to keep
        # track of the previous one which is stored in self._prev_index so we call
        # _save_location_soillayers with the previous index
        # after that we update the _prev_index and everything is fine
        self._save_location_soillayers(self._prev_index)
        self._prev_index = self.cbLocations.currentIndex()
        self._afterUpdateLocation()

    def onPbExportClicked(self):
        if self.cbLocations.currentIndex() > -1:
            self._save_location_soillayers(self.cbLocations.currentIndex())
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save soilprofiles', "soilprofiles.csv", "csv files (*.csv)")[0]

        if filename == "":
            return
        
        self.project.export_to_dam(filename)
        QtWidgets.QMessageBox.information(self, "HDSR tool", f"Grondopbouw weggeschreven naar bestand '{filename}'") 


    def onPbResetClicked(self):
        self.tableWidget.setRowCount(0)
        self._save_location_soillayers(self.cbLocations.currentIndex())

    def onPbUpdateClicked(self):
        self.pbarMain.setValue(0)
        # find all cpt and borehole files
        cpt_files = case_insensitive_glob(SONDERINGEN_MAP, ".gef")
        borehole_files = case_insensitive_glob(BORINGEN_MAP, ".gef")
        self.pbarMain.setMaximum(len(cpt_files) + len(borehole_files))

        sis = []
        for i, cptfile in enumerate(cpt_files):
            self.pbarMain.setValue(i)
            si = SoilInvestigation.from_file(cptfile)
            if si is not None: 
                si.stype = SoilInvestigationEnum.CPT # todo, kan ook uit GEF gelezen worden maar omdat GEF niet altijd betrouwbaar is maar even zo gedaan
                sis.append(si)
            
        for boreholefile in borehole_files:
            self.pbarMain.setValue(self.pbarMain.value() + 1)
            si = SoilInvestigation.from_file(boreholefile)

            if si is not None:
                si.stype = SoilInvestigationEnum.BOREHOLE
                sis.append(si)
        
        self.project.soilinvestigations = sis
        self.pbarMain.setValue(0)
        QtWidgets.QMessageBox.information(self, "HDSR tool", f"Er zijn {len(self.project.cpts)} sonderingen en {len(self.project.boreholes)} boringen gevonden") 

    
    def _update_closest_soilinvestigations(self):
        self._clear_figure()

        self.soilinvestigations = []                
        loc = self.project.locations[self.cbLocations.currentIndex()]

        if len(self.project.soilinvestigations) == 0:
            QtWidgets.QMessageBox.warning(self, "HDSR tool", "Er is geen grondonderzoek gevonden, heb je 'update grondonderzoek' uitgevoerd?")     
            return      

        # use project to find the closest ones
        sis = self.project.get_closest(loc.x_rd, loc.y_rd, max_distance=self.spSearchDistance.value(), num=self.num_soilinvestigations_to_show)

        if len(sis) == 0:
            QtWidgets.QMessageBox.warning(self, "HDSR tool", "Er is geen grondonderzoek gevonden, verruim de zoekafstand.")     
            return      

        self.soilinvestigations = sis
        self._update_figure()
    
    def onPbStartClicked(self):
        if self.cbLocations.currentIndex() < 0:
            return
        self._update_closest_soilinvestigations()
           

    def onPbFirstClicked(self):
        if self.project.has_locations:
            self.cbLocations.setCurrentIndex(0)            

    def onPbPreviousClicked(self):
        if self.project.has_locations and self.cbLocations.currentIndex()  > 0:
            self.cbLocations.setCurrentIndex(self.cbLocations.currentIndex() - 1)    

    def onPbNextClicked(self):
        if self.project.has_locations and self.cbLocations.currentIndex() < len(self.project.locations) - 1:
            self.cbLocations.setCurrentIndex(self.cbLocations.currentIndex() + 1)   

    def onPbLastClicked(self):
        if self.project.has_locations:
            self.cbLocations.setCurrentIndex(len(self.project.locations) - 1)

    def onPbLocationsClicked(self):
        # this is a workaround a bug from matplotlib which does not allow negative sized figures
        # which happens if you initialize the figure in the constructor so we now create this 
        # figure after opening the locations file which happens definitely after the creation of the GUI
        if self._figure is None:
            layout = QtWidgets.QVBoxLayout(self.frameMain)
            self._figure = Figure()
            self._figure.set_tight_layout(True)
            self._canvas = FigureCanvas(self._figure)        
            self._figure.canvas.mpl_connect('button_press_event', self.onFigureMouseClicked)
            layout.addWidget(self._canvas)

        filename = QtWidgets.QFileDialog.getOpenFileName(self, 'Load Locations File', "", "csv files (*.csv)")[0]

        if filename == "":
            return

        # first reset the current project
        self.project.reset()
        self.cbLocations.clear()
        
        self.project.locations_from_csvfile(filename)
        if len(self.project.locations) > 0:
            self.cbLocations.addItems([l.name for l in self.project.locations])            
            self.cbLocations.setCurrentIndex(0)
        
        self._afterUpdateLocation()

    def onFigureMouseClicked(self, e):
        if self.cbLocations.currentIndex() < 0 or len(self.soilinvestigations) == 0:
            return

        if e.button == MouseButton.RIGHT:
            self.remove_last_from_table()            
        elif e.button == MouseButton.LEFT:
            self.add_to_table(e.ydata)
            

    def add_to_table(self, value: float):
        nrows = self.tableWidget.rowCount()
        lastvalue = None
        if nrows > 0:
            item = self.tableWidget.item(nrows-1, 1)
            if item is not None:
                lastvalue = float(self.tableWidget.item(nrows-1, 1).text())

        if nrows == 0: # first entry
            self.tableWidget.setRowCount(1)
            self.tableWidget.setItem(0, 0, QtWidgets.QTableWidgetItem(f"{value:.2f}"))
            return
                    
        if lastvalue is None: # fill in the bottom value                         
            self.tableWidget.setItem(self.tableWidget.rowCount()-1, 1, QtWidgets.QTableWidgetItem(f"{value:.2f}"))                
        else: # create a new row and add the top from the previous line and the bottom from the clicked point
            self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)
            self.tableWidget.setItem(self.tableWidget.rowCount()-1, 0, QtWidgets.QTableWidgetItem(f"{lastvalue}"))
            self.tableWidget.setItem(self.tableWidget.rowCount()-1, 1, QtWidgets.QTableWidgetItem(f"{value:.2f}"))

        cbSoillayers = QtWidgets.QComboBox()
        cbSoillayers.addItems([st.name for st in self.project.soiltypes])
        self.tableWidget.setCellWidget(self.tableWidget.rowCount()-1,2,cbSoillayers)        

    def remove_last_from_table(self):
        if self.tableWidget.rowCount() > 0:
            self.tableWidget.setRowCount(self.tableWidget.rowCount()-1)    
    
    def _save_location_soillayers(self, index):
        if index > -1 and index < len(self.project.locations):        
            self.project.locations[index].soillayers = []
            if self.tableWidget.rowCount() > 0:
                for i in range(self.tableWidget.rowCount()):
                    try:
                        top = float(self.tableWidget.item(i,0).text())
                        bottom = float(self.tableWidget.item(i,1).text())
                        name = self.tableWidget.cellWidget(i,2).currentText()          
                        self.project.locations[index].soillayers.append(SoilLayer(
                            z_top = top,
                            z_bottom = bottom,
                            soilcode = name
                        ))          
                    except Exception as e: # log any errors to the python console
                        print(f"Error trying to save a soillayer to the location; {e}")
    
    def _afterUpdateLocation(self):
        if self.cbLocations.currentIndex() > -1:
            location = self.project.locations[self.cbLocations.currentIndex()]
            self.cbLocations.setCurrentIndex(self.cbLocations.currentIndex())
            self._clear_figure()
            self.tableWidget.setRowCount(len(location.soillayers))

            for i in range(len(location.soillayers)):
                self.tableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(f"{location.soillayers[i].z_top:.2f}"))
                self.tableWidget.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{location.soillayers[i].z_bottom:.2f}"))
                cbSoillayers = QtWidgets.QComboBox()
                cbSoillayers.addItems([st.name for st in self.project.soiltypes])
                try:
                    index = [st.name for st in self.project.soiltypes].index(location.soillayers[i].soilcode)
                    cbSoillayers.setCurrentIndex(index)
                except Exception as e:
                    cbSoillayers.setCurrentIndex(0)
                    print(f"Error,could not find soilname '{location.soillayers[i].soilcode}' in the given resources, got error '{e}'")                
                    
                self.tableWidget.setCellWidget(i,2,cbSoillayers) 

            self.soilinvestigations = []

            if self.checkboxAuto.isChecked():
                self._update_closest_soilinvestigations()
            self._goto()        
   
    def _updateUI(self):
        soiltypes = self.project.soiltypes
        self.tableSoiltypes.setRowCount(len(soiltypes))
        for i, soiltype in enumerate(soiltypes):
            self.tableSoiltypes.setItem(i,0,QtWidgets.QTableWidgetItem(soiltype.name))   
            self.tableSoiltypes.setItem(i,1,QtWidgets.QTableWidgetItem(""))     
            self.tableSoiltypes.item(i,1).setBackground(QtGui.QColor(soiltype.color))    

    def _goto(self):
        if self.cbLocations.currentIndex() > -1:
            location = self.project.locations[self.cbLocations.currentIndex()]            
            box = QgsRectangle(location.x_rd - 100, location.y_rd - 100, location.x_rd + 100, location.y_rd + 100)
            self.iface.mapCanvas().setExtent(box)
            self.iface.mapCanvas().refresh()

    
    def _clear_figure(self):
        self._figure.clear() 
        self._canvas.draw()

    def _update_figure(self):
        self._figure.clear()        

        axs = []
        num = 101 + len(self.soilinvestigations) * 10 # this will create the second number of the subplot which are the num of columns
        for i in range(len(self.soilinvestigations)):
            if i > 0:
                axs.append(self._figure.add_subplot(num+i, sharey=axs[0]))
            else:
                axs.append(self._figure.add_subplot(num+i))
        
        for i, msi in enumerate(self.soilinvestigations):
            dist, si = msi[0], msi[1]
            if si.stype == SoilInvestigationEnum.CPT:                
                try:
                    cpt = CPT.from_file(si.filename)
                    axs[i].title.set_text(f"{cpt.name} ({int(dist)}m)")
                    qcs = [min(qc, QC_MAX) for qc in cpt.qc]

                    zs = [z for z in cpt.z if z > PLOT_Y_MIN]

                    axs[i].plot(qcs[:len(zs)], zs, 'k-')                    
                    rfs = [min(rf, RF_MAX) for rf in cpt.Rf]
                    axs[i].plot(rfs[:len(zs)], zs, 'g--') 
                    axs[i].grid(axis="both")
                    axs[i].set_xlim(0, QC_MAX)
                except:
                    pass
            else:
                try:
                    borehole = Borehole.from_file(si.filename)                    
                    axs[i].title.set_text(f"{borehole.name} ({int(dist)}m)")

                    for soillayer in borehole.soillayers:
                        if soillayer.z_top < PLOT_Y_MIN:
                            break

                        if soillayer.z_bottom < PLOT_Y_MIN:
                            soillayer.z_bottom = PLOT_Y_MIN


                        if len(soillayer.short_soilcode) > 0 and soillayer.short_soilcode[0] in BOREHOLE_COLORS.keys():
                            color = BOREHOLE_COLORS[soillayer.short_soilcode[0]]
                        else:
                            color = "#ccccc8"
                        axs[i].add_patch(
                            patches.Rectangle(
                                (0.1, soillayer.z_bottom),
                                0.8,
                                soillayer.height,
                                fill=True,                                    
                                facecolor=color,
                                edgecolor="#000"
                            )                        
                        )
                        axs[i].text(0.1, soillayer.z_bottom + 0.1, soillayer.short_soilcode)
                        
                except Exception as e:
                    print(e)
                    pass     

        self._canvas.draw()
