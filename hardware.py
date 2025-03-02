# Hardware in use:
# - Custom-built vacuum chamber with adapter PCBs
# - Keithley DMM6500 with a multiplexer
# - Rigol DP811A Programmable Power Supply
import pyvisa

KEITHLEY_DMM6500_VISA_ADDRESS = ''
RIGOL_DP811A_VISA_ADDRESS = ''


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
        self.keithley_dmm6500.timeout = 1000
        self.keithley_dmm6500.write('*RST')
        self.keithley_dmm6500.write('SYST:REM')
        self.keithley_dmm6500.write('TRIG:SOUR IMM')
        self.keithley_dmm6500.write('TRIG:COUN 1')
        self.keithley_dmm6500.write('TRIG:DEL 0')
        self.keithley_dmm6500.write('TRIG:ARM')
    
    def close(self):
        self.keithley_dmm6500.close()
        self.rigol_dp811a.close()
        self.rm.close()