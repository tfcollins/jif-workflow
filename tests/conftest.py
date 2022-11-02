import json
import os
import shutil

import pytest
from .reporting import pytest_runtest_makereport, pytest_sessionfinish

# zynqmp-zcu102-rev10-ad9081-m8-l4-vcxo122p88.dts

repo = os.environ.get("CUSTOM_GIT") if "CUSTOM_GIT" in os.environ else "https://github.com/analogdevicesinc/linux.git"

linux_parent = os.environ.get("LINUX_DIR") if "LINUX_DIR" in os.environ else os.getcwd()


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
    loc = os.path.join(linux_parent, "linux")
    org = os.getcwd()

    if not os.path.isdir(loc):
        os.system(
            f"git clone {repo} --depth=1 -b {request.param['LinuxBranch']} {loc}"
        )
    os.chdir(loc)
    # cmd = f". /opt/Xilinx/Vivado/{request.param['Vivado']}/settings64.sh ; "
    cmd = ""
    cmd += f"export ARCH={request.param['ARCH']} ; "
    cmd += f"export CROSS_COMPILE={request.param['CROSS_COMPILE']} ; "
    if arch == "arm64":
        os.system(f"{cmd} make adi_zynqmp_defconfig")
        os.system(f"{cmd} make -j4 Image UIMAGE_LOADADDR=0x8000")
    else:
        os.system(f"{cmd} make zynq_xcomm_adv7511_defconfig")
        os.system(f"{cmd} make -j4 UIMAGE_LOADADDR=0x8000 uImage")
    os.chdir(org)
    return loc


@pytest.fixture(scope="function")
def logger(request):
    class MyLogger:
        saved = {}

    meta = MyLogger()

    yield meta

    print("\nLogger called\n")

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