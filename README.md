# jif-worflow
Complete end to end workflow examples and tests for JESD configurations of ADI board

## Set up codebase

Clone repo with all submodules and enter repo

```bash
git clone --recursive https://github.com/tfcollins/jif-worflow.git -b dev
cd jif-workflow
```

Set up python in virtualenv and install dependencies

```bash
make dev-setup
```

Activate environment 

```bash
source .venv/bin/activate
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