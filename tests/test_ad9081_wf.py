import logging
import os

import adidt
import iio
import pytest
from adi import jesd

import nebula

logging.getLogger().setLevel(logging.ERROR)

from tests.ad9081_gen import ad9081_get_rx_decimations, get_rates_from_sample_rate
from tests.common import build_devicetree, create_jif_configuration

ip = os.environ.get("TARGET_IP") if "TARGET_IP" in os.environ else "analog-2.local"
vcxo = int(os.environ.get("TARGET_VCXO")) if "TARGET_VCXO" in os.environ else 122.88e6
tx_jesd_mode = (
    os.environ.get("TARGET_TX_JESD_MODE")
    if "TARGET_TX_JESD_MODE" in os.environ
    else "9"
)
rx_jesd_mode = (
    os.environ.get("TARGET_RX_JESD_MODE")
    if "TARGET_TX_JESD_MODE" in os.environ
    else "10.0"
)

# The purpose of this test is to permute the interpolators+decimators and DAC+ADC rates without changing the
# framer rates to verify changing upstream configurations do not effect downstream
#
# Limitations
#
# ADC min/max: 1.45e9/4e9
# DAC min/max: 2.9e9/12e9

# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set0]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set8]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set12]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set52]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set56]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set60]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set61]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set64]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set65]
# FAILED tests/test_ad9081_wf.py::test_ad9081_stock_hdl[build_kernel0-param_set70]

indexes = [0, 8, 12, 52, 56, 60, 61, 64, 65, 70]
rates = [*range(250, 321, 1)]
rates = [rates[index] for index in indexes]


