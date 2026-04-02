##!
##! Copyright(c) 2026 Stanford Research Systems, All rights reserved
##! Subject to the MIT License
##!

from srsgui import Component
from srsgui.inst.commands import (
    Command, GetCommand,
    BoolCommand, BoolGetCommand,
    IntCommand, IntGetCommand,
    FloatCommand, FloatGetCommand,
    DictCommand, DictGetCommand,
)
from srsgui.inst.indexcommands import (
    IndexCommand,
    BoolIndexCommand,
    BoolIndexGetCommand,
    IntIndexCommand,
    FloatIndexCommand,
    DictIndexCommand,
)
from .keys import Keys


# ---------------------------------------------------------------------------
# DisplayCommand / _DisplayProxy
#
# DISP has asymmetric set/query signatures that don't fit any IndexCommand:
#   Set:   DISP i,c   (display_type first, then channel — value before index)
#   Query: DISP?      (no parameter at all → returns 'i,c')
#
# The descriptor returns a proxy on every attribute access.  The proxy
# supports subscript-assignment for the set form and tuple-unpacking for
# the query form:
#
#   dg.display.display['A'] = 11       # DISP 11,2
#   dg.display.display[2]   = 11       # DISP 11,2
#   disp_type, ch = dg.display.display # DISP? → (11, 2)
#   repr(dg.display.display)           # DISP? → '11,2'
# ---------------------------------------------------------------------------

class _DisplayProxy:
    """Proxy returned by DisplayCommand.__get__.

    Supports subscript-assignment (set) and iteration/unpacking (query).
    """

    def __init__(self, index_dict, comm):
        self._index_dict = index_dict
        self._comm = comm

    def _convert_index(self, channel):
        if isinstance(channel, int):
            return channel
        if isinstance(channel, str):
            if channel in self._index_dict:
                return self._index_dict[channel]
            raise KeyError("Key '{}' not in display channel dict".format(channel))
        raise TypeError('Channel must be an int or str key')

    def __setitem__(self, channel, display_type):
        """DISP i,c — set display type i for channel c."""
        idx = self._convert_index(channel)
        self._comm.send('DISP {},{}'.format(display_type, idx))

    def __iter__(self):
        """DISP? — allow tuple unpacking: disp_type, ch = dg.display.display"""
        reply = self._comm.query_text('DISP?')
        parts = reply.strip().split(',')
        yield int(parts[0])
        yield int(parts[1])

    def __repr__(self):
        return self._comm.query_text('DISP?').strip()


class DisplayCommand:
    """Class-level descriptor for the DISP command.

    Set:   ``dg.display.display['A'] = 11``  → ``DISP 11,2``
    Query: ``disp_type, ch = dg.display.display``  → ``DISP?`` → ``(11, 2)``
    """

    def __init__(self, index_dict=None):
        self.index_dict = index_dict or {}

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return _DisplayProxy(self.index_dict, obj.comm)

    def __set__(self, obj, value):
        raise AttributeError("Use subscript assignment: display['channel'] = display_type")


# ---------------------------------------------------------------------------
# FloatDualIndexCommand — generalizable IndexCommand for DLAY-style commands
#
# The DLAY command is asymmetric:
#   Set:   DLAY c,d,t   (two channel indices + float)
#   Query: DLAY? c      (one channel index → returns 'd,+t')
#
# Usage:
#   dg.delays.delay['B']['A'] = 1e-3   # DLAY 3,2,1e-3
#   proxy = dg.delays.delay['B']       # _DualIndexProxy for channel B
#   str(proxy)                         # '2,+0.001000000000'
#   ref, t = proxy                     # (2, 0.001)
# ---------------------------------------------------------------------------

class _DualIndexProxy:
    """Proxy returned by FloatDualIndexCommand[channel].

    Supports:
        proxy[ref_channel] = delay_time    # set DLAY c,d,t
        str(proxy)                         # query DLAY? c → '2,+0.001000000000'
        ref, t = proxy                     # unpack (int d, float t)
    """

    def __init__(self, cmd_obj, channel_idx):
        self._cmd = cmd_obj
        self._channel_idx = channel_idx

    def _query_raw(self):
        return self._cmd._parent.comm.query_text(
            '{0}? {1}'.format(self._cmd.remote_command, self._channel_idx)
        )

    def _convert_ref(self, ref_channel):
        return self._cmd._convert_index(ref_channel)

    def __setitem__(self, ref_channel, delay_time):
        d = self._convert_ref(ref_channel)
        self._cmd._parent.comm.send(
            '{0} {1},{2},{3:e}'.format(
                self._cmd.remote_command,
                self._channel_idx,
                d,
                delay_time,
            )
        )

    def __repr__(self):
        return self._query_raw()

    def __str__(self):
        return self._query_raw()

    def __iter__(self):
        """Allow tuple unpacking: ref, t = dg.delays.delay['B']"""
        reply = self._query_raw()
        d_str, t_str = reply.split(',')
        yield int(d_str.strip())
        yield float(t_str.strip())


