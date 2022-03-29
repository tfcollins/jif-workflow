# Workflow 0: Matched Sample Rate Validation

<center>

![Flow](test-flow.mmd.svg)

</center>

The test workflow follows the path in the figure above, by starting with a high-level sample rate then translating that down to the hardware to configuration and validation. This leverages 4 main python libraries:

- <span style="color:red">pyadi-jif</span>: Configuration generation and validation
- <span style="color:green">pyadi-dt</span>: DeviceTree Translation
- <span style="color:purple">pyadi-iio</span>: IIO and SSH access
- <span style="color:blue">nebula</span>: Hardware management for boot files and UART control
