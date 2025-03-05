# Hardware in use:
# - Custom-built vacuum chamber with adapter PCBs
# - Keithley DMM6500 with a multiplexer
# - Rigol DP811A Programmable Power Supply
import pyvisa
import numpy as np


KEITHLEY_DMM6500_VISA_ADDRESS = 'USB0::0x05E6::0x6500::04538852::INSTR'
RIGOL_DP811A_VISA_ADDRESS = 'USB0::0x1AB1::0x0E11::DP8D193500109::INSTR'


class Hardware:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.keithley_dmm6500 = self.rm.open_resource(KEITHLEY_DMM6500_VISA_ADDRESS)
        self.rigol_dp811a = self.rm.open_resource(RIGOL_DP811A_VISA_ADDRESS)
        self.setup_rigol_dp811a()
        self.setup_keithley_dmm6500()
    
    def set_rigol_voltage(self, voltage):
        self.rigol_dp811a.write(f'VOLT {voltage}')
    
    def set_rigol_current(self, current):
        self.rigol_dp811a.write(f'CURR {current}')
    
    def set_rigol_output(self, state):
        self.rigol_dp811a.write(f'OUTP {state.upper()}')
    
    def read_rigol_voltage(self):
        self.rigol_dp811a.write('MEAS:VOLT?')
        return float(self.rigol_dp811a.read().strip('\n'))
    
    def read_rigol_current(self):
        self.rigol_dp811a.write('MEAS:CURR?')
        return float(self.rigol_dp811a.read().strip('\n'))

    def setup_rigol_dp811a(self):
        self.rigol_dp811a.timeout = 1000
        self.rigol_dp811a.write('*RST')
        self.rigol_dp811a.write('SYST:REM')
        self.rigol_dp811a.write('OUTP OFF')
        self.rigol_dp811a.write('VOLT 0')
        self.rigol_dp811a.write('CURR 0')
    
    def setup_keithley_dmm6500(self):
        self.keithley_dmm6500.timeout = 30000
        self.keithley_dmm6500.write('*RST')
        self.keithley_dmm6500.write('TRAC:CLE "defbuffer1"')
        self.keithley_dmm6500.write('TRAC:MAKE "scanbuffer", 20')
        self.keithley_dmm6500.write(':SENS:FUNC "RES", (@1:10)')
        self.keithley_dmm6500.write(':SENS:RES:NPLC 1, (@1:10)')
        self.keithley_dmm6500.write(':ROUT:SCAN:BUFF "scanbuffer"')
        self.keithley_dmm6500.write(':ROUT:SCAN:COUN:SCAN 1')
        self.keithley_dmm6500.write(':SENS:RES:RANG:AUTO ON')
        self.keithley_dmm6500.write('ROUT:SCAN:CRE (@1:10)')
        # self.keithley_dmm6500.write('ROUT:SCAN:CRE "(@101:110)"')
        # self.keithley_dmm6500.write('ROUT:SCAN')
        # self.keithley_dmm6500.write(':SENS:RES:RANG AUTO ON')
        #self.keithley_dmm6500.write('AZER ON')
        #self.keithley_dmm6500.write('INIT:CONT ON')
        #self.keithley_dmm6500.write('ROUT:SCAN:START')
    
    def read_keithley_dmm6500(self, channel):
        self.keithley_dmm6500.write(f'ROUT:SCAN:CHAN {channel}')
        self.keithley_dmm6500.write('MEAS:RES?')
        return self.keithley_dmm6500.read().strip('\n')
    
    def res_to_temp(self, R):
        return 1 / (1.113e-3 + 2.43e-4*np.log(R) + 8.87e-8*(np.log(R)**3)) - 273.15
    
    def close(self):
        self.rigol_dp811a.write('OUTP OFF')
        self.keithley_dmm6500.close()
        self.rigol_dp811a.close()
        self.rm.close()
    

def list_available_instruments():
    rm = pyvisa.ResourceManager()
    print('All addresses:', rm.list_resources())
    i = 0
    for key, value in rm.list_resources_info().items():
        print(f'\nInstrument {i}:', key)
        print('  Interface type:', value.interface_type)
        print('  Interface board number:', value.interface_board_number)
        print('  Resource class:', value.resource_class)
        print('  Resource name:', value.resource_name)
        print('  Resource alias:', value.alias)
        i += 1

if __name__=='__main__':
    # list_available_instruments()
    hardware = Hardware()
    hardware.keithley_dmm6500.write('INIT')
    hardware.keithley_dmm6500.write('*WAI')
    hardware.keithley_dmm6500.write(':ROUT:SCAN:STAT?')
    print(hardware.keithley_dmm6500.read())
    print()
    hardware.keithley_dmm6500.write(':READ? "scanbuffer"')
    print(hardware.keithley_dmm6500.read())
    print()
    hardware.keithley_dmm6500.write(':TRAC:DATA? 1, 10, "scanbuffer", READ')
    print(hardware.keithley_dmm6500.read())
    hardware.keithley_dmm6500.write(':SYST:ERR?')
    print(hardware.keithley_dmm6500.read())

    """ import libusb_package
    import usb.core
    import usb.backend.libusb1

    libusb1_backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    # -> calls usb.libloader.load_locate_library(
    #                ('usb-1.0', 'libusb-1.0', 'usb'),
    #                'cygusb-1.0.dll', 'Libusb 1',
    #                win_cls=win_cls,
    #                find_library=find_library, check_symbols=('libusb_init',))
    #
    # -> calls find_library(candidate) with candidate in ('usb-1.0', 'libusb-1.0', 'usb')
    #   returns lib name or path (as appropriate for OS) if matching lib is found

    # It would also be possible to pass the output of libusb_package.get_libsusb1_backend()
    # to the backend parameter here. In fact, that function is simply a shorthand for the line
    # above.
    devices = usb.core.find(find_all=True, backend=libusb1_backend)
    for device in devices:
        print(f'Device: {hex(device.idVendor)}:{hex(device.idProduct)}') """

    """ import libusb_package

    for dev in libusb_package.find(find_all=True):
        print(dev)

    import usb.core
    import usb.util
    devices = usb.core.find(find_all=True)
    for device in devices:
        print(device) """
    """ hardware = Hardware()
    hardware.setup_keithley_dmm6500()
    import time
    for i in range(1, 10):
        time.sleep(1)
        print(hardware.read_keithley_dmm6500(i))
    hardware.close()
    hardware.keithley_dmm6500.write('FETCh?')
    print(hardware.keithley_dmm6500.read())
    print('Done')
    hardware.close() """