class FloatDualIndexCommand(IndexCommand):
    """IndexCommand subclass for commands with asymmetric set/query syntax.

    Set form:   CMD c,d,t   (two channel indices + float value)
    Query form: CMD? c      (one channel index → instrument returns 'd,+t')

    Inherits IndexCommand so that get_command_dict() and
    add_parent_to_index_commands() recognize it automatically.

    Parameters
    ----------
    remote_command_name : str
        The instrument command mnemonic (e.g. 'DLAY').
    index_max : int
        Maximum valid integer index.
    index_min : int, optional
        Minimum valid integer index (default 0).
    index_dict : dict, optional
        Mapping of string tokens to integer indices (e.g. Keys.DelayChannelDict).
    """

    def __init__(self, remote_command_name, index_max, index_min=0, index_dict=None):
        super().__init__(remote_command_name, index_max, index_min, index_dict)

    def __getitem__(self, index):
        """Return a _DualIndexProxy for the given channel index."""
        idx = self._convert_index(index)
        return _DualIndexProxy(self, idx)

    def __setitem__(self, index, value):
        raise TypeError(
            'Use chained subscript syntax to set: '
            'cmd[channel][ref_channel] = delay_time'
        )


# ---------------------------------------------------------------------------
# Component 1 — Interface: IEEE-488.2 basics
# ---------------------------------------------------------------------------

class Interface(Component):
    """IEEE-488.2 standard commands."""

    # *IDN? — identification string (query only)
    id_string = GetCommand('*IDN')

    # *OPC? — operation complete (query only); also has set form via method
    operation_complete = IntGetCommand('*OPC')

    # *CAL? — run auto calibration; returns 0=success, 17=fail (query only)
    calibrate = IntGetCommand('*CAL')

    # *TST? — self test; returns 0=success, 16=fail (query only)
    self_test = IntGetCommand('*TST')

    def set_opc(self):
        """*OPC — set form: sets OPC bit in ESR when all commands complete."""
        self.comm.send('*OPC')

    def wait(self):
        """*WAI — hold off new commands until all prior commands complete."""
        self.comm.send('*WAI')

    def trigger(self):
        """*TRG — initiate a single trigger (or arm for external single-shot)."""
        self.comm.send('*TRG')

    def clear_status(self):
        """*CLS — clear ESR, INSR, and the LERR error queue."""
        self.comm.send('*CLS')

    def reset(self):
        """*RST — restore factory defaults."""
        self.comm.send('*RST')


# ---------------------------------------------------------------------------
# Component 2 — System: settings save/recall
# ---------------------------------------------------------------------------

class System(Component):
    """Settings storage and power-on configuration."""

    # *PSC(?) — power-on status clear: 0=retain SRE/ESE on power-on, 1=clear
    power_on_status_clear = BoolCommand('*PSC')

    def save(self, location):
        """*SAV i — save current settings to non-volatile location i (1–9)."""
        self.comm.send('*SAV {}'.format(location))

    def recall(self, location):
        """*RCL i — recall settings from location i (0=factory defaults, 1–9=user)."""
        self.comm.send('*RCL {}'.format(location))


# ---------------------------------------------------------------------------
# Component 3 — Status: status registers and error queue
# ---------------------------------------------------------------------------

