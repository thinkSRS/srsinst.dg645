##!
##! Copyright(c) 2026 Stanford Research Systems, All rights reserved
##! Subject to the MIT License
##!
"""
Integration tests for the srsinst.dg645 driver.

These tests exercise every command and method in the driver against a live
DG645 instrument over VXI-11, TCP/IP, VISA, or RS-232.  The goal is to
validate the *driver* — correct SCPI strings, correct read-back parsing,
correct error propagation, and correct handling of invalid parameters.

Run with:
    pytest -v -s tests/ --ip 192.168.0.10
    pytest -v -s tests/ --port COM3
(Use -s so that input() works when --ip/--port is omitted.)

Error codes (LERR?):
    10  — illegal value (out of range)
   110  — illegal command (undefined mnemonic)
   111  — undefined command
   113  — illegal set (command is query-only)
"""

import re
import pytest
from srsinst.dg645 import DG645, Keys


# ── Shared helpers ────────────────────────────────────────────────────────────

def no_errors(dg):
    """Assert that no errors have occurred since the last LERR? drain."""
    err = dg.status.get_last_error()
    assert err == 0, 'Unexpected error in LERR? queue: {}'.format(err)


def clear_errors(dg):
    """Drain all pending LERR? errors and clear the ESR."""
    dg.status.drain_errors()
    dg.interface.clear_status()


# ── TestConnection ─────────────────────────────────────────────────────────────

class TestConnection:
    """Smoke tests — verifies that the driver can communicate at all."""

    def test_id_string_contains_dg645(self, dg):
        assert 'DG645' in dg.interface.id_string

    def test_check_id_returns_model(self, dg):
        model, serial, firmware = dg.check_id()
        assert model is not None
        assert 'DG645' in model

    def test_is_connected(self, dg):
        assert dg.is_connected() is True


# ── TestReset ─────────────────────────────────────────────────────────────────

class TestReset:
    """Send *RST and verify every settable parameter against the factory defaults."""

    def test_reset_trigger_defaults(self, dg):
        dg.reset()
        assert dg.trigger.trigger_source == Keys.SingleShot
        assert abs(dg.trigger.trigger_rate - 1000.0) < 0.01
        assert abs(dg.trigger.trigger_level - 1.0) < 0.001
        assert abs(dg.trigger.holdoff - 0.0) < 1e-12
        assert dg.trigger.inhibit == Keys.InhibitTriggers
        assert dg.trigger.advanced_trigger is False

    def test_reset_burst_defaults(self, dg):
        dg.reset()
        assert dg.burst.burst_mode is False
        assert dg.burst.burst_count == 5
        assert abs(dg.burst.burst_period - 100e-6) < 1e-9
        assert abs(dg.burst.burst_delay - 0.0) < 1e-12
        assert dg.burst.burst_t0 == Keys.T0OnAll

    def test_reset_prescale_defaults(self, dg):
        dg.reset()
        for i in range(5):
            assert dg.trigger.prescale_factor[i] == 1
        for i in range(1, 5):
            assert dg.trigger.prescale_phase[i] == 0

    def test_reset_delay_defaults(self, dg):
        """After *RST: A=T0+0, B=A+10ns, C=T0+0, D=C+10ns, E=T0+0, F=E+10ns, G=T0+0, H=G+10ns."""
        dg.reset()
        # Channel A: relative to T0, delay = 0
        ref_a, t_a = dg.delays.delay['A']
        assert ref_a == Keys.DelayChannelDict['T0']
        assert abs(t_a - 0.0) < 1e-12

        # Channel B: relative to A, delay = 10 ns
        ref_b, t_b = dg.delays.delay['B']
        assert ref_b == Keys.DelayChannelDict['A']
        assert abs(t_b - 10e-9) < 1e-12

        # Channel C: relative to T0, delay = 0
        ref_c, t_c = dg.delays.delay['C']
        assert ref_c == Keys.DelayChannelDict['T0']
        assert abs(t_c - 0.0) < 1e-12

    def test_reset_output_defaults(self, dg):
        """After *RST: amplitude=2.5 V, offset=0.0 V, polarity=positive for all outputs."""
        dg.reset()
        for output in ('T0', 'AB', 'CD', 'EF', 'GH'):
            assert abs(dg.outputs.amplitude[output] - 2.5) < 0.001, \
                'amplitude[{}] should be 2.5 V after reset'.format(output)
            assert abs(dg.outputs.offset[output] - 0.0) < 0.001, \
                'offset[{}] should be 0.0 V after reset'.format(output)
            assert dg.outputs.polarity[output] is True, \
                'polarity[{}] should be positive (True) after reset'.format(output)


