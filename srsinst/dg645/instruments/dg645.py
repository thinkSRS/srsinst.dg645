##!
##! Copyright(c) 2026 Stanford Research Systems, All rights reserved
##! Subject to the MIT License
##!

from srsgui import Instrument
from srsgui.inst import TcpipInterface, SerialInterface
from srsgui.task.inputs import FindListInput, IntegerListInput, Ip4Input, IntegerInput

from srsinst.interfaces import Vxi11Interface, VisaInterface
from .components import Interface, System, Status, Display, Trigger, Burst, Delays, Outputs, Network


class DG645(Instrument):
    """Python driver for the SRS DG645 Digital Delay Generator.

    Supports VXI-11, TCP/IP (raw socket), VISA, and RS-232 interfaces.

    Example usage::

        from srsinst.dg645 import DG645

        # Connect via VXI-11
        dg = DG645('vxi11', '192.168.0.10')

        # Connect via serial
        dg = DG645('serial', 'COM3', 9600)

        # Configure a delay: channel B, 1 ms after channel A
        dg.delays.delay['B']['A'] = 1e-3

        # Set output AB amplitude
        dg.outputs.amplitude['AB'] = 3.5

        # Set trigger source to internal at 1 kHz
        dg.trigger.trigger_source = 'internal'
        dg.trigger.trigger_rate = 1000.0

        dg.disconnect()
    """

    _IdString = 'DG645'

    available_interfaces = [
        [
            Vxi11Interface,
            {
                'ip_address': Ip4Input('192.168.0.5'),
            }
        ],
        [
            TcpipInterface,
            {
                'ip_address': Ip4Input('192.168.0.5'),
                'port':       IntegerInput(5025),
            }
        ],
        [
            VisaInterface,
            {
                'resource': FindListInput(),
            }
        ],
        [
            SerialInterface,
            {
                'port':      FindListInput(),
                'baud_rate': IntegerListInput([4800, 9600, 19200, 38400, 57600, 115200], 1),
            }
        ],
    ]

    def __init__(self, interface_type=None, *args):
        super().__init__(interface_type, *args)
        self.interface = Interface(self)
        self.system    = System(self)
        self.status    = Status(self)
        self.display   = Display(self)
        self.trigger   = Trigger(self)
        self.burst     = Burst(self)
        self.delays    = Delays(self)
        self.outputs   = Outputs(self)
        self.network   = Network(self)

    def reset(self):
        """*RST — restore factory defaults."""
        self.send('*RST')

    def trigger_now(self):
        """*TRG — fire a single trigger event."""
        self.send('*TRG')

    def get_status(self):
        """Return a human-readable status string including trigger config and errors."""
        src = self.trigger.trigger_source
        rate = self.trigger.trigger_rate
        burst_on = self.burst.burst_mode
        return (
            'Trigger source: {}\n'.format(src) +
            'Trigger rate: {} Hz\n'.format(rate) +
            'Burst mode: {}\n'.format(burst_on) +
            '\n' +
            self.status.get_status_text()
        )

    allow_run_button = [reset, trigger_now]
