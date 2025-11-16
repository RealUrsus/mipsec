```python
#!/usr/bin/python3
import argparse
import logging
import sys
import subprocess
import vici
import yaml


class tunnelChecker:
    def __init__(self, tunnels=[], socketPath=None, configFile=None, verbose=False, quiet=False):
        """
        param tunnels: List of tunnels (as strings). Those are the names of the configured CHILD_SAs.
        param socketPath: If a non-standard socket location is used, set this argument to the path to it.
        """
        self.tunnels = []
        self.loadConfiguration(configFile)

        if not len(tunnels) > 0 and not self.tunnels:
            logging.error("No tunnels to monitor were configured.")
            sys.exit(1)
        self.session = vici.Session(socketPath)

        self.tunnels.extend(tunnels)

        self.logging = logging.getLogger(__name__)
        channel = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        channel.setFormatter(formatter)
        self.logging.addHandler(channel)
        self.verbose = verbose
        self.quiet = quiet

        self.logging.setLevel(logging.INFO)
        channel.setLevel(logging.INFO)

        if self.verbose:
            self.logging.setLevel(logging.DEBUG)
            channel.setLevel(logging.DEBUG)

        if self.quiet:
            self.logging.setLevel(logging.ERROR)
            channel.setLevel(logging.ERROR)

    def loadConfiguration(self, path):
        try:
            file = None
            try:
                file = open(path, "r")
            except Exception as e:
                logging.info("Could not open the configuration file. Not loading tunnels from it. Exception: {}".format(e))
                return

            yamlObject = yaml.safe_load(file)
            if type(yamlObject) != list:
                logging.critical("The content of the configuration file has to be a list.")
                sys.exit(2)
            for element in yamlObject:
                if type(element) != str:
                    logging.critical("The list must only contain strings. Invalid item: {}".format(element))
                    sys.exit(3)
            self.tunnels.extend(yamlObject)
        except Exception as e:
            logging.critical("A critical exception occured while reading from the configuration file: {}".format(e))
            sys.exit(4)
        return

    def resetTunnels(self, downTunnels):
            for tunnel in downTunnels:
                self.logging.info("Reseting {} tunnel".format(tunnel))
                subprocess.run(['/usr/sbin/ipsec', 'down', tunnel], capture_output=True)

    def run(self):
        downTunnels = list(self.tunnels)
        for i in self.session.list_sas():
            for j in i.values():
                # in different versions of strongSwan, the keys of the items is a unique string composed
                # of the name of the CHILD_SA configuration and the CHILD_SA's ID.
                # Older versions return the key as the CHILD_SA config's name. We need to catch both.
                for childSAName, childSAValue in j["child-sas"].items():
                    state = str(childSAValue["state"], "UTF-8")
                    if type(childSAName) == bytes:
                        name = str(childSAName, "UTF-8")
                    else:
                        name = childSAName
                    if name in downTunnels and state == "INSTALLED":
                        downTunnels.remove(childSAName)
                        continue
                    # check if this is as in newer versions
                    lastDash = name.rfind("-")
                    # dash found
                    if lastDash > 0:
                        # check if anything after the dash is numbers
                        if name[lastDash + 1 :].isnumeric():
                            rest = name[:lastDash]
                            if rest in downTunnels and state == "INSTALLED":
                                downTunnels.remove(rest)
                    # no Dash found and no match

        if len(downTunnels) > 0:
            self.logging.warning("The following tunnels were detected as being down: {}".format(" ".join(downTunnels)))
            self.resetTunnels(downTunnels)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script to monitor and reset tunnels."
    )
    parser.add_argument(
        "--socket",
        help="If a non-standard path to the VICI socket is used, the path to it is set with this argument.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--config",
        help="The path to the optional configuration file.",
        type=str,
        default="/opt/mipsec/mipsec.yaml",
    )
    parser.add_argument(
        "--verbose",
        help="Print additional information",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--quiet",
        help="Disable any non-error output from the script",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "tunnels", nargs="*", help="The list of CHILD_SAs to monitor and reestablish"
    )

    args = parser.parse_args()

    if args.verbose and args.quiet:
        logging.error("--verbose and --quiet can not be used at the same time.")
        sys.exit(1)

    checker = tunnelChecker(args.tunnels, args.socket, args.config, args.verbose, args.quiet)
    checker.run()