@pytest.mark.parametrize(
    "param_set",
    []
    + [
        get_rates_from_sample_rate(rate * 1e6, vcxo, rx_jesd_mode, tx_jesd_mode)
        for rate in rates
    ]
    + [
        # dict(ADC_freq=3000000000, cddc=4, fddc=2, DAC_freq=3000000000, cduc=4, fduc=4), # Case 0
        # dict(ADC_freq=3000000000, cddc=4, fddc=4, DAC_freq=3000000000, cduc=4, fduc=4), # Case 1
        # dict(ADC_freq=3000000000, cddc=4, fddc=4, DAC_freq=6000000000, cduc=4, fduc=4), # Case 2
        # dict(ADC_freq=4000000000, cddc=4, fddc=4, DAC_freq=4000000000, cduc=4, fduc=4), # Case 3
        # dict(ADC_freq=4000000000, cddc=4, fddc=8, DAC_freq=4000000000, cduc=4, fduc=4), # Case 4
        #
        # dict(ADC_freq=4000000000, cddc=4, fddc=4, DAC_freq=8000000000, cduc=4, fduc=8), # DRIVER FAILS TO FIND PLL
        #
        # dict(ADC_freq=3200000000, cddc=4, fddc=4, DAC_freq=6400000000, cduc=4, fduc=8), # Working 200
        # dict(ADC_freq=3200000000, cddc=4, fddc=4, DAC_freq=3200000000, cduc=4, fduc=4), # Working 200
        # dict(ADC_freq=4000000000, cddc=4, fddc=4, DAC_freq=12000000000, cduc=6, fduc=8),# Working 250
        # dict(ADC_freq=2000000000, cddc=4, fddc=2, DAC_freq=6000000000, cduc=6, fduc=4), # Working 250
        # dict(ADC_freq=2200000000, cddc=4, fddc=2, DAC_freq=8800000000, cduc=4, fduc=8), # Working 275
        # dict(ADC_freq=2200000000, cddc=4, fddc=2, DAC_freq=4400000000, cduc=4, fduc=4), # Working 275
        # dict(ADC_freq=2240000000, cddc=4, fddc=2, DAC_freq=4480000000, cduc=4, fduc=4), # Working 280
        # dict(ADC_freq=2400000000, cddc=4, fddc=2, DAC_freq=9600000000, cduc=4, fduc=8), # Failing 300
        # dict(ADC_freq=2400000000, cddc=4, fddc=2, DAC_freq=4800000000, cduc=4, fduc=4), # Failing 300
        # dict(ADC_freq=3000000000, cddc=4, fddc=2, DAC_freq=6000000000, cduc=4, fduc=4), # Failing 375
        # dict(ADC_freq=3000000000, cddc=4, fddc=2, DAC_freq=3000000000, cduc=4, fduc=2), # Failing 375
        # dict(ADC_freq=3200000000, cddc=4, fddc=2, DAC_freq=6400000000, cduc=4, fduc=4), # Failing 400
        # dict(ADC_freq=3200000000, cddc=4, fddc=2, DAC_freq=3200000000, cduc=4, fduc=2), # Failing 400
    ]
    # + ad9081_get_rx_decimations(vcxo, "10.0", "9", "jesd204b", "jesd204b"),
)
def test_ad9081_stock_hdl(logger, build_kernel, param_set):

    logger.saved["param_set"] = param_set
    logger.saved["status"] = "skipped"
    if "not_possible" in param_set:
        pytest.skip(f"Rate not possible: {param_set['sample_rate']}")

    ############################################################################
    # Generate JIF configuration
    cfg, sys = create_jif_configuration(param_set, vcxo, rx_jesd_mode, tx_jesd_mode)
    # return
    logger.saved["cfg"] = cfg
    logger.saved["status"] = "failed"

    ############################################################################
    # Generate DT fragment
    fmc = adidt.ad9081_fmc()
    clock, adc, dac, fpga = fmc.map_clocks_to_board_layout(cfg)
    # dts_filename = "ad9081_fmc_zcu102.dts"
    dts_filename = fmc.gen_dt(clock=clock, adc=adc, dac=dac, fpga=fpga)

    ############################################################################
    # Build new devicetree
    print("Building new devicetree")
    dtb_filename = build_devicetree(dts_filename)

    ############################################################################
    # Update on board
    # Reboot and wait for board to come back up
    print("Updating devicetree on board")
    file_list = [dtb_filename]
    show = True

    d = adidt.dt(dt_source="remote_sd", ip=ip, arch="arm64")
    d.copy_local_files_to_remote_sd_card(file_list, show=show)

    nb = nebula.manager(
        monitor_type="uart",
        configfilename="ad9081.yaml",
        board_name="zynqmp-zcu102-rev10-ad9081",
        extras=None,
    )

    print("Starting board reboot")
    d._runr("reboot", warn=True)

    print("Waiting for board to boot")
    nb.wait_for_boot()

    ############################################################################
    # Get dmesg
    dev = jesd(address=ip)
    dmesg = dev.fs._run("dmesg")
    logger.saved["dmesg"] = dmesg[0]

    ############################################################################
    # Verify board working
    print("Verifying board working")

    ctx = iio.Context(f"ip:{ip}")
    required_devices = ["axi-ad9081-rx-hpc", "axi-ad9081-tx-hpc", "hmc7044"]
    found_devices = [dev.name for dev in ctx.devices]
    logger.saved["found_devices"] = found_devices
    print("Found_devices:", found_devices)
    found_devs = True
    e1_msg = "" 
    for dev in required_devices:
        c = dev in found_devices
        found_devs = c & found_devs
        if not c:
            print(f"Device {dev} not found")
            e1_msg = f"Device {dev} not found"

    # Read registers
    dev = jesd(address=ip)
    dev = ctx.find_device("axi-ad9081-rx-hpc")
    reg = dev.reg_read(0x0728)
    logger.saved["RX_0x0728"] = reg
    reg = dev.reg_read(0x00CA)
    logger.saved["RX_0x00CA"] = reg
    reg = dev.reg_read(0x09)
    logger.saved["TX_0x09"] = reg

    # Log expected device clock based on JIF config (not measured)
    logger.saved["RX_Expected_Device_Clock"] = (
        param_set["ADC_freq"] / param_set["cddc"] / param_set["fddc"]
    )
    logger.saved["TX_Expected_Device_Clock"] = (
        param_set["DAC_freq"] / param_set["cduc"] / param_set["fduc"]
    )

    # Check JESD lanes
    jdevices_statuses = dev.get_all_statuses()
    logger.saved["jdevices_statuses"] = jdevices_statuses

    enables_check = True
    link_data_check = True
    adc_bit_clock_check = True
    dac_bit_clock_check = True

    for dev in jdevices_statuses:
        print("Checking", dev)
        print(jdevices_statuses[dev])
        print(
            "Link info:",
            jdevices_statuses[dev]["enabled"],
            jdevices_statuses[dev]["Link status"],
        )
        enable = jdevices_statuses[dev]["enabled"] == "enabled"
        enables_check = enables_check & enable
        if not enable:
            print(f"Device {dev} not enabled")
            e2_msg = f"Device {dev} not enabled"

        data = jdevices_statuses[dev]["Link status"] == "DATA"
        link_data_check = link_data_check & data
        if not data:
            print(f"Device {dev} not in DATA")
            e3_msg = f"Device {dev} not in DATA"

        lr = float(jdevices_statuses[dev]["Lane rate"].split(" ")[0]) * 1e6
        if "rx" in dev:
            lane_rate_c = lr == sys.converter.adc.bit_clock
            adc_bit_clock_check = adc_bit_clock_check & lane_rate_c
            if not lane_rate_c:
                print(f"Device {dev} has wrong bit clock")
                e4_msg = f"Device {dev} has wrong bit clock"
        else:
            lane_rate_c = lr == sys.converter.dac.bit_clock
            dac_bit_clock_check = dac_bit_clock_check & lane_rate_c
            if not lane_rate_c:
                print(f"Device {dev} has wrong bit clock")
                e5_msg = f"Device {dev} has wrong bit clock"
    logger.saved["status"] = "passed"

    if not found_devs:
        pytest.fail(e1_msg)
    if not enables_check:
        pytest.fail(e2_msg)
    if not link_data_check:
        pytest.fail(e3_msg)
    if not adc_bit_clock_check:
        pytest.fail(e4_msg)
    if not dac_bit_clock_check:
        pytest.fail(e5_msg)
