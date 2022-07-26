import logging
import os

import adidt
import iio
import pytest
from adi import jesd

import nebula

logging.getLogger().setLevel(logging.ERROR)

from tests.common import build_devicetree, create_jif_configuration_ad9680

ip = os.environ.get("TARGET_IP") if "TARGET_IP" in os.environ else "192.168.86.243"
vcxo = int(os.environ.get("TARGET_VCXO")) if "TARGET_VCXO" in os.environ else 125e6
tx_jesd_mode = (
    os.environ.get("TARGET_TX_JESD_MODE")
    if "TARGET_TX_JESD_MODE" in os.environ
    else "4"
)
rx_jesd_mode = (
    os.environ.get("TARGET_RX_JESD_MODE")
    if "TARGET_TX_JESD_MODE" in os.environ
    else str(0x88)
)

arch = os.environ.get("ARCH") if "ARCH" in os.environ else "arm64"

# The purpose of this test is to permute the interpolators+decimators and DAC+ADC rates without changing the
# framer rates to verify changing upstream configurations do not effect downstream


@pytest.mark.parametrize(
    "param_set",
    []
    + [
        dict(ADC_freq=int(1e9), ddc=1, DAC_freq=int(1e9), duc=1),  # Case 0
        dict(
            ADC_freq=int(1e9 * 3 / 4), ddc=1, DAC_freq=int(1e9 * 3 / 4), duc=1
        ),  # Case 1
        dict(ADC_freq=int(1e9 // 2), ddc=1, DAC_freq=int(1e9 // 2), duc=1),  # Case 2
        dict(ADC_freq=int(375e6), ddc=1, DAC_freq=int(250e6), duc=1),  # Case 3
    ]
    + [
        dict(ADC_freq=int(rate * 100e6), ddc=1, DAC_freq=int(rate * 100e6), duc=1)
        for rate in range(1, 10)
    ]
    + [
        dict(ADC_freq=int(1e9), ddc=1, DAC_freq=int(1e9), duc=1, lmfc_divisor=div)
        for div in range(1, 40)
    ],
)
def test_ad9680_stock_hdl(logger, build_kernel, param_set):

    logger.saved["param_set"] = param_set
    logger.saved["status"] = "skipped"
    if "not_possible" in param_set:
        pytest.skip(f"Rate not possible: {param_set['sample_rate']}")

    ############################################################################
    # Generate JIF configuration
    if "lmfc_divisor" in param_set:
        lmfc_divisor = param_set["lmfc_divisor"]
    else:
        lmfc_divisor = None
    cfg, sys = create_jif_configuration_ad9680(
        param_set, vcxo, rx_jesd_mode, tx_jesd_mode, lmfc_divisor
    )
    logger.saved["cfg"] = cfg
    logger.saved["status"] = "failed"

    ############################################################################
    # Generate DT fragment
    fmc = adidt.daq2()
    clock, adc, dac, fpga = fmc.map_clocks_to_board_layout(cfg)
    dts_filename = fmc.gen_dt(clock=clock, adc=adc, dac=dac, fpga=fpga, arch=arch)

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

    d = adidt.dt(dt_source="remote_sd", ip=ip, arch=arch)
    d.copy_local_files_to_remote_sd_card(file_list, show=show)

    if arch == "arm64":
        board_name = "zynqmp-zcu102-rev10-fmcdaq2"
    else:
        board_name = "zynq-zc706-adv7511-fmcdaq2"

    nb = nebula.manager(
        monitor_type="uart",
        # configfilename="daq2.yaml",
        configfilename="/etc/default/nebula",
        board_name=board_name,
        extras=None,
    )

    print("Starting board reboot")
    d._runr("reboot", warn=True)

    print("Waiting for board to boot")
    nb.wait_for_boot()

    ############################################################################
    # Verify board working
    print("Verifying board working")

    ctx = iio.Context(f"ip:{ip}")
    required_devices = ["axi-ad9680-hpc", "axi-ad9144-hpc", "ad9523-1"]
    found_devices = [dev.name for dev in ctx.devices]
    logger.saved["found_devices"] = found_devices
    print("Found_devices:", found_devices)
    for dev in required_devices:
        assert dev in found_devices, f"{dev} not found"

    # Read registers
    # dev = ctx.find_device("axi-ad9081-rx-hpc")
    # reg = dev.reg_read(0x0728)
    # logger.saved["RX_0x0728"] = reg
    # reg = dev.reg_read(0x00CA)
    # logger.saved["RX_0x00CA"] = reg
    # reg = dev.reg_read(0x09)
    # logger.saved["TX_0x09"] = reg

    dev = jesd(address=ip)
    # Get dmesg
    dmesg = dev.fs._run("dmesg")
    logger.saved["dmesg"] = dmesg[0]

    # Log expected device clock based on JIF config (not measured)
    logger.saved["RX_Expected_Device_Clock"] = param_set["ADC_freq"] / param_set["ddc"]
    logger.saved["TX_Expected_Device_Clock"] = param_set["DAC_freq"] / param_set["duc"]

    # Check JESD lanes
    jdevices_statuses = dev.get_all_statuses()
    logger.saved["jdevices_statuses"] = jdevices_statuses
    for dev in jdevices_statuses:
        print("Checking", dev)
        print(jdevices_statuses[dev])
        print(
            "Link info:",
            jdevices_statuses[dev]["enabled"],
            jdevices_statuses[dev]["Link status"],
        )
        assert jdevices_statuses[dev]["enabled"] == "enabled"
        assert jdevices_statuses[dev]["Link status"] == "DATA"
        lr = float(jdevices_statuses[dev]["Lane rate"].split(" ")[0]) * 1e6
        if "rx" in dev:
            assert lr == sys.converter[0].bit_clock
        else:
            assert lr == sys.converter[1].bit_clock
    logger.saved["status"] = "passed"
