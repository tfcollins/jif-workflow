import adijif
import numpy as np
import shutil
import os
import pytest

params = {
    "Vivado": "2019.1",
    "LinuxBranch": "2019_2",
    "ARCH": "arm64",
    "CROSS_COMPILE": "aarch64-linux-gnu-",
}


def build_devicetree(dts_name):
    dtb_name = dts_name.replace(".dts", ".dtb")
    shutil.copy(
        dts_name,
        f"linux/arch/arm64/boot/dts/xilinx/{dts_name}",
    )
    os.chdir("linux")
    cmd = f". /opt/Xilinx/Vivado/{params['Vivado']}/settings64.sh ; "
    cmd += f"export ARCH={params['ARCH']} ; "
    cmd += f"export CROSS_COMPILE={params['CROSS_COMPILE']} ; "
    os.system(f"{cmd} make xilinx/{dtb_name}")
    shutil.copy(f"arch/arm64/boot/dts/xilinx/{dtb_name}", "../system.dtb")
    os.chdir("..")
    return "system.dtb"


def create_jif_configuration(param_set, vcxo=122.88e6):
    ###############################################################################
    # RX
    rx = adijif.ad9081_rx
    params = {"jesd_class": "jesd204b", "M": 8, "L": 4, "S": 1, "Np": 16}
    rx_modes = adijif.utils.get_jesd_mode_from_params(rx, **params)
    # print("RX", rx_modes)
    assert len(rx_modes) == 1, f"Expected 1 mode, got {len(rx_modes)}"

    # TX
    tx = adijif.ad9081_tx
    params = {"jesd_class": "jesd204b", "M": 8, "L": 4, "S": 1, "Np": 16}
    tx_modes = adijif.utils.get_jesd_mode_from_params(tx, **params)
    # print("TX", tx_modes)
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
    cfg = sys.solve()
    # try:
    #     cfg = sys.solve()
    # except:
    #     pytest.skip("No solution for configuration")

    # Use older mode naming
    cfg["jesd_adc"]["jesd_mode"] = str(
        int(np.floor(float(cfg["jesd_adc"]["jesd_mode"])))
    )
    cfg["jesd_dac"]["jesd_mode"] = str(
        int(np.floor(float(cfg["jesd_dac"]["jesd_mode"])))
    )

    return cfg, sys