class Status(Component):
    """Status registers, error queue, and human-readable status summary."""

    # --- Bit dictionaries (used by per-bit IndexCommand instances and get_status_text) ---

    InsrBitDict = {
        Keys.TRIG:         0,
        Keys.RATE:         1,
        Keys.END_OF_DELAY: 2,
        Keys.END_OF_BURST: 3,
        Keys.INHIBIT:      4,
        Keys.ABORT_DELAY:  5,
        Keys.PLL_UNLOCK:   6,
        Keys.RB_UNLOCK:    7,
    }

    EsrBitDict = {
        Keys.OPC: 0,
        Keys.QYE: 2,
        Keys.DDE: 3,
        Keys.EXE: 4,
        Keys.CME: 5,
        Keys.PON: 7,
    }

    StbBitDict = {
        Keys.INSB:      0,
        Keys.BUSY:      1,
        Keys.BURST_BIT: 2,
        Keys.MAV:       4,
        Keys.ESB:       5,
        Keys.MSS:       6,
    }

    # --- Full-register descriptors (class-level) ---

    # INSR? — Instrument Status Register (read clears register)
    instrument_status        = IntGetCommand('INSR')
    # INSE(?) — Instrument Status Enable register
    instrument_status_enable = IntCommand('INSE')
    # *SRE(?) — Service Request Enable register
    serial_poll_enable       = IntCommand('*SRE')
    # *STB? — Status Byte / serial poll register (read-only)
    serial_poll              = IntGetCommand('*STB')
    # *ESE(?) — Standard Event Status Enable register
    event_enable             = IntCommand('*ESE')
    # *ESR? — Standard Event Status Register (read clears register)
    event_status             = IntGetCommand('*ESR')

    def __init__(self, parent):
        super().__init__(parent)
        # Per-bit descriptors (instance-level, keyed by name token)
        self.instrument_status_bit        = BoolIndexGetCommand('INSR', 7, 0, Status.InsrBitDict)
        self.instrument_status_enable_bit = BoolIndexCommand('INSE', 7, 0, Status.InsrBitDict)
        self.serial_poll_enable_bit       = BoolIndexCommand('*SRE', 7, 0, Status.StbBitDict)
        self.serial_poll_bit              = BoolIndexGetCommand('*STB', 7, 0, Status.StbBitDict)
        self.event_enable_bit             = BoolIndexCommand('*ESE', 7, 0, Status.EsrBitDict)
        self.event_bit                    = BoolIndexGetCommand('*ESR', 7, 0, Status.EsrBitDict)
        self.add_parent_to_index_commands()

    def get_last_error(self):
        """LERR? — read one error code from the queue; returns 0 when queue is empty."""
        return int(self.comm.query_text('LERR?'))

    def drain_errors(self):
        """Drain the full LERR? error queue; returns list of non-zero error codes."""
        errors = []
        while True:
            code = self.get_last_error()
            if code == 0:
                break
            errors.append(code)
        return errors

    def get_status_text(self):
        """Return a human-readable summary of all active status bits and errors.

        Returns 'OK' when nothing is set.
        Note: reading instrument_status, event_status, and draining LERR?
        clears those registers/queue.
        """
        msg = ''

        insr = self.instrument_status   # reading clears INSR
        if insr:
            for key, bit in self.InsrBitDict.items():
                if 2 ** bit & insr:
                    msg += 'INSR bit {}, {} is set, '.format(bit, key)

        esr = self.event_status         # reading clears ESR
        if esr:
            for key, bit in self.EsrBitDict.items():
                if 2 ** bit & esr:
                    msg += 'ESR bit {}, {} is set, '.format(bit, key)

        for code in self.drain_errors():
            msg += 'Error {}, '.format(code)

        stb = self.serial_poll
        if stb:
            for key, bit in self.StbBitDict.items():
                if 2 ** bit & stb:
                    msg += 'STB bit {}, {} is set, '.format(bit, key)

        return msg[:-2] if msg else 'OK'


# ---------------------------------------------------------------------------
# Component 4 — Display: front-panel display control
# ---------------------------------------------------------------------------

class Display(Component):
    """Front-panel display configuration."""

    # SHDP(?) — show/hide the front-panel display (True=on, False=off)
    display_on = BoolCommand('SHDP')

    # Display type reference (for documentation / user code)
    DisplayTypeDict = {
        'trigger rate':            0,
        'trigger threshold':       1,
        'trigger single shot':     2,
        'trigger line':            3,
        'advanced triggering':     4,
        'trigger holdoff':         5,
        'prescale config':         6,
        'burst mode':              7,
        'burst delay':             8,
        'burst count':             9,
        'burst period':            10,
        'channel delay':           11,
        'channel output levels':   12,
        'channel output polarity': 13,
        'burst T0 config':         14,
    }

    # DISP — display type indexed by channel token or integer
    #   Set:   dg.display.display['A'] = 11          → DISP 11,2
    #          dg.display.display[2]   = 11          → DISP 11,2
    #   Query: disp_type, ch = dg.display.display    → DISP? → (11, 2)
    display = DisplayCommand(index_dict=Keys.DelayChannelDict)