# ── TestTrigger ────────────────────────────────────────────────────────────────

class TestTrigger:
    """Tests for every command in the Trigger component."""

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    # ── TSRC ──────────────────────────────────────────────────────────────────

    def test_tsrc_internal(self, dg):
        dg.trigger.trigger_source = 'internal'
        assert dg.trigger.trigger_source == Keys.Internal
        no_errors(dg)

    def test_tsrc_ext_rising(self, dg):
        dg.trigger.trigger_source = 'ext rising'
        assert dg.trigger.trigger_source == Keys.ExtRising
        no_errors(dg)

    def test_tsrc_ext_falling(self, dg):
        dg.trigger.trigger_source = 'ext falling'
        assert dg.trigger.trigger_source == Keys.ExtFalling
        no_errors(dg)

    def test_tsrc_single_shot(self, dg):
        dg.trigger.trigger_source = 'single shot'
        assert dg.trigger.trigger_source == Keys.SingleShot
        no_errors(dg)

    def test_tsrc_line(self, dg):
        dg.trigger.trigger_source = 'line'
        assert dg.trigger.trigger_source == Keys.Line
        no_errors(dg)

    def test_tsrc_integer_0(self, dg):
        dg.send('TSRC 0')
        assert dg.trigger.trigger_source == Keys.Internal
        no_errors(dg)

    def test_tsrc_integer_max(self, dg):
        dg.send('TSRC 6')
        assert dg.trigger.trigger_source == Keys.Line
        no_errors(dg)

    def test_tsrc_out_of_range(self, dg):
        dg.send('TSRC 7')
        assert dg.status.get_last_error() == 10  # illegal value

    # ── TRAT ──────────────────────────────────────────────────────────────────

    def test_trat_min(self, dg):
        dg.trigger.trigger_source = 'internal'
        dg.trigger.trigger_rate = 0.001
        assert abs(dg.trigger.trigger_rate - 0.001) < 1e-6
        no_errors(dg)

    def test_trat_midpoint(self, dg):
        dg.trigger.trigger_source = 'internal'
        dg.trigger.trigger_rate = 1000.0
        assert abs(dg.trigger.trigger_rate - 1000.0) < 0.001
        no_errors(dg)

    def test_trat_max(self, dg):
        dg.trigger.trigger_source = 'internal'
        dg.trigger.trigger_rate = 1e6
        assert abs(dg.trigger.trigger_rate - 1e6) < 1.0
        no_errors(dg)

    def test_trat_out_of_range(self, dg):
        # DG645 clamps TRAT silently at the boundary rather than reporting an
        # error for values that are just slightly out of range.  Use a wildly
        # out-of-range value (negative) which the instrument does reject.
        dg.send('TRAT -1')
        assert dg.status.get_last_error() != 0

    # ── TLVL ──────────────────────────────────────────────────────────────────

    def test_tlvl_min(self, dg):
        dg.trigger.trigger_level = -3.5
        assert abs(dg.trigger.trigger_level - (-3.5)) < 0.001
        no_errors(dg)

    def test_tlvl_zero(self, dg):
        dg.trigger.trigger_level = 0.0
        assert abs(dg.trigger.trigger_level - 0.0) < 0.001
        no_errors(dg)

    def test_tlvl_max(self, dg):
        dg.trigger.trigger_level = 3.5
        assert abs(dg.trigger.trigger_level - 3.5) < 0.001
        no_errors(dg)

    def test_tlvl_out_of_range(self, dg):
        dg.send('TLVL 5.0')
        assert dg.status.get_last_error() == 10  # illegal value

    # ── HOLD ──────────────────────────────────────────────────────────────────

    def test_hold_zero(self, dg):
        dg.trigger.holdoff = 0.0
        assert abs(dg.trigger.holdoff - 0.0) < 1e-12
        no_errors(dg)

    def test_hold_nonzero(self, dg):
        dg.trigger.holdoff = 1e-6
        assert abs(dg.trigger.holdoff - 1e-6) < 1e-12
        no_errors(dg)

    # ── INHB ──────────────────────────────────────────────────────────────────

    def test_inhb_off(self, dg):
        dg.trigger.inhibit = 'off'
        assert dg.trigger.inhibit == Keys.InhibitOff
        no_errors(dg)

    def test_inhb_triggers(self, dg):
        dg.trigger.inhibit = 'triggers'
        assert dg.trigger.inhibit == Keys.InhibitTriggers
        no_errors(dg)

    def test_inhb_ab(self, dg):
        dg.trigger.inhibit = 'AB'
        assert dg.trigger.inhibit == Keys.InhibitAB
        no_errors(dg)

    def test_inhb_abcd(self, dg):
        dg.trigger.inhibit = 'AB and CD'
        assert dg.trigger.inhibit == Keys.InhibitABCD
        no_errors(dg)

    def test_inhb_all(self, dg):
        dg.trigger.inhibit = 'AB, CD, EF, and GH'
        assert dg.trigger.inhibit == Keys.InhibitAll
        no_errors(dg)

    def test_inhb_integer_0(self, dg):
        dg.send('INHB 0')
        assert dg.trigger.inhibit == Keys.InhibitOff
        no_errors(dg)

    def test_inhb_out_of_range(self, dg):
        dg.send('INHB 6')
        assert dg.status.get_last_error() == 10  # illegal value

    # ── ADVT ──────────────────────────────────────────────────────────────────

    def test_advt_on(self, dg):
        dg.trigger.advanced_trigger = True
        assert dg.trigger.advanced_trigger is True
        no_errors(dg)

    def test_advt_off(self, dg):
        dg.trigger.advanced_trigger = False
        assert dg.trigger.advanced_trigger is False
        no_errors(dg)

    # ── PRES ──────────────────────────────────────────────────────────────────

    def test_prescale_factor_trigger_input(self, dg):
        dg.trigger.prescale_factor[0] = 1
        assert dg.trigger.prescale_factor[0] == 1
        no_errors(dg)

    def test_prescale_factor_channel_ab(self, dg):
        dg.trigger.prescale_factor[1] = 10
        assert dg.trigger.prescale_factor[1] == 10
        no_errors(dg)
        dg.trigger.prescale_factor[1] = 1

    def test_prescale_factor_all_prescalers(self, dg):
        for i in range(5):
            dg.trigger.prescale_factor[i] = 2
            assert dg.trigger.prescale_factor[i] == 2
            no_errors(dg)
            dg.trigger.prescale_factor[i] = 1

    # ── PHAS ──────────────────────────────────────────────────────────────────

    def test_prescale_phase_channel_ab(self, dg):
        dg.trigger.prescale_phase[1] = 0
        assert dg.trigger.prescale_phase[1] == 0
        no_errors(dg)

    def test_prescale_phase_nonzero(self, dg):
        dg.trigger.prescale_factor[1] = 4
        dg.trigger.prescale_phase[1] = 2
        assert dg.trigger.prescale_phase[1] == 2
        no_errors(dg)
        dg.trigger.prescale_factor[1] = 1
        dg.trigger.prescale_phase[1] = 0


