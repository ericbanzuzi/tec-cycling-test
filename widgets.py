from PyQt6 import QtCore, QtWidgets, QtGui


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

    CHANNELS = [f"ch{i}" for i in range(1, 11)]
    PS_INFO_FIELDS = ['Current I (A)', 'Voltage (V)', 'Power On (sec)', 'Power Off (sec)', 'Sample Rate (sec)', 'Start Cycle', 'End Cycle']
    def __init__(self, layout=None, ):
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
        self.ps_info_fields = {field: QtWidgets.QLineEdit(self.ps_info_group) for field in self.PS_INFO_FIELDS}
        self.ps_info = self.create_form_widget(self.ps_info_group, self.PS_INFO_FIELDS, self.ps_info_fields.values())
        self.main_layout.addWidget(self.ps_info)

        # Channels in Use
        self.active_channels_group = QtWidgets.QGroupBox('Channels in Use')
        self.active_channels_box = CheckableComboBox()
        self.active_channels_box.addItems(self.CHANNELS, selectedItems=[self.CHANNELS,[0]])
        self.add_grouped_widget(self.active_channels_group, [self.active_channels_box])

        # Channel Names
        self.channel_inputs_group = QtWidgets.QGroupBox("Channel Names")
        self.channel_inputs_fields = {channel: QtWidgets.QLineEdit(self.channel_inputs_group) for channel in self.CHANNELS}
        self.channel_inputs = self.create_form_widget(self.channel_inputs_group, self.CHANNELS, self.channel_inputs_fields.values())
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
