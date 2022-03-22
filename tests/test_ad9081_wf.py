import adidt
import adijif
import numpy as np
from pprint import pprint
import pytest
import os
import shutil
import time
import iio
from adi import jesd
from tqdm import tqdm

ip = "analog-2.local"
# vcxo = 100e6
vcxo = 122.88e6


@pytest.fixture(scope="module")
def build_kernel():
    if not os.path.exists("/opt/Xilinx/Vivado/2019.2/settings64.sh"):
        raise Exception("No Vivado settings found")
    if not os.path.isdir("linux"):
        os.system(
            "git clone https://github.com/analogdevicesinc/linux.git --depth=1 -b 2019_R2"
        )
        os.chdir("linux")
        cmd = ". /opt/Xilinx/Vivado/2019.2/settings64.sh ; "
        cmd += "ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- ; "
        os.system(cmd + ". make adi_zynqmp_defconfig")
        os.system(cmd + " make -j5 Image UIMAGE_LOADADDR=0x8000")
        os.chdir("..")


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
    ],
)
def test_ad9081_stock_hdl(build_kernel, param_set):
    ###############################################################################
    # RX
    rx = adijif.ad9081_rx
    params = {"jesd_class": "jesd204b", "M": 8, "L": 4, "S": 1, "Np": 16}
    rx_modes = adijif.utils.get_jesd_mode_from_params(rx, **params)
    print("RX", rx_modes)
    assert len(rx_modes) == 1, f"Expected 1 mode, got {len(rx_modes)}"

    # TX
    tx = adijif.ad9081_tx
    params = {"jesd_class": "jesd204b", "M": 8, "L": 4, "S": 1, "Np": 16}
    tx_modes = adijif.utils.get_jesd_mode_from_params(tx, **params)
    print("TX", tx_modes)
    assert len(tx_modes) == 1, f"Expected 1 mode, got {len(tx_modes)}"

    ###############################################################################
    # Set up JIF solver to generate the clocking details for new sample rate

    DAC_freq = param_set["DAC_freq"]
    ADC_freq = param_set["ADC_freq"]
    fddc = param_set["fddc"]
    cddc = param_set["cddc"]
    fduc = param_set["fduc"]
    cduc = param_set["cduc"]
    tx_sample_rate = DAC_freq // (cduc * fduc)
    rx_sample_rate = ADC_freq // (cddc * fddc)

    sys = adijif.system("ad9081", "hmc7044", "xilinx", vcxo, solver="CPLEX")
    sys.fpga.setup_by_dev_kit_name("zcu102")
    sys.fpga.sys_clk_select = "GTH34_SYSCLK_QPLL0"  # Use faster QPLL
    sys.converter.clocking_option = "integrated_pll"
    sys.fpga.request_fpga_core_clock_ref = True  # force reference to be core clock rate

    sys.converter.dac.set_quick_configuration_mode(tx_modes[0]["mode"], "jesd204b")
    sys.converter.adc.set_quick_configuration_mode(rx_modes[0]["mode"], "jesd204b")

    sys.converter.adc.sample_clock = rx_sample_rate
    sys.converter.dac.sample_clock = tx_sample_rate

    sys.converter.adc.decimation = fddc * cddc
    sys.converter.dac.interpolation = fduc * cduc

    sys.converter.adc.datapath.fddc_decimations = [fddc] * 8
    sys.converter.adc.datapath.cddc_decimations = [cddc] * 4
    sys.converter.adc.datapath.cddc_enabled = [True] * 4
    sys.converter.adc.datapath.fddc_enabled = [True] * 8

    sys.converter.dac.datapath.cduc_interpolation = cduc
    sys.converter.dac.datapath.fduc_interpolation = fduc
    sys.converter.dac.datapath.cduc_enabled = [True] * 4
    sys.converter.dac.datapath.fduc_enabled = [True] * 8

    sys.converter.adc._check_clock_relations()
    sys.converter.dac._check_clock_relations()
    # sys.converter._check_clock_relations()

    # sys.Debug_Solver = True
    try:
        cfg = sys.solve()
    except:
        pytest.skip("No solution for configuration")

    # Use older mode naming
    cfg["jesd_adc"]["jesd_mode"] = str(
        int(np.floor(float(cfg["jesd_adc"]["jesd_mode"])))
    )
    cfg["jesd_dac"]["jesd_mode"] = str(
        int(np.floor(float(cfg["jesd_dac"]["jesd_mode"])))
    )

    ###############################################################################
    # Generate DT fragment
    fmc = adidt.ad9081_fmc()
    clock, adc, dac = fmc.map_clocks_to_board_layout(cfg)
    fmc.gen_dt(clock=clock, adc=adc, dac=dac)
    shutil.copy(
        "ad9081_fmc_zcu102.dts",
        "linux/arch/arm64/boot/dts/xilinx/ad9081_fmc_zcu102.dts",
    )

    ###############################################################################
    # Build new devicetree
    print("Building new devicetree")
    os.chdir("linux")
    os.system(
        "ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- make xilinx/ad9081_fmc_zcu102.dtb"
    )
    shutil.copy("arch/arm64/boot/dts/xilinx/ad9081_fmc_zcu102.dtb", "../system.dtb")
    os.chdir("..")

    ###############################################################################
    # Update on board
    print("Updating devicetree on board")
    file_list = ["system.dtb"]
    show = True

    d = adidt.dt(dt_source="remote_sd", ip=ip, arch="arm64")
    d.copy_local_files_to_remote_sd_card(file_list, show=show)
    d._runr("reboot", warn=True)

    ###############################################################################
    # Verify board working
    print("Waiting for board to reboot")
    for _ in tqdm(range(30)):
        time.sleep(1)

    ctx = iio.Context(f"ip:{ip}")
    required_devices = ["axi-ad9081-rx-hpc", "axi-ad9081-tx-hpc", "hmc7044"]
    found_devices = [dev.name for dev in ctx.devices]
    for dev in required_devices:
        assert dev in found_devices, f"{dev} not found"

    dev = jesd(address=ip)
    jdevices_statuses = dev.get_all_statuses()
    for dev in jdevices_statuses:
        print("Checking", dev)
        assert jdevices_statuses[dev]["enabled"] == "enabled"
        assert jdevices_statuses[dev]["Link status"] == "DATA"
        lr = float(jdevices_statuses[dev]["Lane rate"].split(" ")[0]) * 1e6
        if "rx" in dev:
            assert lr == sys.converter.adc.bit_clock
        else:
            assert lr == sys.converter.dac.bit_clock