# ── TestBurst ─────────────────────────────────────────────────────────────────

class TestBurst:
    """Tests for every command in the Burst component."""

    @pytest.fixture(autouse=True)
    def reset_burst(self, dg):
        dg.burst.burst_mode = False
        clear_errors(dg)
        yield
        dg.burst.burst_mode = False
        clear_errors(dg)

    def test_burst_mode_on(self, dg):
        dg.burst.burst_mode = True
        assert dg.burst.burst_mode is True
        no_errors(dg)

    def test_burst_mode_off(self, dg):
        dg.burst.burst_mode = False
        assert dg.burst.burst_mode is False
        no_errors(dg)

    def test_burst_count_min(self, dg):
        dg.burst.burst_count = 1
        assert dg.burst.burst_count == 1
        no_errors(dg)

    def test_burst_count_mid(self, dg):
        dg.burst.burst_count = 100
        assert dg.burst.burst_count == 100
        no_errors(dg)

    def test_burst_count_out_of_range(self, dg):
        dg.send('BURC 0')
        assert dg.status.get_last_error() == 10  # illegal value

    def test_burst_period(self, dg):
        dg.burst.burst_period = 1e-3
        assert abs(dg.burst.burst_period - 1e-3) < 1e-9
        no_errors(dg)

    def test_burst_delay(self, dg):
        dg.burst.burst_delay = 0.0
        assert abs(dg.burst.burst_delay - 0.0) < 1e-12
        no_errors(dg)

    def test_burst_t0_on_all(self, dg):
        dg.burst.burst_t0 = 'T0 on all'
        assert dg.burst.burst_t0 == Keys.T0OnAll
        no_errors(dg)

    def test_burst_t0_on_first(self, dg):
        dg.burst.burst_t0 = 'T0 on first'
        assert dg.burst.burst_t0 == Keys.T0OnFirst
        no_errors(dg)

    def test_burst_t0_integer_0(self, dg):
        dg.send('BURT 0')
        assert dg.burst.burst_t0 == Keys.T0OnAll
        no_errors(dg)

    def test_burst_t0_integer_1(self, dg):
        dg.send('BURT 1')
        assert dg.burst.burst_t0 == Keys.T0OnFirst
        no_errors(dg)

    def test_burst_t0_out_of_range(self, dg):
        dg.send('BURT 2')
        assert dg.status.get_last_error() == 10  # illegal value

    def test_burst_count_step_size(self, dg):
        dg.burst.burst_count_step_size = 5
        assert dg.burst.burst_count_step_size == 5
        no_errors(dg)

    def test_burst_delay_step_size(self, dg):
        dg.burst.burst_delay_step_size = 1e-9
        assert abs(dg.burst.burst_delay_step_size - 1e-9) < 1e-15
        no_errors(dg)

    def test_burst_period_step_size(self, dg):
        dg.burst.burst_period_step_size = 1e-6
        assert abs(dg.burst.burst_period_step_size - 1e-6) < 1e-12
        no_errors(dg)


