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
        self.keithley_dmm6500.write('TRAC:MAKE "scanbuffer", 20')
        self.keithley_dmm6500.write(':SENS:FUNC "RES", (@1:10)')
        self.keithley_dmm6500.write(':SENS:RES:NPLC 1, (@1:10)')
        self.keithley_dmm6500.write(':ROUT:SCAN:BUFF "scanbuffer"')
        self.keithley_dmm6500.write(':ROUT:SCAN:COUN:SCAN 1')
        self.keithley_dmm6500.write(':SENS:RES:RANG:AUTO ON')
        self.keithley_dmm6500.write(f'ROUT:SCAN:CRE (@1:10)')  # ensure correct channels
    
    def read_keithley_dmm6500_temperatures(self, channels, resistance=False):
        self.keithley_dmm6500.write('TRAC:CLE "scanbuffer"')  # clear buffer
        self.keithley_dmm6500.write('INIT')  # start scan
        self.keithley_dmm6500.write('*WAI')  # wait  for scan to end
        # self.keithley_dmm6500.write(':READ? "scanbuffer"')
        self.keithley_dmm6500.write(f':TRAC:DATA? 1, 10, "scanbuffer", READ')  # read the data
        
        data = self.keithley_dmm6500.read().strip('\n').split(',')
        print(len(data), data)
        if resistance:
            return [float(data[int(channel)]) for channel in channels]
        return [self.res_to_temp(float(value)) for value in data]
        # return [self.res_to_temp(float(data[int(channel) - 1])) for channel in channels]
    
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
    """ hardware.keithley_dmm6500.write('INIT')
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
    print(hardware.keithley_dmm6500.read()) """

    import time
    print('TESTING METHOD')
    chans = ['1', '2', '3', '4', '5', '6']
    print(hardware.read_keithley_dmm6500_temperatures(chans))
    time.sleep(1)
    print(hardware.read_keithley_dmm6500_temperatures(chans))
    time.sleep(1)
    print(hardware.read_keithley_dmm6500_temperatures(chans))
    