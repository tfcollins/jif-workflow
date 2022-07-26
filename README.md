# jif-worflow
Complete end to end workflow examples and tests for JESD configurations of ADI board

See [workflow0](workflow0.md) for a breakdown of the different projects and flow of the test benches.

## Set up codebase

Clone repo with all submodules and enter repo

```bash
git clone --recursive https://github.com/tfcollins/jif-worflow.git -b dev
cd jif-workflow
```

Set up python in virtualenv and install dependencies

```bash
virtualenv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Hardware Configuration

The current workflow testing assumes the use of a AD9081+ZCU102 or a DAQ2+ZC706 and the current master branch BOOT.BIN and Kernel are already being used. The board must also correctly boot. Before running any tests, first boot the board.

To help make sure the board is booted before checking for the drivers and the link status, UART is monitored for the login prompt. This is done through the nebula repo, which must be configured. To make this function the tty must be set correctly in the **ad9081.yaml** of the repo's root:

```
zynqmp-zcu102-rev10-ad9081:
  ...
  uart-config:
  - address: /dev/ttyUSB0 # <- Update
```

The workflow will also leverage SSH and IIO over IP so an IP must be set as an environmental variable. Otherwise **analog.local** is assumed:

```
export TARGET_IP=192.168.3.1
```


## Running the workflow

Worflow runs are set up as pytest unittest since it makes handling errors and state much much simpler. There is only one test workflow but other would have the similar syntax. This should be run from the root of the *jif-workflow* repo:

```bash
python -m pytest -vs tests/test_ad9081_wf.py
```

This will place logs and other test artifacts inside the **logs** folder inside the root of the repo.

## Analyzing data

The recommended analysis mechanism is through the use of Jupyter Notebooks as it makes sharing results easier.

Start the notebook server with external access:

```bash
jupyter-notebook --ip 0.0.0.0
```