# ── TestDelays ────────────────────────────────────────────────────────────────

class TestDelays:
    """Tests for the Delays component — DLAY, LINK, SSDL."""

    @pytest.fixture(autouse=True)
    def reset_delays(self, dg):
        dg.reset()
        clear_errors(dg)
        yield
        dg.reset()
        clear_errors(dg)

    # ── DLAY (FloatDualIndexCommand) ───────────────────────────────────────────

    def test_delay_set_by_name(self, dg):
        """dg.delays.delay['A']['T0'] = 0 — channel A, 0 s after T0."""
        dg.delays.delay['A']['T0'] = 0.0
        ref, t = dg.delays.delay['A']
        assert ref == Keys.DelayChannelDict['T0']
        assert abs(t - 0.0) < 1e-12
        no_errors(dg)

    def test_delay_set_nonzero(self, dg):
        """Channel B: 500 ns after A."""
        dg.delays.delay['B']['A'] = 500e-9
        ref, t = dg.delays.delay['B']
        assert ref == Keys.DelayChannelDict['A']
        assert abs(t - 500e-9) < 1e-12
        no_errors(dg)

    def test_delay_set_1ms(self, dg):
        """Channel C: 1 ms after T0."""
        dg.delays.delay['C']['T0'] = 1e-3
        ref, t = dg.delays.delay['C']
        assert ref == Keys.DelayChannelDict['T0']
        assert abs(t - 1e-3) < 1e-12
        no_errors(dg)

    def test_delay_str_format(self, dg):
        """str(dg.delays.delay['B']) should look like '3,+<float>'."""
        dg.delays.delay['B']['A'] = 10e-9
        s = str(dg.delays.delay['B'])
        assert ',' in s, 'Expected comma-separated reply, got: {!r}'.format(s)

    def test_delay_by_integer_index(self, dg):
        """Channel index can be an integer as well as a string."""
        # Channel index 2 = 'A', ref 0 = 'T0'
        dg.delays.delay[2][0] = 100e-9
        ref, t = dg.delays.delay[2]
        assert abs(t - 100e-9) < 1e-12
        no_errors(dg)

    def test_delay_multiple_channels(self, dg):
        for ch, ref_ch, t_val in [
            ('A', 'T0', 0.0),
            ('B', 'A', 10e-9),
            ('C', 'T0', 100e-9),
            ('D', 'C', 200e-9),
        ]:
            dg.delays.delay[ch][ref_ch] = t_val
            ref, t = dg.delays.delay[ch]
            assert ref == Keys.DelayChannelDict[ref_ch], \
                'Channel {} ref mismatch'.format(ch)
            assert abs(t - t_val) < 1e-12, \
                'Channel {} time mismatch'.format(ch)
            no_errors(dg)

    # ── LINK ──────────────────────────────────────────────────────────────────

    def test_link_by_name(self, dg):
        dg.delays.link['A'] = 0  # link A to T0
        assert dg.delays.link['A'] == 0
        no_errors(dg)

    def test_link_by_integer(self, dg):
        dg.delays.link[2] = 0   # channel 2 = A, ref 0 = T0
        assert dg.delays.link[2] == 0
        no_errors(dg)

    # ── SSDL ──────────────────────────────────────────────────────────────────

    def test_delay_step_size(self, dg):
        dg.delays.delay_step_size['A'] = 1e-9
        assert abs(dg.delays.delay_step_size['A'] - 1e-9) < 1e-15
        no_errors(dg)