# ---------------------------------------------------------------------------
# Component 5 — Trigger: trigger configuration
# ---------------------------------------------------------------------------

class Trigger(Component):
    """Trigger source, rate, level, holdoff, inhibit, and prescale settings."""

    TriggerSourceDict = {
        Keys.Internal:     0,
        Keys.ExtRising:    1,
        Keys.ExtFalling:   2,
        Keys.SsExtRising:  3,
        Keys.SsExtFalling: 4,
        Keys.SingleShot:   5,
        Keys.Line:         6,
    }

    InhibitDict = {
        Keys.InhibitOff:      0,
        Keys.InhibitTriggers: 1,
        Keys.InhibitAB:       2,
        Keys.InhibitABCD:     3,
        Keys.InhibitABCDEF:   4,
        Keys.InhibitAll:      5,
    }

    # TSRC(?) — trigger source (default: SingleShot = 5)
    trigger_source = DictCommand('TSRC', TriggerSourceDict)

    # TRAT(?) — internal trigger rate in Hz (default: 1000.0)
    trigger_rate = FloatCommand('TRAT', 'Hz', 0.001, 1e6, 0.001, 6, 1000.0)

    # TLVL(?) — external trigger threshold level in V (default: 1.0)
    trigger_level = FloatCommand('TLVL', 'V', -3.5, 3.5, 0.001, 4, 1.0)

    # HOLD(?) — trigger holdoff time in s (default: 0.0)
    holdoff = FloatCommand('HOLD', 's', 0.0, 1000.0, 1e-9, 10, 0.0)

    # INHB(?) — trigger inhibit mode (default: InhibitTriggers = 1)
    inhibit = DictCommand('INHB', InhibitDict)

    # ADVT(?) — advanced triggering enable (default: False)
    advanced_trigger = BoolCommand('ADVT')

    # Step sizes (non-indexed)
    holdoff_step_size       = FloatCommand('SSHD', 's', 0.0, 1000.0, 1e-12, 10)
    trigger_rate_step_size  = FloatCommand('SSTR', 'Hz', 0.001, 1e6, 0.001, 6)
    trigger_level_step_size = FloatCommand('SSTL', 'V', 0.0, 3.5, 0.001, 4)

    def __init__(self, parent):
        super().__init__(parent)

        # PRES(?)i,j — prescale factor for prescaler i (0=trigger, 1–4=AB,CD,EF,GH)
        # dg.trigger.prescale_factor[0] = 100  →  PRES 0,100
        self.prescale_factor = IntIndexCommand('PRES', 4, 0, None, '', 1, 2147483647, 1)

        # PHAS(?)i,j — prescale phase for prescaler i (1–4 only)
        # dg.trigger.prescale_phase[1] = 0   →  PHAS 1,0
        self.prescale_phase = IntIndexCommand('PHAS', 4, 1, None, '', 0, 2147483646, 1)

        # Step sizes for prescale (indexed)
        self.prescale_factor_step = IntIndexCommand('SSPS', 4, 0, None, '', 1, 2147483647, 1)
        self.prescale_phase_step  = IntIndexCommand('SSPH', 4, 1, None, '', 0, 2147483646, 1)

        self.add_parent_to_index_commands()

    def step_holdoff(self, direction):
        """SPHD i — step holdoff by current step size (1=up, 0=down)."""
        self.comm.send('SPHD {}'.format(direction))

    def step_trigger_rate(self, direction):
        """SPTR i — step trigger rate by current step size (1=up, 0=down)."""
        self.comm.send('SPTR {}'.format(direction))

    def step_trigger_level(self, direction):
        """SPTL i — step trigger level by current step size (1=up, 0=down)."""
        self.comm.send('SPTL {}'.format(direction))

    def step_prescale_factor(self, prescaler, direction):
        """SPPS i,j — step prescale factor for prescaler i (1=up, 0=down)."""
        self.comm.send('SPPS {},{}'.format(prescaler, direction))

    def step_prescale_phase(self, prescaler, direction):
        """SPPH i,j — step prescale phase for prescaler i (1=up, 0=down)."""
        self.comm.send('SPPH {},{}'.format(prescaler, direction))


# ---------------------------------------------------------------------------
# Component 6 — Burst: burst mode configuration
# ---------------------------------------------------------------------------

