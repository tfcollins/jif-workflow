# Workflow 0: Matched Sample Rate Validation

<center>

```mermaid
flowchart TD

	A[Select Sample Rate] --> B[Generate Valid DP Config];
	B --> C[Generate Clock Config JIF]
	C --> D[Generate DeviceTree]
	D --> E[Update Board with New DT]
	E --> K[Reboot Board and Verify Booted]
	K --> F[Check IIO Driver Exist]
	F --> G[Check Links Up]
	G --> A

	style A fill:red
	style B fill:red
	style C fill:red
	style D fill:green
	style E fill:green
	style F fill:purple
	style G fill:purple
	style K fill:blue
```
  
</center>

The test workflow follows the path in the figure above, by starting with a high-level sample rate then translating that down to the hardware to configuration and validation. This leverages 4 main python libraries:

- $\textcolor{red}{pyadi-jif}$: Configuration generation and validation
- $\textcolor{green}{pyadi-dt}$: DeviceTree Translation
- $\textcolor{purple}{pyadi-iio}$: IIO and SSH access
- $\textcolor{blue}{nebula}$: Hardware management for boot files and UART control
