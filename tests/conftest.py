##!
##! Copyright(c) 2026 Stanford Research Systems, All rights reserved
##! Subject to the MIT License
##!

import pytest
from srsinst.dg645 import DG645


def pytest_addoption(parser):
    parser.addoption(
        "--ip",
        default=None,
        help="IP address for DG645 VXI-11 or TCP/IP connection (e.g. 192.168.0.10)",
    )
    parser.addoption(
        "--port",
        default=None,
        help="COM port for DG645 RS-232 connection (e.g. COM3)",
    )
    parser.addoption(
        "--resource",
        default=None,
        help="VISA resource string for DG645 GPIB/USB connection (e.g. GPIB0::15::INSTR)",
    )


@pytest.fixture(scope="session")
def dg(request):
    ip       = request.config.getoption("--ip")
    port     = request.config.getoption("--port")
    resource = request.config.getoption("--resource")

    print("\n" + "=" * 60)
    print("DG645 Integration Test Suite")
    print("=" * 60)

    inst = DG645()

    if resource is not None:
        interface = 'visa'
        param = resource
    elif ip is not None:
        # Prefer VXI-11 when an IP address is supplied
        interface = 'vxi11'
        param = ip
    elif port is not None:
        interface = 'serial'
        param = port
    else:
        print("Please connect the PC to the DG645 (VXI-11, TCP/IP, VISA/GPIB, or RS-232).")
        choice = input(
            "Enter connection info:\n"
            "  'ip <address>'         for VXI-11/TCP\n"
            "  'visa <resource>'      for GPIB/USB (e.g. visa GPIB0::15::INSTR)\n"
            "  'serial <port>'        for RS-232\n"
            "> "
        ).strip().split(None, 1)
        interface = choice[0].lower()
        param = choice[1] if len(choice) > 1 else ''

    baud = 9600  # only used for serial

    while True:
        try:
            if interface == 'serial':
                inst.connect(interface, param, baud)
            else:
                inst.connect(interface, param)
            inst.check_id()
            break
        except Exception as exc:
            try:
                inst.disconnect()
            except Exception:
                pass
            print('\nConnection failed: {}'.format(exc))
            entry = input(
                'Please ensure the DG645 is connected and powered on.\n'
                'Press Enter to retry, or enter a new address/resource/port: '
            ).strip()
            if entry:
                param = entry

    # Clear all error registers before the test run
    inst.interface.clear_status()
    inst.status.drain_errors()

    yield inst

    # Teardown: restore defaults and release the connection
    try:
        inst.reset()
    finally:
        inst.disconnect()
