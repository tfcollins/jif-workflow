import json
import os
import shutil

import pytest

arch = os.environ.get("ARCH") if "ARCH" in os.environ else "arm64"
if arch == "arm64":
    from tests.common import params
else:
    from tests.common import params32 as params

@pytest.fixture(
    scope="module",
    params=[params],
)
def build_kernel(request):  # sourcery skip: raise-specific-error
    # if not os.path.exists(
    #     f"/opt/Xilinx/Vivado/{request.param['Vivado']}/settings64.sh"
    # ):
    #     raise Exception("No Vivado settings found")
    if not os.path.isdir("linux"):
        os.system(
            f"git clone https://github.com/analogdevicesinc/linux.git --depth=1 -b {request.param['LinuxBranch']}"
        )
    os.chdir("linux")
    # cmd = f". /opt/Xilinx/Vivado/{request.param['Vivado']}/settings64.sh ; "
    cmd = ""
    cmd += f"export ARCH={request.param['ARCH']} ; "
    cmd += f"export CROSS_COMPILE={request.param['CROSS_COMPILE']} ; "
    if arch == "arm64":
        os.system(f"{cmd} make adi_zynqmp_defconfig")
        os.system(f"{cmd} make -j$(nproc) Image UIMAGE_LOADADDR=0x8000")
    else:
        os.system(f"{cmd} make zynq_xcomm_adv7511_defconfig")
        os.system(f"{cmd} make -j$(nproc) UIMAGE_LOADADDR=0x8000 uImage")
    os.chdir("..")


@pytest.fixture(scope="function")
def logger(request):
    class MyLogger:
        saved = {}

    meta = MyLogger()

    yield meta

    if "cfg" not in meta.saved:
        return

    testname = request.node.name
    if not os.path.isdir("logs"):
        os.mkdir("logs")
    if "dmesg" in meta.saved:
        with open(f"logs/{testname}_dmesg.txt", "w") as f:
            f.write(meta.saved["dmesg"])
            del meta.saved["dmesg"]
    with open(f"logs/{testname}.json", "w") as f:
        json.dump(meta.saved, f, indent=4)

    dts = "ad9081_fmc_zcu102.dts"
    if os.path.isfile(dts):
        shutil.copy(dts, os.path.join("logs",f"{testname}_{dts}"))