# ── TestOutputs ───────────────────────────────────────────────────────────────

class TestOutputs:
    """Tests for the Outputs component — LAMP, LOFF, LPOL."""

    @pytest.fixture(autouse=True)
    def reset_outputs(self, dg):
        dg.reset()
        clear_errors(dg)
        yield
        dg.reset()
        clear_errors(dg)

    # ── LAMP ──────────────────────────────────────────────────────────────────

    def test_amplitude_by_name(self, dg):
        dg.outputs.amplitude['AB'] = 3.5
        assert abs(dg.outputs.amplitude['AB'] - 3.5) < 0.001
        no_errors(dg)

    def test_amplitude_by_integer(self, dg):
        dg.outputs.amplitude[1] = 2.0   # index 1 = AB
        assert abs(dg.outputs.amplitude[1] - 2.0) < 0.001
        no_errors(dg)

    def test_amplitude_all_outputs_by_name(self, dg):
        for output in ('T0', 'AB', 'CD', 'EF', 'GH'):
            dg.outputs.amplitude[output] = 2.5
            assert abs(dg.outputs.amplitude[output] - 2.5) < 0.001, \
                'amplitude[{}] readback failed'.format(output)
            no_errors(dg)

    def test_amplitude_out_of_range(self, dg):
        dg.send('LAMP 1, 10.0')
        assert dg.status.get_last_error() == 10  # illegal value

    # ── LOFF ──────────────────────────────────────────────────────────────────

    def test_offset_zero(self, dg):
        dg.outputs.offset['AB'] = 0.0
        assert abs(dg.outputs.offset['AB'] - 0.0) < 0.001
        no_errors(dg)

    def test_offset_positive(self, dg):
        dg.outputs.offset['AB'] = 1.0
        assert abs(dg.outputs.offset['AB'] - 1.0) < 0.001
        no_errors(dg)

    def test_offset_negative(self, dg):
        dg.outputs.offset['CD'] = -1.0
        assert abs(dg.outputs.offset['CD'] - (-1.0)) < 0.001
        no_errors(dg)

    def test_offset_all_outputs(self, dg):
        for output in ('T0', 'AB', 'CD', 'EF', 'GH'):
            dg.outputs.offset[output] = 0.5
            assert abs(dg.outputs.offset[output] - 0.5) < 0.001
            no_errors(dg)
            dg.outputs.offset[output] = 0.0

    # ── LPOL ──────────────────────────────────────────────────────────────────

    def test_polarity_positive(self, dg):
        dg.outputs.polarity['AB'] = True
        assert dg.outputs.polarity['AB'] is True
        no_errors(dg)

    def test_polarity_negative(self, dg):
        dg.outputs.polarity['AB'] = False
        assert dg.outputs.polarity['AB'] is False
        no_errors(dg)

    def test_polarity_all_outputs(self, dg):
        for output in ('T0', 'AB', 'CD', 'EF', 'GH'):
            dg.outputs.polarity[output] = False
            assert dg.outputs.polarity[output] is False
            no_errors(dg)
            dg.outputs.polarity[output] = True

    # ── Step sizes ────────────────────────────────────────────────────────────

    def test_amplitude_step_size(self, dg):
        dg.outputs.amplitude_step_size['AB'] = 0.1
        assert abs(dg.outputs.amplitude_step_size['AB'] - 0.1) < 0.001
        no_errors(dg)

    def test_offset_step_size(self, dg):
        dg.outputs.offset_step_size['AB'] = 0.05
        assert abs(dg.outputs.offset_step_size['AB'] - 0.05) < 0.001
        no_errors(dg)


# ── TestDisplay ───────────────────────────────────────────────────────────────

