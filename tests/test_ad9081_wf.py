import adidt
import numpy as np

from pprint import pprint
import pytest
import os
import shutil
import time
import iio
from adi import jesd
from tqdm import tqdm

import nebula
import logging

logging.getLogger().setLevel(logging.ERROR)

from tests.common import create_jif_configuration, build_devicetree
from tests.ad9081_gen import ad9081_get_rx_decimations

ip = os.environ.get("TARGET_IP") if "TARGET_IP" in os.environ else "analog-2.local"
vcxo = os.environ.get("TARGET_VCXO") if "TARGET_VCXO" in os.environ else 122.88e6


def gen_configs_from_rates(rates):
    return [
        dict(
            DAC_freq=int(rate),
            ADC_freq=int(rate) // 1,
            fddc=4,
            cddc=4,
            fduc=4,
            cduc=4,
        )
        for rate in rates
    ]


@pytest.mark.parametrize(
    "param_set",
    [
        dict(
            DAC_freq=int(12e9),
            ADC_freq=int(12e9) // 3,
            fddc=4,
            cddc=4,
            fduc=6,
            cduc=8,
        ),
        dict(
            DAC_freq=int(4e9),
            ADC_freq=int(4e9) // 1,
            fddc=4,
            cddc=4,
            fduc=4,
            cduc=4,
        ),
        dict(  # Failing case
            DAC_freq=int(6e9),
            ADC_freq=int(6e9) // 3,
            fddc=4,
            cddc=2,
            fduc=4,
            cduc=4,
        ),
    ]
    # + gen_configs_from_rates([2e9, 2.5e9, 3e9, 3.5e9])
    + ad9081_get_rx_decimations(vcxo, "10.0", "9", "jesd204b", "jesd204b"),
)
def test_ad9081_stock_hdl(logger, build_kernel, param_set):

    logger.saved["param_set"] = param_set
    logger.saved["status"] = "skipped"

    ############################################################################
    # Generate JIF configuration
    cfg, sys = create_jif_configuration(param_set, vcxo)
    logger.saved["cfg"] = cfg
    logger.saved["status"] = "failed"

    ############################################################################
    # Generate DT fragment
    fmc = adidt.ad9081_fmc()
    clock, adc, dac = fmc.map_clocks_to_board_layout(cfg)
    dts_filename = fmc.gen_dt(clock=clock, adc=adc, dac=dac)

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
    # Verify board working
    print("Verifying board working")

    ctx = iio.Context(f"ip:{ip}")
    required_devices = ["axi-ad9081-rx-hpc", "axi-ad9081-tx-hpc", "hmc7044"]
    found_devices = [dev.name for dev in ctx.devices]
    logger.saved["found_devices"] = found_devices
    print("Found_devices:", found_devices)
    for dev in required_devices:
        assert dev in found_devices, f"{dev} not found"

    dev = jesd(address=ip)
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
            assert lr == sys.converter.adc.bit_clock
        else:
            assert lr == sys.converter.dac.bit_clock
    logger.saved["status"] = "passed"
