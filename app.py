import datetime
import shutil
import os
import matplotlib.colors as mcolors
import pandas as pd
from PyQt6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
from pathlib import Path
from random import randint
import seaborn as sns
from hardware import Hardware

palette = sns.color_palette()
COLORS = [mcolors.to_hex(color) for color in palette]

CHANNELS = [f"ch{i}" for i in range(1, 11)]
PS_INFO_FIELDS = ['Current I (A)', 'Voltage (V)', 'Power On (sec)', 'Power Off (sec)', 'Sample Rate (sec)', 'Start Cycle', 'End Cycle']
CSV_PATH = 'test-data'


class CheckableComboBox(QtWidgets.QComboBox):

    selectionChanged = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.closeOnLineEditClick = False

        self.lineEdit().installEventFilter(self)
        self.view().viewport().installEventFilter(self)

        self.model().dataChanged.connect(self.updateLineEdit)
    
    def eventFilter(self, widget, event):
        """
        Filter events for the line edit and the view
        """
        if widget is self.lineEdit():
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return super().eventFilter(widget, event)
        
        elif widget is self.view().viewport():
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())
                if item.checkState() == QtCore.Qt.CheckState.Checked:
                    item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                return True
            return super().eventFilter(widget, event)
    
    def hidePopup(self):
        """
        Hide the popup and delay by .1 secs to update the line displaying seleted items
        """
        super().hidePopup()
        self.startTimer(100)


    def addItems(self, items, itemList=None, selectedItems=None):
        """
        Add items to the combobox
        """
        for idx, item in enumerate(items):
            try:
                data = itemList[idx]
            except (IndexError, TypeError):
                data = None
            self.addItem(item, data, item in selectedItems)
        self.updateLineEdit()

    def addItem(self, text, userData=None, selected=False):
        """
        Add an item to the combobox
        """
        item = QtGui.QStandardItem(text)
        item.setText(text)

        if userData: item.setData(userData)

        # Enable item checkability
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(QtCore.Qt.CheckState.Unchecked, QtCore.Qt.ItemDataRole.CheckStateRole)

        # Set default checked state
        if selected:
            item.setCheckState(QtCore.Qt.CheckState.Checked)
        else:
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        
        self.model().appendRow(item)

    def updateLineEdit(self):
        """
        Update the line edit with the selected items
        """
        items = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                items.append(item.text())
        self.lineEdit().setText(", ".join(items))

        # Emit signal with selected items
        self.selectionChanged.emit(items)


class MetricBox(QtWidgets.QWidget):
    def __init__(self, title, value, use_float=True):
        super().__init__()
        layout = QtWidgets.QVBoxLayout()
        self.use_float = use_float

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet('font-size: 14px; font-weight: bold;')

        # Large Number Display
        if use_float:
            self.value_label = QtWidgets.QLabel(f"{value:.2f}")
        else:
            self.value_label = QtWidgets.QLabel(str(value))

        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.value_label.setStyleSheet(f"""
            font-size: 26px;
            font-weight: bold;
            background-color: black;
            color: white;
            border: 2px solid black;
            padding: 10px;
        """)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        self.setLayout(layout)

    def update_value(self, new_value):
        """Updates the number displayed in the box"""
        if self.use_float:
            self.value_label.setText(f"{new_value:.2f}")
        else:
            self.value_label.setText(str(new_value))
            