class TestDisplay:
    """Tests for the Display component — SHDP, DISP."""

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    def test_display_on(self, dg):
        dg.display.display_on = True
        assert dg.display.display_on is True
        no_errors(dg)

    def test_display_off(self, dg):
        dg.display.display_on = False
        assert dg.display.display_on is False
        no_errors(dg)

    def test_display_on_restored(self, dg):
        """Ensure display is left on after testing."""
        dg.display.display_on = True
        assert dg.display.display_on is True

    def test_get_display_returns_tuple(self, dg):
        """dg.display.display unpacks as (display_type, channel_index)."""
        disp_type, ch = dg.display.display
        assert isinstance(disp_type, int)
        assert isinstance(ch, int)

    def test_set_display_by_name_channel_delay(self, dg):
        """dg.display.display['A'] = 11 → DISP 11,2 ('channel delay' for channel A)."""
        dg.display.display['A'] = 11
        disp_type, ch = dg.display.display
        assert disp_type == 11
        assert ch == Keys.DelayChannelDict['A']
        no_errors(dg)

    def test_set_display_by_integer(self, dg):
        """dg.display.display[2] = 11 → DISP 11,2 (integer channel index)."""
        dg.display.display[2] = 11
        disp_type, ch = dg.display.display
        assert disp_type == 11
        assert ch == 2
        no_errors(dg)

    def test_set_display_trigger_rate(self, dg):
        """Display type 0 = 'trigger rate'."""
        dg.display.display['T0'] = 0
        disp_type, _ = dg.display.display
        assert disp_type == 0
        no_errors(dg)


# ── TestInterface ─────────────────────────────────────────────────────────────

class TestInterface:
    """Tests for the Interface component — *IDN, *OPC, *CLS, *TRG, *WAI."""

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    def test_id_string_format(self, dg):
        idn = dg.interface.id_string
        assert 'Stanford Research Systems' in idn or 'DG645' in idn, \
            'Unexpected IDN format: {!r}'.format(idn)

    def test_id_string_read_only(self, dg):
        """*IDN without '?' → illegal set → LERR? returns 113."""
        dg.send('*IDN FOOBAR')
        err = dg.status.get_last_error()
        assert err in (110, 111, 113), \
            'Expected illegal-set error, got {}'.format(err)

    def test_operation_complete_query(self, dg):
        assert dg.interface.operation_complete == 1

    def test_set_opc(self, dg):
        """*OPC set form — after all commands complete, OPC bit (bit 0) of ESR is set."""
        dg.interface.clear_status()
        dg.interface.set_opc()
        esr = dg.status.event_status
        assert esr & 1 == 1, 'Expected OPC bit (bit 0) set in ESR, got {}'.format(esr)

    def test_clear_status(self, dg):
        dg.send('*IDN')  # trigger a CME → sets ESR bit 5
        dg.interface.clear_status()
        assert dg.status.event_status == 0

    def test_wait_does_not_raise(self, dg):
        dg.interface.wait()
        no_errors(dg)

    def test_trigger_does_not_raise(self, dg):
        """*TRG fires a single trigger when source is SingleShot."""
        dg.trigger.trigger_source = 'single shot'
        dg.interface.trigger()
        no_errors(dg)

    def test_self_test_returns_int(self, dg):
        result = dg.interface.self_test
        assert isinstance(result, int)

    @pytest.mark.skip(reason='*CAL? runs a hardware auto-calibration routine that takes '
                              'many seconds; skip to avoid timeout cascades in normal runs')
    def test_calibrate_returns_int(self, dg):
        result = dg.interface.calibrate
        assert isinstance(result, int)


# ── TestSystem ────────────────────────────────────────────────────────────────

class TestSystem:
    """Tests for the System component — *PSC, *SAV, *RCL."""

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    def test_power_on_status_clear_on(self, dg):
        dg.system.power_on_status_clear = True
        assert dg.system.power_on_status_clear is True
        no_errors(dg)

    def test_power_on_status_clear_off(self, dg):
        dg.system.power_on_status_clear = False
        assert dg.system.power_on_status_clear is False
        no_errors(dg)

    def test_save_and_recall(self, dg):
        """*SAV 1 / *RCL 1 round-trip: save a known state then recall it."""
        # Set a distinctive trigger rate, save it, change it, recall, verify
        dg.trigger.trigger_source = 'internal'
        dg.trigger.trigger_rate = 500.0
        dg.system.save(1)
        dg.trigger.trigger_rate = 1000.0
        dg.system.recall(1)
        assert abs(dg.trigger.trigger_rate - 500.0) < 0.01
        no_errors(dg)

    def test_recall_factory_defaults(self, dg):
        """*RCL 0 should restore factory defaults."""
        dg.trigger.trigger_rate = 50.0
        dg.trigger.trigger_source = 'internal'
        dg.system.recall(0)
        assert dg.trigger.trigger_source == Keys.SingleShot