class Burst(Component):
    """Burst mode enable, count, period, delay, and T0 configuration."""

    BurstT0Dict = {
        Keys.T0OnAll:   0,
        Keys.T0OnFirst: 1,
    }

    # BURM(?) — burst mode enable (default: False)
    burst_mode = BoolCommand('BURM')

    # BURC(?) — burst count, number of pulses per burst (default: 5)
    burst_count = IntCommand('BURC', '', 1, 2147483647, 1, 5)

    # BURP(?) — burst period in s (default: 100e-6)
    burst_period = FloatCommand('BURP', 's', 100e-9, 2000.0, 1e-9, 10, 100e-6)

    # BURD(?) — burst delay (delay of first pulse in burst) in s (default: 0.0)
    burst_delay = FloatCommand('BURD', 's', 0.0, 2000.0, 1e-9, 10, 0.0)

    # BURT(?) — burst T0 configuration (default: T0OnAll = 0)
    burst_t0 = DictCommand('BURT', BurstT0Dict)

    # Step sizes
    burst_count_step_size  = IntCommand('SSBC', '', 1, 2147483647, 1)
    burst_delay_step_size  = FloatCommand('SSBD', 's', 0.0, 2000.0, 1e-12, 10)
    burst_period_step_size = FloatCommand('SSBP', 's', 100e-9, 2000.0, 1e-12, 10)

    def step_burst_count(self, direction):
        """SPBC i — step burst count by current step size (1=up, 0=down)."""
        self.comm.send('SPBC {}'.format(direction))

    def step_burst_delay(self, direction):
        """SPBD i — step burst delay by current step size (1=up, 0=down)."""
        self.comm.send('SPBD {}'.format(direction))

    def step_burst_period(self, direction):
        """SPBP i — step burst period by current step size (1=up, 0=down)."""
        self.comm.send('SPBP {}'.format(direction))


# ---------------------------------------------------------------------------
# Component 7 — Delays: per-channel delay settings
# ---------------------------------------------------------------------------

class Delays(Component):
    """Per-channel delay, reference link, and step-size settings.

    Channels are addressed by name ('T0','T1','A'–'H') or integer index (0–9).

    Example usage::

        dg.delays.delay['B']['A'] = 1e-3   # DLAY 3,2,1e-3
        ref, t = dg.delays.delay['B']      # unpack → (2, 0.001)
        str(dg.delays.delay['B'])          # '2,+0.001000000000'
        dg.delays.link['A'] = 0            # LINK 2,0
        dg.delays.delay_step_size['A'] = 1e-9
    """

    def __init__(self, parent):
        super().__init__(parent)

        # DLAY(?)c{,d,t} — asymmetric dual-index delay command
        # Set:   DLAY c,d,t   (channel c relative to channel d with offset t)
        # Query: DLAY? c      → '2,+0.001000000000'
        self.delay = FloatDualIndexCommand('DLAY', 9, 0, Keys.DelayChannelDict)

        # LINK(?)c,d — reference channel link for channel c
        # dg.delays.link['A'] = Keys.T0  →  LINK 2,0
        self.link = IntIndexCommand('LINK', 9, 0, Keys.DelayChannelDict, '', 0, 9, 1)

        # SSDL(?)c,f — delay step size for channel c
        self.delay_step_size = FloatIndexCommand(
            'SSDL', 9, 0, Keys.DelayChannelDict, 's', 0.0, 1000.0, 1e-12, 10
        )

        self.add_parent_to_index_commands()

    def step_delay(self, channel, direction):
        """SPDL c,i — step delay for channel c by current step size (1=up, 0=down).

        Parameters
        ----------
        channel : int or str
            Channel index (0–9) or name ('T0','A','B',...).
        direction : int
            1 to step up, 0 to step down.
        """
        if isinstance(channel, str):
            channel = Keys.DelayChannelDict.get(channel, channel)
        self.comm.send('SPDL {},{}'.format(channel, direction))


# ---------------------------------------------------------------------------
# Component 8 — Outputs: per-output level settings
# ---------------------------------------------------------------------------

