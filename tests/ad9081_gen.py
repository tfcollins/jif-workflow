import adijif as jif

try:
    from tests.common import create_jif_configuration
except:
    from common import create_jif_configuration


def gen_dict(cfg):
    adc_rate = cfg["rx"]["sample_clock"] * cfg["rx"]["coarse"] * cfg["rx"]["fine"]
    dac_rate = cfg["tx"]["sample_clock"] * cfg["tx"]["coarse"] * cfg["rx"]["fine"]
    return dict(
        DAC_freq=int(dac_rate),
        ADC_freq=int(adc_rate),
        fddc=cfg["rx"]["fine"],
        cddc=cfg["rx"]["coarse"],
        fduc=cfg["tx"]["fine"],
        cduc=cfg["tx"]["coarse"],
    )


def _ad9081_tx_config(tx, cfg_tx, rx_gsps):
    done = False
    for tx_c in cfg_tx["decimations"]:
        for tx_mult in [4, 3, 2, 1]:
            tx_gsps = rx_gsps * tx_mult * 1e9
            # Determine a DAC rate in range
            if tx_gsps < tx.converter_clock_min or tx_gsps > tx.converter_clock_max:
                continue
            tx.interpolation = tx_c["coarse"] * tx_c["fine"]
            tx.sample_clock = tx_gsps / tx.interpolation
            try:
                tx._check_clock_relations()
            except:
                # print("Failed to find a valid clock configuration")
                continue
            sample_clock = tx_gsps / tx.interpolation
            return tx_c, sample_clock

    return None, None


def _system_check(rx, tx, c, tx_c, vcxo, rx_sample_clock, tx_sample_clock):
    full_config = {
        "rx": {
            "sample_clock": rx_sample_clock,
            "coarse": c["coarse"],
            "fine": c["fine"],
        },
        "tx": {
            "sample_clock": tx_sample_clock,
            "coarse": tx_c["coarse"],
            "fine": tx_c["fine"],
        },
    }

    try:
        d = gen_dict(full_config)
        cfg, sys = create_jif_configuration(d, vcxo)
    except Exception as e:
        return False

    rx_gsps = rx_sample_clock * rx.decimation
    tx_gsps = tx_sample_clock * tx.interpolation

    # print("------------------")
    print(f"Rx Valid: {rx_gsps}, {c['coarse']}, {c['fine']}")
    print(f"Tx Valid: {tx_gsps}, {tx_c['coarse']}, {tx_c['fine']}")
    return gen_dict(full_config)


def ad9081_get_rx_decimations(vcxo, rx_qmode, tx_qmode, rx_jesd_class, tx_jesd_class):
    """Find valid converter rates (DAC+ADC) and decs/ints only based on VCXO
    and JESD modes
    """

    all_configs = []

    rx = jif.ad9081_rx()
    tx = jif.ad9081_tx()

    cfg_rx = rx.quick_configuration_modes[rx_jesd_class][rx_qmode]
    cfg_tx = tx.quick_configuration_modes[tx_jesd_class][tx_qmode]

    print("\n\n\n")
    found_pairs = []

    for c in cfg_rx["decimations"]:
        print("------------------")
        print(f"Looking for configuration: {c['coarse']},{c['fine']}")
        found_rx_config = False
        found_tx_config = False
        for oogsps in reversed(range(10, 41)):
            # Determine a ADC rate in range
            gsps = oogsps / 10
            if gsps < c["conv_min"] or gsps > c["conv_max"]:
                continue
            rx.decimation = c["coarse"] * c["fine"]
            rx.sample_clock = gsps * 1e9 / rx.decimation
            try:
                rx._check_clock_relations()
                found_rx_config = True
            except:
                continue
            rx_sample_clock = gsps * 1e9 / rx.decimation

            # Check TX
            tx_c, tx_sample_clock = _ad9081_tx_config(tx, cfg_tx, gsps)
            if not tx_c:
                continue

            # Check system
            config = _system_check(
                rx, tx, c, tx_c, vcxo, rx_sample_clock, tx_sample_clock
            )
            if config:
                found_tx_config = True
                if c["coarse"] > c["fine"]:
                    p = f"{c['coarse']}_{c['fine']}"
                else:
                    p = f"{c['fine']}_{c['coarse']}"
                found_pairs.append(p)
                all_configs.append(config)
                break

        if c["coarse"] > c["fine"]:
            p = f"{c['coarse']}_{c['fine']}"
        else:
            p = f"{c['fine']}_{c['coarse']}"
        if not found_tx_config:
            if p in found_pairs:
                print("Existing solution has same decimation")
            print("Failed to find a valid configuration based on TX")

        if not found_rx_config:
            if p in found_pairs:
                print("Existing solution has same decimation")
            print(
                f"No valid clock configuration found RX {c['coarse']},{c['fine']} {c}"
            )

    # print(cfg)
    # return cfg_tx
    print(
        f"Total configuration found: {len(all_configs)}"
        + f" (Desired {len(cfg_rx['decimations'])})"
    )
    return all_configs


def get_rates_from_sample_rate(sample_rate, vcxo, rx_jesd_mode, tx_jesd_mode):
    """Based on a desired sample rate (RX and TX), VCXO, and JESD modes
    determine valid decimator/interpolation/ADC rate/DAC rate.
    """

    cdcs = [1, 2, 3, 4, 6]
    fdcs = [1, 2, 3, 4, 6, 8, 12, 16, 24]

    cdcs_tx = [1, 2, 4, 6, 8, 12]
    fdcs_tx = [1, 2, 3, 4, 6, 8]

    rx = jif.ad9081_rx()
    tx = jif.ad9081_tx()

    cfg = rx.quick_configuration_modes["jesd204b"][rx_jesd_mode]
    rx_d = [(dec["coarse"], dec["fine"]) for dec in cfg["decimations"]]

    cfg = tx.quick_configuration_modes["jesd204b"][tx_jesd_mode]
    tx_d = [(dec["coarse"], dec["fine"]) for dec in cfg["decimations"]]

    print(f"----Searching for sample_rate config: {sample_rate}")

    for cdc_tx in cdcs_tx:
        for cdc_rx in cdcs:
            for fdc_tx in fdcs_tx:
                for fdc_rx in fdcs:
                    # Filter out unavailable decs/ints
                    if (cdc_rx, fdc_rx) not in rx_d:
                        continue
                    if (cdc_tx, fdc_tx) not in tx_d:
                        continue

                    DAC_rate = fdc_tx * cdc_tx * sample_rate
                    ADC_rate = fdc_rx * cdc_rx * sample_rate
                    if (
                        DAC_rate >= 2.9e9
                        and DAC_rate <= 12e9
                        and ADC_rate >= 1.45e9
                        and ADC_rate <= 4e9
                    ):
                        param_set = dict(
                            DAC_freq=int(DAC_rate),
                            ADC_freq=int(ADC_rate),
                            fddc=fdc_rx,
                            cddc=cdc_rx,
                            fduc=fdc_tx,
                            cduc=cdc_tx,
                        )
                        try:
                            cfg, sys = create_jif_configuration(
                                param_set, vcxo, rx_jesd_mode, tx_jesd_mode
                            )
                            print(f"----Found sample_rate config: {sample_rate}")
                            return param_set
                        except Exception as e:
                            print("Configuration failed")
                            print(e)
                            pass
    return dict(sample_rate=sample_rate, not_possible=True)


if __name__ == "__main__":
    cfg = ad9081_get_rx_decimations(122.88e6, "10.0", "9", "jesd204b", "jesd204b")
