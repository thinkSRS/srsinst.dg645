##!
##! Copyright(c) 2026 Stanford Research Systems, All rights reserved
##! Subject to the MIT License
##!


class Keys:
    """String constants for DG645 token-type commands and index dictionaries."""

    # --- Trigger source (TSRC) ---
    Internal        = 'internal'
    ExtRising       = 'ext rising'
    ExtFalling      = 'ext falling'
    SsExtRising     = 'ss ext rising'
    SsExtFalling    = 'ss ext falling'
    SingleShot      = 'single shot'
    Line            = 'line'

    # --- Inhibit mode (INHB) ---
    InhibitOff      = 'off'
    InhibitTriggers = 'triggers'
    InhibitAB       = 'AB'
    InhibitABCD     = 'AB and CD'
    InhibitABCDEF   = 'AB, CD, and EF'
    InhibitAll      = 'AB, CD, EF, and GH'

    # --- Burst T0 config (BURT) ---
    T0OnAll   = 'T0 on all'
    T0OnFirst = 'T0 on first'

    # --- Timebase source (TIMB) ---
    InternalTimebase = 'internal'
    OcxoTimebase     = 'OCXO'
    RubidiumTimebase = 'rubidium'
    ExternalTimebase = 'external'

    # --- Delay channel names (subscript keys for dg.delays.*['A'] etc.) ---
    T0 = 'T0'
    T1 = 'T1'
    A  = 'A'
    B  = 'B'
    C  = 'C'
    D  = 'D'
    E  = 'E'
    F  = 'F'
    G  = 'G'
    H  = 'H'

    # --- Output BNC names (subscript keys for dg.outputs.*['AB'] etc.) ---
    AB = 'AB'
    CD = 'CD'
    EF = 'EF'
    GH = 'GH'
    # T0 already defined above (shared string value 'T0')

    # --- Index dictionaries ---
    # Channel index map: channel name → integer index sent to instrument
    DelayChannelDict = {
        'T0': 0, 'T1': 1,
        'A': 2, 'B': 3, 'C': 4, 'D': 5,
        'E': 6, 'F': 7, 'G': 8, 'H': 9,
    }

    # Output BNC index map: output name → integer index sent to instrument
    OutputBNCDict = {
        'T0': 0, 'AB': 1, 'CD': 2, 'EF': 3, 'GH': 4,
    }

    # --- ESR bit names ---
    OPC = 'OPC'
    QYE = 'QYE'
    DDE = 'DDE'
    EXE = 'EXE'
    CME = 'CME'
    PON = 'PON'

    # --- STB bit names ---
    INSB     = 'INSB'
    BUSY     = 'BUSY'
    BURST_BIT = 'BURST'   # renamed to avoid shadowing the Burst component attribute
    MAV      = 'MAV'
    ESB      = 'ESB'
    MSS      = 'MSS'

    # --- INSR (Instrument Status Register) bit names ---
    TRIG         = 'TRIG'
    RATE         = 'RATE'
    END_OF_DELAY = 'END_OF_DELAY'
    END_OF_BURST = 'END_OF_BURST'
    INHIBIT      = 'INHIBIT'
    ABORT_DELAY  = 'ABORT_DELAY'
    PLL_UNLOCK   = 'PLL_UNLOCK'
    RB_UNLOCK    = 'RB_UNLOCK'