class ParameterSidebar(QtWidgets.QWidget):

    def __init__(self, layout=None):
        super().__init__()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.title_label = QtWidgets.QLabel('Test Parameters')
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px")
        self.main_layout.addWidget(self.title_label)

        # Operator name
        self.operator_name_group = QtWidgets.QGroupBox()
        self.operator_name_field = QtWidgets.QLineEdit(self.operator_name_group)
        self.operator_name = self.create_form_widget(self.operator_name_group, ['Operator Name:'], [self.operator_name_field])
        self.main_layout.addWidget(self.operator_name)

        # Power Supply Info
        self.ps_info_group = QtWidgets.QGroupBox('Power Supply Info')
        self.ps_info_fields = {field: QtWidgets.QLineEdit(self.ps_info_group) for field in PS_INFO_FIELDS}
        self.ps_info = self.create_form_widget(self.ps_info_group, PS_INFO_FIELDS, self.ps_info_fields.values())
        self.main_layout.addWidget(self.ps_info)

        # Channels in Use
        self.active_channels_group = QtWidgets.QGroupBox('Channels in Use')
        self.active_channels_box = CheckableComboBox()
        self.active_channels_box.addItems(CHANNELS, selectedItems=[CHANNELS[0]])
        self.add_grouped_widget(self.active_channels_group, [self.active_channels_box])

        # Channel Names
        self.channel_inputs_group = QtWidgets.QGroupBox("Channel Names")
        self.channel_inputs_fields = {channel: QtWidgets.QLineEdit(self.channel_inputs_group) for channel in CHANNELS}
        self.channel_inputs = self.create_form_widget(self.channel_inputs_group, CHANNELS, self.channel_inputs_fields.values())
        self.main_layout.addWidget(self.channel_inputs)

    
    def add_grouped_widget(self, group_box, list_of_qwidgets, layout=None):
        """
        Adds a QGroupBox to the sidebar with the widgets provided in list_of_qwidgets
        """
        gb_layout = layout or QtWidgets.QVBoxLayout()
        group_box.setLayout(gb_layout)
        for qwidget in list_of_qwidgets:    
            gb_layout.addWidget(qwidget)    
        self.main_layout.addWidget(group_box)

    
    def create_form_widget(self, group_box, field_names, field_widgets):
        """
        Adds a form layout with the given field names and field widgets
        """
        form_layout = QtWidgets.QFormLayout()
        group_box.setLayout(form_layout)

        for field_name, field_widget in zip(field_names, field_widgets):
            if isinstance(field_widget, QtWidgets.QLineEdit):
                field_widget.setMinimumWidth(100)
            form_layout.addRow(field_name, field_widget)
        return group_box
    
    def set_enabled_state(self, enabled: bool):
        """
        Enable or disable all widgets in the sidebar.
        """
        for group in [self.operator_name_group, self.ps_info_group, self.channel_inputs_group]:
            group.setEnabled(enabled)
        self.active_channels_box.setEnabled(enabled)
 

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle('TEC Cycling Test')

        # Buttons
        self.stop_button = QtWidgets.QPushButton('Stop')
        self.start_button = QtWidgets.QPushButton('Start')
        self.save_button = QtWidgets.QPushButton('Save Data as CSV')

        self.start_button.setMinimumSize(150, 50)
        self.stop_button.setMinimumSize(150, 50)
        self.save_button.setMinimumSize(150, 50)

        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setFixedSize(800, 600)

        # The layout of the interface
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)   
        self.main_layout = QtWidgets.QHBoxLayout() 
        self.main_widget.setLayout(self.main_layout)
        
        # Add sidebar    
        self.sidebar = ParameterSidebar()
        self.sidebar.main_layout.addStretch()
        self.main_layout.addWidget(self.sidebar)

        # Create a central widget to hold the plot and buttons
        self.center_layout = QtWidgets.QVBoxLayout()
        self.center_layout.addWidget(self.plot_graph)

        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.addWidget(self.start_button)
        self.button_layout.addWidget(self.stop_button)
        self.center_layout.addLayout(self.button_layout)

        self.status_label = QtWidgets.QLabel('INACTIVE')
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.status_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.status_label.setMaximumHeight(50)
        self.center_layout.addWidget(self.status_label)

        self.main_layout.addLayout(self.center_layout)

        # Add the measurement metrics and display optinons
        self.right_layout = QtWidgets.QVBoxLayout()
        metric_layout = QtWidgets.QVBoxLayout()
        self.metric_group = QtWidgets.QGroupBox('Test Data')
        self.cycle_no = MetricBox('Cycle No.', 0, use_float=False)
        self.current_value = MetricBox('Current I (A):', 3)
        self.voltage_value = MetricBox("Voltage (V):", 34)
        
        for metric in [self.cycle_no, self.current_value, self.voltage_value]:
            metric.setMaximumWidth(200)
            metric.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
            metric_layout.addWidget(metric)
        
        self.metric_group.setLayout(metric_layout)
        self.right_layout.addWidget(self.metric_group)

        # Graph display options
        display_label = QtWidgets.QLabel('Channels to Display:')
        self.right_layout.addWidget(display_label)

        self.display_selector = QtWidgets.QTableView()
        self.model = QtGui.QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Channel", "Color"])
        
        # Define the channel names and colors
        for row in range(len(CHANNELS)):
            channel_item = QtGui.QStandardItem(CHANNELS[row])
            channel_item.setCheckable(True)  # Make this item checkable
            channel_item.setFlags(channel_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)

            color_item = QtGui.QStandardItem()
            color_item.setBackground(QtGui.QBrush(QtGui.QColor(COLORS[row])))
            color_item.setFlags(color_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)

            # Add items to the model
            self.model.appendRow([channel_item, color_item])

        self.display_selector.setModel(self.model)
        # Set fixed column width
        self.display_selector.setColumnWidth(0, 80)
        self.display_selector.setColumnWidth(1, 60)

        # Disable automatic resizing
        self.display_selector.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.display_selector.setFixedSize(170, 330)
        
        self.right_layout.addWidget(self.display_selector)

        # Add the save button
        self.save_button.clicked.connect(self.save_csv)

        self.right_layout.addWidget(self.save_button)
        self.main_layout.addLayout(self.right_layout)

        self.channels_in_use = []
        self.channels_in_use2int = []
        self.channel_names_in_use = {channel: f'Temp of {channel.capitalize()}' for channel in CHANNELS}

        # Temperature vs time dynamic plot
        self.plot_graph.setBackground("w")
        self.pens = {channel: pg.mkPen(color, width=3) for channel, color in zip(CHANNELS, COLORS)}
        self.plot_graph.setTitle(" ", color="black", size="20pt")
        styles = {"color": "black", "font-size": "18px"}
        self.plot_graph.setLabel("left", "Temperature (°C)", **styles)
        self.plot_graph.setLabel("bottom", "Time (sec)", **styles)
        self.plot_graph.addLegend()
        self.plot_graph.showGrid(x=True, y=True)
        self.plot_graph.setYRange(20, 40)
        self.time = []
        self.temperatures = {channel: [] for channel in CHANNELS}
        
        # Add a timer to simulate new temperature measurements
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)

        self.power_timer = QtCore.QTimer()
        self.power_timer.timeout.connect(self.update_power_cycle)
        self.power_counter = 0
        self.power_is_on = False

        # Button connections
        self.start_button.clicked.connect(self.start_test)
        self.stop_button.clicked.connect(self.stop_test)

        self.setFocus()
        
        # Initialize the parameters
        self.operator = ''
        self.start_cycle = 0
        self.end_cycle = 0
        self.sample_rate = 0
        self.current_input = 0
        self.voltage_input = 0
        self.power_on = 0
        self.power_off = 0
        self.test_df = None

        if not os.path.exists(CSV_PATH):
            os.makedirs(CSV_PATH)

        # Hardware
        self.hardware = Hardware()

    def start_test(self):
        """
        Disable the sidebar when the test starts
        """
        success = self.read_parameters()
        if not success:
            return
        self.timer.setInterval(self.sample_rate * 1000)
        self.power_timer.setInterval(1000)
        
        self.test_df = f'./{CSV_PATH}/TEC cycling test {datetime.datetime.now().strftime("%d-%m-%Y %H.%M.%S")}.csv'
        df = pd.DataFrame(columns=['Datetime', 'Cycle No.', 'Operator', 'Current I (A)', 'Voltage (V)', *self.channel_names_in_use.values()])
        df.to_csv(self.test_df, index=False)

        self.cycle_no.update_value(0)
        self.update_plot()

        # TODO: Connect to the power supply and start the test and see how it goes, also read temp at start
        self.power_is_on = True
        self.last_power_toggle = datetime.datetime.now()
        self.power_timer.start()
        self.timer.start()
        
        self.status_label.setStyleSheet(f"""
            font-size: 26px;
            font-weight: bold;
            background-color: red;
            color: white;
            padding: 10px;
        """)
        self.status_label.setText('TESTING')

        self.sidebar.set_enabled_state(False)
        self.save_button.setEnabled(False)

    def stop_test(self):
        """
        Enable the sidebar when the test stops
        """
        self.timer.stop()
        self.power_timer.stop()
        self.power_counter = 0
        self.time = []
        self.temperatures = {channel: [] for channel in CHANNELS}

        self.status_label.setStyleSheet(f"""
            font-size: 26px;
            font-weight: bold;
            background-color: green;
            color: white;
            padding: 10px;
        """)
        self.status_label.setText('TEST COMPLETE')

        self.sidebar.set_enabled_state(True)
        self.save_button.setEnabled(True)
    
    def update_plot(self):
        """
        Update the plot with new data
        """
        # Append the new data to the existing CSV file
        row = {}
        row['Datetime'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        row['Cycle No.'] = int(self.cycle_no.value_label.text())
        row['Operator'] = self.operator
        row['Current I (A)'] = self.current_input
        row['Voltage (V)'] = self.voltage_input

        if len(self.time) > 0:
            self.time.append(self.time[-1] + self.sample_rate)
        else:
            self.time.append(0)
        
        temperature_readings = self.hardware.read_keithley_dmm6500_temperatures(self.channels_in_use2int)
        for i, channel in enumerate(self.channels_in_use):
            self.temperatures[channel].append(temperature_readings[i])
            row[f'Temp of {self.channel_names_in_use[channel]}'] = self.temperatures[channel][-1]
        
        new_df = pd.DataFrame([row])
        new_df = new_df.reindex(columns=['Datetime', 'Cycle No.', 'Operator', 'Current I (A)', 'Voltage (V)', *self.channel_names_in_use.values()])
        new_df.to_csv(self.test_df, mode='a', index=False, header=False)
        self.update_visible_channels()
    
    def update_visible_channels(self):
        """
        Updates the plot based on selected channels
        """
        selected_channels = self.get_visible_channels()

        # Clear the plot
        self.plot_graph.clear()

        # Re-plot only selected channels
        for channel in selected_channels:
            pen = self.pens[channel]
            temp_data = self.temperatures[channel]
            self.plot_graph.plot(self.time, temp_data, pen=pen)
    
    def update_power_cycle(self):
        """
        Update the power cycle
        """
        now = datetime.datetime.now()
        elapsed_time = (now - self.last_power_toggle).total_seconds()  # Calculate time difference

        if self.power_is_on and elapsed_time >= self.power_on:
            self.power_is_on = False
            self.last_power_toggle = now  # Update timestamp
            # TODO: Change the power state of the power supply

        elif not self.power_is_on and elapsed_time >= self.power_off:
            self.power_is_on = True
            self.last_power_toggle = now  # Update timestamp
            self.cycle_no.update_value(int(self.cycle_no.value_label.text()) + 1)
            # TODO: Change the power state of the power supply

    def get_visible_channels(self):
        """
        Returns a list of selected channels
        """
        selected_channels = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item.checkState() == QtCore.Qt.CheckState.Checked and item.text() in self.channels_in_use:
                selected_channels.append(item.text())
        return selected_channels

    def save_csv(self):
        if not self.test_df:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'No measurements to save')
            return

        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', '', 'CSV files (*.csv)', options=QtWidgets.QFileDialog.Option.ShowDirsOnly)
        if fileName:
            file_path = Path(fileName)
            if file_path.exists():
                reply = QtWidgets.QMessageBox.question(self, 'File Exists', 'File already exists. Do you want to overwrite it?', QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, QtWidgets.QMessageBox.StandardButton.No)
                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    return

            try:
                shutil.copy(self.test_df, fileName)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f'Could not save file: {e}')
    
    def read_parameters(self):
        """
        Read the parameters from the sidebar
        """
        self.operator = self.sidebar.operator_name_field.text()
        if not self.operator:
            QtWidgets.QMessageBox.warning(self, 'No Operator Name', 'Enter the operator name')
            return False
        
        try:
            self.current_input = float(self.sidebar.ps_info_fields['Current I (A)'].text().replace(',', '.'))
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Current Input', 'Enter a valid current input')
            return False
        
        try:
            self.voltage_input = float(self.sidebar.ps_info_fields['Voltage (V)'].text().replace(',', '.'))
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Voltage Input', 'Enter a valid voltage input')
            return False
        
        try:
            self.power_on = int(self.sidebar.ps_info_fields['Power On (sec)'].text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Power On', 'Enter a valid power on time')
            return False
        
        try:
            self.power_off = int(self.sidebar.ps_info_fields['Power Off (sec)'].text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Power Off', 'Enter a valid power off time')
            return False
        
        try:
            self.sample_rate = int(self.sidebar.ps_info_fields['Sample Rate (sec)'].text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Sample Rate', 'Enter a valid sample rate')
            return False

        try:
            self.start_cycle = int(self.sidebar.ps_info_fields['Start Cycle'].text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid Start Cycle', 'Enter a valid start cycle')
            return False

        try:
            self.end_cycle = int(self.sidebar.ps_info_fields['End Cycle'].text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'No or Invalid End Cycle', 'Enter a valid end cycle')
            return False
        
        self.channels_in_use = self.sidebar.active_channels_box.lineEdit().text().split(", ")
        if not self.channels_in_use:
            QtWidgets.QMessageBox.warning(self, 'No Channels Selected', 'Select at least one channel to use')
            return False
        self.channels_in_use2int = [item.replace("ch", "") for item in self.channels_in_use]
        print(self.channels_in_use2int)

        for channel in self.channels_in_use:
            if self.sidebar.channel_inputs_fields[channel].text():
                self.channel_names_in_use[channel] = f'Temp of {self.sidebar.channel_inputs_fields[channel].text()}'

        if self.end_cycle < self.start_cycle:
            QtWidgets.QMessageBox.warning(self, 'Invalid Cycle Range', 'End cycle must be greater than start cycle')
            return False
        return True
    
    def complete_test(self):
        """
        Finish the test and save the data to a CSV file
        """
        self.timer.stop()
        self.status_label.setStyleSheet(f"""
            font-size: 26px;
            font-weight: bold;
            background-color: green;
            color: white;
            padding: 10px;
        """)
        self.status_label.setText('TEST COMPLETE')
        

    def center_window(self):
        """Centers the main window on the screen"""
        frame_geometry = self.frameGeometry()
        screen = QtWidgets.QApplication.primaryScreen()
        screen_center = screen.availableGeometry().center()
        frame_geometry.moveCenter(screen_center)
        self.move(frame_geometry.topLeft())

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    main = MainWindow()
    main.show()
    main.center_window()
    app.exec()