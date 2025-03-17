import argparse
import datetime
import shutil
import time
import os
import matplotlib.colors as mcolors
import pandas as pd
from PyQt6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
from pathlib import Path
from random import randint
import seaborn as sns
from hardware import Hardware
from widgets import MetricBox, ParameterSidebar


PALETTE = sns.color_palette()
COLORS = [mcolors.to_hex(color) for color in PALETTE]
CHANNELS = [f"ch{i}" for i in range(1, 11)]
CSV_PATH = 'test-data'
CYCLES_IN_GRAPH = 5
PS_READING_RATE = 500


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dummy_data=False):
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
        self.current_value = MetricBox('Current I (A):', 0)
        self.voltage_value = MetricBox("Voltage (V):", 0)
        
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
        self.model.itemChanged.connect(self.handle_channel_toggle)

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
        self.plot_curves = {}
        
        self.time = []
        self.temperatures = {channel: [] for channel in CHANNELS}
        
        # Add a timer to simulate new temperature measurements
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)

        self.power_timer = QtCore.QTimer()
        self.power_timer.timeout.connect(self.update_power_cycle)
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
        self.dummy_data = dummy_data
        self.hardware = Hardware() if not dummy_data else None
        self.max_plot_points = 0

    def start_test(self):
        """
        Disable the sidebar when the test starts
        """
        success = self.read_parameters()
        if not success:
            return
        self.timer.setInterval(self.sample_rate * 1000)
        self.power_timer.setInterval(PS_READING_RATE)

        self.time = []
        self.temperatures = {channel: [] for channel in CHANNELS}
        
        self.test_df = f'./{CSV_PATH}/TEC cycling test {datetime.datetime.now().strftime("%d-%m-%Y %H.%M.%S")}.csv'
        self.max_plot_points = int((self.power_on + self.power_off)/self.sample_rate) * CYCLES_IN_GRAPH  # limit to displaying 5 cycles at the same time
        self.init_used_channels()

        df = pd.DataFrame(columns=['Datetime', 'Cycle No.', 'Operator', 'Current I (A)', 'Voltage (V)', *self.channel_names_in_use.values()])
        df.to_csv(self.test_df, index=False)
        self.power_is_on = False
        self.last_power_toggle = datetime.datetime.now()

        # Initialization
        self.cycle_no.update_value(self.start_cycle)
        self.voltage_value.update_value(0)
        self.current_value.update_value(0)
        self.update_plot()
        
        if self.dummy_data:
            pass
        else:
            self.hardware.set_rigol_output('OFF')
            self.hardware.set_rigol_current(self.current_input)
            self.hardware.set_rigol_voltage(self.voltage_input)
            self.update_power_cycle()
        
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
        
        if not self.dummy_data:
            self.hardware.set_rigol_output('OFF')
            self.hardware.set_rigol_current(0)
            self.hardware.set_rigol_voltage(0)

        self.status_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.status_label.setText('TEST STOPPED')

        self.sidebar.set_enabled_state(True)
        self.save_button.setEnabled(True)
    
    def update_plot(self):
        """
        Update the plot with new data
        """
        start_time = time.time()
        # Append the new data to the existing CSV file
        row = {}
        row['Datetime'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        row['Cycle No.'] = int(self.cycle_no.value_label.text())
        row['Operator'] = self.operator
        row['Current I (A)'] = self.hardware.read_rigol_current() if not self.dummy_data else self.current_input
        row['Voltage (V)'] = self.hardware.read_rigol_voltage() if not self.dummy_data else self.voltage_input

        if len(self.time) > 0:
            self.time.append(self.time[-1] + self.sample_rate)
        else:
            self.time.append(0)

        # Limit size of time list
        if len(self.time) > self.max_plot_points:
            self.time = self.time[-self.max_plot_points:]

        temperature_readings = self.hardware.read_keithley_dmm6500_temperatures(self.channels_in_use2int) if not self.dummy_data else [float(randint(20, 40)) for _ in self.channels_in_use2int]
        
        # if not self.dummy_data:
        #   print('TEMP:', temperature_readings)
        #   print('CH:', self.channels_in_use2int)
        
        for i, channel in enumerate(self.channels_in_use):
            self.temperatures[channel].append(temperature_readings[i])
            if len(self.temperatures[channel]) > self.max_plot_points:
                self.temperatures[channel] = self.temperatures[channel][-self.max_plot_points:]

            row[self.channel_names_in_use[channel]] = self.temperatures[channel][-1]
        
        new_df = pd.DataFrame([row])
        new_df = new_df.reindex(columns=['Datetime', 'Cycle No.', 'Operator', 'Current I (A)', 'Voltage (V)', *self.channel_names_in_use.values()])
        new_df.to_csv(self.test_df, mode='a', index=False, header=False)
        self.update_visible_channels()
        time_elapsed = time.time() - start_time
        
        # print(f'Update done in %s' % end_time)
        self.timer.setInterval(self.sample_rate * 1000 - int(time_elapsed * 1000))  # readjust interval calls
    
    def update_visible_channels(self):
        """
        Updates the plot based on selected channels
        """
        selected_channels = self.get_visible_channels()
        
        for channel in self.channels_in_use:
            if channel in selected_channels:
                self.plot_curves[channel].setData(self.time, self.temperatures[channel])
            else:
                self.plot_curves[channel].setData([], [])
        
        # OLD approach 
        # Clear the plot
        # self.plot_graph.clear()

        # Re-plot only selected channels
        # for channel in selected_channels:
            # pen = self.pens[channel]
            # temp_data = self.temperatures[channel]
            # self.plot_graph.plot(self.time, temp_data, pen=pen)
    
    def init_used_channels(self):
        """
        Initializes the plot based on selected channels
        """
        self.plot_graph.clear()
        # Re-plot only selected channels
        for channel in self.channels_in_use:
            self.plot_curves[channel] = self.plot_graph.plot([], [], pen=self.pens[channel])
    
    def update_power_cycle(self):
        """
        Update the power cycle
        """
        # start_time = time.time()
        now = datetime.datetime.now()
        elapsed_time = (now - self.last_power_toggle).total_seconds()  # Calculate time difference

        if self.power_is_on and elapsed_time >= self.power_on:
            self.power_is_on = False
            self.last_power_toggle = now  # Update timestamp

            if int(self.cycle_no.value_label.text()) + 1 > self.end_cycle:
                self.complete_test()
            else:
                self.cycle_no.update_value(int(self.cycle_no.value_label.text()) + 1)
                if not self.dummy_data:
                    self.hardware.set_rigol_output('OFF')
                    self.voltage_value.update_value(self.hardware.read_rigol_voltage())
                    self.current_value.update_value(self.hardware.read_rigol_current())

        elif not self.power_is_on and elapsed_time >= self.power_off:
            self.power_is_on = True
            self.last_power_toggle = now  # Update timestamp
            if not self.dummy_data:
                self.hardware.set_rigol_output('ON')
                self.hardware.set_rigol_current(self.current_input)
                self.hardware.set_rigol_voltage(self.voltage_input)
                
                self.voltage_value.update_value(self.hardware.read_rigol_voltage())
                self.current_value.update_value(self.hardware.read_rigol_current())
        
        elif not self.power_is_on and int(self.cycle_no.value_label.text()) == 0:
            self.cycle_no.update_value(self.start_cycle)
            self.voltage_value.update_value(self.hardware.read_rigol_voltage())
            self.current_value.update_value(self.hardware.read_rigol_current())
        
        elif not self.dummy_data:
            self.voltage_value.update_value(self.hardware.read_rigol_voltage())
            self.current_value.update_value(self.hardware.read_rigol_current())
        
        # if not self.dummy_data:
        #   print('POWER:', self.hardware.read_rigol_voltage(), self.hardware.read_rigol_current())
        #   print(f'POWER done in %s' % (time.time() - start_time))
        
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
        """
        Saves the measurement csv to the desired location
        """
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
        self.update_plot()
        self.timer.stop()
        self.power_timer.stop()

        if not self.dummy_data:
            self.hardware.set_rigol_output('OFF')
            self.hardware.set_rigol_current(0)
            self.hardware.set_rigol_voltage(0)

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

    def center_window(self):
        """
        Centers the main window on the screen
        """
        frame_geometry = self.frameGeometry()
        screen = QtWidgets.QApplication.primaryScreen()
        screen_center = screen.availableGeometry().center()
        frame_geometry.moveCenter(screen_center)
        self.move(frame_geometry.topLeft())

    def handle_channel_toggle(self, item):
        """
        Update the visibility of curves in the graph
        """
        if item.column() != 0:
            return
        
        channel = item.text()
        try:
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                self.plot_curves[channel].setData(self.time, self.temperatures[channel])
            else:
                self.plot_curves[channel].setData([], [])
        except KeyError:
           if len(self.channels_in_use) > 0:
               print(f'Cannot display {channel}, it is not in use for the test')

    def closeEvent(self, event):
        try:
            print('App is closing...')
            if not self.dummy_data:
                self.hardware.close()
            event.accept()
        except Exception as e:
            print(f'Error on closing: {e}')
            event.ignore()

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dummy', '-d', action='store_true', help='Use dummy data')
    return parser


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    print('Starting app...')
    app = QtWidgets.QApplication([])
    main = MainWindow(dummy_data=args.dummy)
    main.show()
    main.center_window()
    app.exec()