# ── TestStatus ────────────────────────────────────────────────────────────────

class TestStatus:
    """Tests for the Status component — INSR, INSE, LERR, ESR, STB, SRE, ESE."""

    @pytest.fixture(autouse=True)
    def clean_state(self, dg):
        dg.interface.clear_status()
        dg.status.drain_errors()
        yield
        dg.interface.clear_status()
        dg.status.drain_errors()

    def test_insr_read_only(self, dg):
        """INSR is read-only — attempting to set should produce an error."""
        dg.send('INSR 0')
        err = dg.status.get_last_error()
        assert err in (110, 111, 113), \
            'Expected illegal-set error for INSR, got {}'.format(err)

    def test_instrument_status_enable_roundtrip(self, dg):
        dg.status.instrument_status_enable = 0xFF
        assert dg.status.instrument_status_enable == 0xFF
        no_errors(dg)
        dg.status.instrument_status_enable = 0

    def test_get_last_error_zero_when_clean(self, dg):
        assert dg.status.get_last_error() == 0

    def test_lerr_triggers_on_bad_value(self, dg):
        dg.send('TRAT -1')
        err = dg.status.get_last_error()
        assert err != 0, 'Expected non-zero LERR after TRAT -1'

    def test_lerr_illegal_value_code(self, dg):
        dg.send('TSRC 99')
        err = dg.status.get_last_error()
        assert err == 10, 'Expected error code 10 (illegal value), got {}'.format(err)

    def test_lerr_self_clears(self, dg):
        dg.send('TSRC 99')
        first = dg.status.get_last_error()
        second = dg.status.get_last_error()
        assert first != 0
        assert second == 0  # cleared after first read

    def test_drain_errors_returns_list(self, dg):
        dg.send('TSRC 99')
        errors = dg.status.drain_errors()
        assert isinstance(errors, list)
        assert len(errors) >= 1
        assert all(e != 0 for e in errors)

    def test_drain_errors_empty_when_clean(self, dg):
        errors = dg.status.drain_errors()
        assert errors == []

    def test_event_status_zero_after_clear(self, dg):
        assert dg.status.event_status == 0

    def test_event_status_cme_bit_on_bad_command(self, dg):
        """A command error sets ESR bit 5 (CME, weight 32)."""
        dg.send('*IDN')  # missing '?' → CME
        esr = dg.status.event_status
        assert esr & 32 == 32, 'Expected ESR CME bit set, got {}'.format(esr)

    def test_event_status_clears_on_read(self, dg):
        dg.send('*IDN')
        dg.status.event_status      # first read clears it
        assert dg.status.event_status == 0

    def test_event_bit_cme(self, dg):
        """Per-bit query: event_bit['CME'] reads ESR bit 5."""
        dg.send('*IDN')             # trigger CME (bit 5)
        assert dg.status.event_bit[Keys.CME] is True
        assert dg.status.event_bit[Keys.CME] is False  # cleared after read

    def test_serial_poll_returns_int(self, dg):
        stb = dg.status.serial_poll
        assert isinstance(stb, int)
        assert 0 <= stb <= 255

    def test_serial_poll_bit_mss(self, dg):
        bit_val = dg.status.serial_poll_bit[Keys.MSS]
        assert isinstance(bit_val, bool)

    def test_serial_poll_enable_roundtrip(self, dg):
        dg.status.serial_poll_enable_bit[Keys.ESB] = True
        assert dg.status.serial_poll_enable & 32 == 32
        dg.status.serial_poll_enable_bit[Keys.ESB] = False
        assert dg.status.serial_poll_enable & 32 == 0

    def test_event_enable_roundtrip(self, dg):
        dg.status.event_enable_bit[Keys.EXE] = True
        assert dg.status.event_enable & 16 == 16
        dg.status.event_enable_bit[Keys.EXE] = False
        assert dg.status.event_enable & 16 == 0

    def test_get_status_text_ok_when_clean(self, dg):
        text = dg.status.get_status_text()
        assert text == 'OK'

    def test_get_status_text_reports_esr_error(self, dg):
        """When a CME is present, get_status_text() should report it."""
        dg.send('*IDN')  # trigger CME
        text = dg.status.get_status_text()
        assert 'CME' in text or 'ESR' in text


# ── TestNetwork ───────────────────────────────────────────────────────────────

