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


def ad9081_get_rx_decimations(vcxo, rx_qmode, tx_qmode, rx_jesd_class, tx_jesd_class):

    all_configs = []

    rx = jif.ad9081_rx()
    tx = jif.ad9081_tx()

    cfg_rx = rx.quick_configuration_modes[rx_jesd_class][rx_qmode]
    cfg_tx = tx.quick_configuration_modes[tx_jesd_class][tx_qmode]

    # conv_rates = [0.4]

    for c in cfg_rx["decimations"]:
        for gsps in reversed(range(1, 4)):
            # Determine a ADC rate in range
            if gsps < c["conv_min"] or gsps > c["conv_max"]:
                continue
            rx.decimation = c["coarse"] * c["fine"]
            rx.sample_clock = gsps * 1e9 / rx.decimation
            try:
                rx._check_clock_relations()
            except:
                print("Failed to find a valid clock configuration")
                continue
            print(f"Rx Valid: {gsps}, {c['coarse']}, {c['fine']}")
            done = False
            for tx_c in cfg_tx["decimations"]:
                for tx_mult in [4, 3, 2, 1]:
                    tx_gsps = gsps * tx_mult * 1e9
                    # Determine a DAC rate in range
                    if (
                        tx_gsps < tx.converter_clock_min
                        or tx_gsps > tx.converter_clock_max
                    ):
                        continue
                    tx.interpolation = tx_c["coarse"] * tx_c["fine"]
                    tx.sample_clock = tx_gsps / tx.interpolation
                    try:
                        tx._check_clock_relations()
                    except:
                        print("Failed to find a valid clock configuration")
                        continue
                    print(f"Tx Valid: {gsps}, {c['coarse']}, {c['fine']}")

                    full_config = {
                        "rx": {
                            "sample_clock": tx.sample_clock,
                            "coarse": c["coarse"],
                            "fine": c["fine"],
                        },
                        "tx": {
                            "sample_clock": tx.sample_clock,
                            "coarse": tx_c["coarse"],
                            "fine": tx_c["fine"],
                        },
                    }

                    # d = gen_dict(full_config)
                    # cfg, sys = create_jif_configuration(d, vcxo)
                    try:
                        d = gen_dict(full_config)
                        cfg, sys = create_jif_configuration(d, vcxo)
                    # except Exception as e:
                    except Exception as e:
                        print(e)
                        print("Failed to create configuration")
                        # print("Failed to create configuration", e)
                        continue

                    all_configs.append(gen_dict(full_config))

                    done = True
                    break
                if done:
                    # done = False
                    break
            if done:
                done = False
                break

                # return rx.decimation, tx.interpolation

    # print(cfg)
    # return cfg_tx
    print(
        f"Total configuration found: {len(all_configs)}"
        + f" (Desired {len(cfg_rx['decimations'])})"
    )
    return all_configs


if __name__ == "__main__":
    cfg = ad9081_get_rx_decimations(122.88e6, "10.0", "9", "jesd204b", "jesd204b")