class Outputs(Component):
    """Per-output BNC amplitude, offset, and polarity settings.

    Outputs are addressed by name ('T0','AB','CD','EF','GH') or integer index (0–4).

    Example usage::

        dg.outputs.amplitude['AB'] = 3.5   # LAMP 1,3.5
        dg.outputs.offset['AB'] = 0.0      # LOFF 1,0.0
        dg.outputs.polarity['AB'] = True   # LPOL 1,1
    """

    def __init__(self, parent):
        super().__init__(parent)

        # LAMP(?)b,v — output amplitude in volts (default: 2.5 V)
        self.amplitude = FloatIndexCommand(
            'LAMP', 4, 0, Keys.OutputBNCDict, 'V', 0.5, 5.0, 0.001, 4
        )

        # LOFF(?)b,v — output offset in volts (default: 0.0 V)
        self.offset = FloatIndexCommand(
            'LOFF', 4, 0, Keys.OutputBNCDict, 'V', -3.0, 3.0, 0.001, 4
        )

        # LPOL(?)b,i — output polarity: True=positive, False=negative (default: True)
        self.polarity = BoolIndexCommand('LPOL', 4, 0, Keys.OutputBNCDict)

        # Step sizes
        self.amplitude_step_size = FloatIndexCommand(
            'SSLA', 4, 0, Keys.OutputBNCDict, 'V', 0.001, 5.0, 0.001, 4
        )
        self.offset_step_size = FloatIndexCommand(
            'SSLO', 4, 0, Keys.OutputBNCDict, 'V', 0.001, 3.0, 0.001, 4
        )

        self.add_parent_to_index_commands()

    def step_amplitude(self, output, direction):
        """SPLA b,i — step amplitude for output b by current step size (1=up, 0=down).

        Parameters
        ----------
        output : int or str
            Output index (0–4) or name ('T0','AB','CD','EF','GH').
        direction : int
            1 to step up, 0 to step down.
        """
        if isinstance(output, str):
            output = Keys.OutputBNCDict.get(output, output)
        self.comm.send('SPLA {},{}'.format(output, direction))

    def step_offset(self, output, direction):
        """SPLO b,i — step offset for output b by current step size (1=up, 0=down).

        Parameters
        ----------
        output : int or str
            Output index (0–4) or name ('T0','AB','CD','EF','GH').
        direction : int
            1 to step up, 0 to step down.
        """
        if isinstance(output, str):
            output = Keys.OutputBNCDict.get(output, output)
        self.comm.send('SPLO {},{}'.format(output, direction))


# ---------------------------------------------------------------------------
# Component 9 — Network: physical interface and connectivity configuration
# ---------------------------------------------------------------------------

class Network(Component):
    """Physical interface configuration: Ethernet, RS-232, GPIB, and timebase."""

    TimbaseDict = {
        0: Keys.InternalTimebase,
        1: Keys.OcxoTimebase,
        2: Keys.RubidiumTimebase,
        3: Keys.ExternalTimebase,
    }

    # EMAC? — Ethernet MAC address (query only)
    mac_address = GetCommand('EMAC')

    # TIMB? — current timebase source (query only)
    timebase = IntGetCommand('TIMB')

    def go_local(self):
        """LCAL — return to local control (RS-232/Telnet only)."""
        self.comm.send('LCAL')

    def go_remote(self):
        """REMT — lock out front panel (RS-232/raw socket/Telnet only)."""
        self.comm.send('REMT')

    def request_lock(self):
        """LOCK? — request exclusive instrument lock; returns 1 if granted."""
        return int(self.comm.query_text('LOCK?'))

    def release_lock(self):
        """UNLK? — release exclusive instrument lock; returns 1 if released."""
        return int(self.comm.query_text('UNLK?'))

    def reset_interface(self, interface):
        """IFRS i — reset interface i (0=RS-232, 1=GPIB, 2=LAN TCP/IP)."""
        self.comm.send('IFRS {}'.format(interface))

    def get_interface_config(self, param):
        """IFCF?i — query interface configuration parameter i."""
        return self.comm.query_text('IFCF? {}'.format(param))

    def set_interface_config(self, param, value):
        """IFCF i,j — set interface configuration parameter i to j."""
        self.comm.send('IFCF {},{}'.format(param, value))

    def get_eth_phy(self, param):
        """EPHY?i — query Ethernet physical layer configuration parameter i."""
        return int(self.comm.query_text('EPHY? {}'.format(param)))

    def set_eth_phy(self, param, value):
        """EPHY i,j — set Ethernet physical layer configuration parameter i to j."""
        self.comm.send('EPHY {},{}'.format(param, value))

    def set_terminator(self, i, j, k):
        """XTRM i,j,k — set response terminator characters."""
        self.comm.send('XTRM {},{},{}'.format(i, j, k))