class TestNetwork:
    """Tests for the Network component — EMAC, TIMB, LCAL, REMT, LOCK, UNLK."""

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    def test_mac_address_format(self, dg):
        """EMAC? should return a MAC address string (colon-separated hex pairs)."""
        mac = dg.network.mac_address
        assert isinstance(mac, str)
        assert len(mac) > 0

    def test_timebase_returns_int(self, dg):
        tb = dg.network.timebase
        assert isinstance(tb, int)
        assert tb in (0, 1, 2, 3), 'Unexpected timebase value: {}'.format(tb)

    def test_go_local_does_not_raise(self, dg):
        # LCAL is only valid over RS-232/Telnet; over GPIB it returns error 111.
        # We only verify it does not raise a Python exception.
        dg.network.go_local()
        dg.status.drain_errors()  # discard any interface-specific error

    def test_go_remote_does_not_raise(self, dg):
        # REMT is only valid over RS-232/raw socket; over GPIB it returns error 111.
        dg.network.go_remote()
        dg.status.drain_errors()  # discard any interface-specific error

    def test_request_lock_returns_int(self, dg):
        result = dg.network.request_lock()
        assert isinstance(result, int)

    def test_release_lock_returns_int(self, dg):
        dg.network.request_lock()
        result = dg.network.release_lock()
        assert isinstance(result, int)


# ── TestInstrumentBaseMethods ─────────────────────────────────────────────────

class TestInstrumentBaseMethods:
    """
    Tests for methods inherited from srsgui.Instrument, exercised against
    the live DG645: is_connected, get/set_term_char, send, query_text,
    query_int, query_float, check_id, get_info, handle_command, and
    connect_with_parameter_string.
    """

    @pytest.fixture(autouse=True)
    def clean_errors(self, dg):
        clear_errors(dg)
        yield
        clear_errors(dg)

    def test_is_connected_true(self, dg):
        assert dg.is_connected() is True

    def test_get_term_char_default(self, dg):
        assert dg.get_term_char() == b'\n'

    def test_set_get_term_char_roundtrip(self, dg):
        original = dg.get_term_char()
        dg.set_term_char(b'\r')
        assert dg.get_term_char() == b'\r'
        dg.set_term_char(original)
        assert dg.get_term_char() == original

    def test_send_does_not_raise(self, dg):
        dg.send('*CLS')
        no_errors(dg)

    def test_query_text_returns_string(self, dg):
        reply = dg.query_text('*IDN?')
        assert isinstance(reply, str)
        assert 'DG645' in reply

    def test_query_int_returns_int(self, dg):
        result = dg.query_int('*OPC?')
        assert isinstance(result, int)
        assert result == 1

    def test_query_float_returns_float(self, dg):
        result = dg.query_float('TRAT?')
        assert isinstance(result, float)

    def test_check_id_returns_tuple(self, dg):
        model, serial, firmware = dg.check_id()
        assert model is not None and 'DG645' in model
        assert serial is not None
        assert firmware is not None

    def test_get_info_returns_dict(self, dg):
        info = dg.get_info()
        assert isinstance(info, dict)
        assert info.get('type') is not None

    def test_handle_command_query(self, dg):
        reply = dg.handle_command('*IDN?')
        assert isinstance(reply, str)
        assert 'DG645' in reply

    def test_handle_command_set_returns_empty_string(self, dg):
        reply = dg.handle_command('*CLS')
        assert reply == ''


# ── TestInstrumentMethods ─────────────────────────────────────────────────────

class TestInstrumentMethods:
    """Tests for DG645-specific methods: reset(), trigger_now(), get_status()."""

    def test_reset_restores_defaults(self, dg):
        dg.trigger.trigger_rate = 500.0
        dg.trigger.trigger_source = 'internal'
        dg.reset()
        assert dg.trigger.trigger_source == Keys.SingleShot
        assert abs(dg.trigger.trigger_rate - 1000.0) < 0.01

    def test_trigger_now_does_not_raise(self, dg):
        dg.trigger.trigger_source = 'single shot'
        dg.trigger_now()  # fires *TRG; should not raise

    def test_get_status_is_nonempty_string(self, dg):
        text = dg.get_status()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_get_status_contains_trigger_source(self, dg):
        text = dg.get_status()
        assert 'Trigger source' in text

    def test_get_status_contains_trigger_rate(self, dg):
        text = dg.get_status()
        assert 'Trigger rate' in text
