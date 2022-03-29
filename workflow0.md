# Workflow 0: Matched Sample Rate Validation

<center>

![Flow](test-flow.mmd.svg)

</center>

The test workflow follows the path in the figure above, by starting with a high-level sample rate then translating that down to the hardware to configuration and validation. This leverages 4 main python libraries:

- pyadi-jif: Configuration generation and validation
- pyadi-dt: DeviceTree Translation
- pyadi-iio: IIO and SSH access
- nebula: Hardware management for boot files and UART control