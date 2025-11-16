#!/usr/bin/python3
import argparse
import logging
import sys
import subprocess
import time
from typing import List, Optional
import vici
import yaml


class TunnelChecker:
    def __init__(
        self,
        tunnels: List[str] = [],
        socketPath: Optional[str] = None,
        configFile: Optional[str] = None,
        verbose: bool = False,
        quiet: bool = False,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        """
        Initialize the TunnelChecker.

        Args:
            tunnels: List of tunnels (as strings). Those are the names of the configured CHILD_SAs.
            socketPath: If a non-standard socket location is used, set this argument to the path to it.
            configFile: Path to YAML configuration file containing tunnel names.
            verbose: Enable verbose logging output.
            quiet: Suppress all non-error output.
            max_retries: Maximum number of retries for failed ipsec operations.
            retry_delay: Base delay in seconds between retries (uses exponential backoff).
        """
        self.tunnels = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.loadConfiguration(configFile)

        if not len(tunnels) > 0 and not self.tunnels:
            logging.error("No tunnels to monitor were configured.")
            sys.exit(1)

        try:
            self.session = vici.Session(socketPath)
        except Exception as e:
            logging.critical(f"Failed to connect to VICI socket: {e}")
            sys.exit(5)

        self.tunnels.extend(tunnels)

        # Setup logging - only create handler if not already configured
        self.logging = logging.getLogger(__name__)

        # Only add handler if none exists
        if not self.logging.handlers:
            channel = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            channel.setFormatter(formatter)
            self.logging.addHandler(channel)

        self.verbose = verbose
        self.quiet = quiet

        self.logging.setLevel(logging.INFO)
        if self.logging.handlers:
            self.logging.handlers[0].setLevel(logging.INFO)

        if self.verbose:
            self.logging.setLevel(logging.DEBUG)
            if self.logging.handlers:
                self.logging.handlers[0].setLevel(logging.DEBUG)

        if self.quiet:
            self.logging.setLevel(logging.ERROR)
            if self.logging.handlers:
                self.logging.handlers[0].setLevel(logging.ERROR)

    def loadConfiguration(self, path: Optional[str]) -> None:
        """
        Load tunnel configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.
        """
        try:
            file = None
            try:
                file = open(path, "r")
            except Exception as e:
                logging.info(f"Could not open the configuration file. Not loading tunnels from it. Exception: {e}")
                return

            yamlObject = yaml.safe_load(file)
            if type(yamlObject) != list:
                logging.critical("The content of the configuration file has to be a list.")
                sys.exit(2)
            for element in yamlObject:
                if type(element) != str:
                    logging.critical(f"The list must only contain strings. Invalid item: {element}")
                    sys.exit(3)
            self.tunnels.extend(yamlObject)
        except Exception as e:
            logging.critical(f"A critical exception occurred while reading from the configuration file: {e}")
            sys.exit(4)
        finally:
            if file:
                file.close()

    def _run_ipsec_command(self, action: str, tunnel: str) -> bool:
        """
        Run an ipsec command with retry logic.

        Args:
            action: The ipsec action (e.g., 'down', 'up').
            tunnel: The tunnel name to operate on.

        Returns:
            True if the command succeeded, False otherwise.
        """
        for attempt in range(self.max_retries):
            try:
                result = subprocess.run(
                    ['/usr/sbin/ipsec', action, tunnel],
                    capture_output=True,
                    timeout=30
                )

                if result.returncode == 0:
                    self.logging.debug(f"Successfully executed 'ipsec {action} {tunnel}'")
                    return True
                else:
                    self.logging.warning(
                        f"'ipsec {action} {tunnel}' returned non-zero exit code {result.returncode}. "
                        f"Stderr: {result.stderr.decode('utf-8', errors='ignore')}"
                    )

            except subprocess.TimeoutExpired:
                self.logging.warning(f"'ipsec {action} {tunnel}' timed out on attempt {attempt + 1}/{self.max_retries}")
            except Exception as e:
                self.logging.warning(f"'ipsec {action} {tunnel}' failed on attempt {attempt + 1}/{self.max_retries}: {e}")

            # Exponential backoff if not the last attempt
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                self.logging.debug(f"Retrying in {delay} seconds...")
                time.sleep(delay)

        self.logging.error(f"Failed to execute 'ipsec {action} {tunnel}' after {self.max_retries} attempts")
        return False

    def resetTunnels(self, downTunnels: List[str]) -> None:
        """
        Reset down tunnels by bringing them down and then back up.

        Args:
            downTunnels: List of tunnel names to reset.
        """
        for tunnel in downTunnels:
            self.logging.info(f"Resetting {tunnel} tunnel")

            # First, bring the tunnel down
            if self._run_ipsec_command('down', tunnel):
                # Wait a moment before bringing it back up
                time.sleep(1)

                # Then bring it back up
                if self._run_ipsec_command('up', tunnel):
                    self.logging.info(f"Successfully reset {tunnel}")
                else:
                    self.logging.error(f"Failed to bring {tunnel} back up")
            else:
                self.logging.error(f"Failed to bring {tunnel} down, skipping 'up' command")

    def run(self) -> int:
        """
        Run the tunnel check and reset any down tunnels.

        Returns:
            0 if all tunnels are up or were successfully reset, 1 if some tunnels remain down.
        """
        downTunnels = list(self.tunnels)

        try:
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

                        # Check if exact name matches
                        if name in downTunnels and state == "INSTALLED":
                            downTunnels.remove(name)
                            self.logging.debug(f"Tunnel {name} is up (INSTALLED)")
                            continue

                        # check if this is as in newer versions (name-ID format)
                        lastDash = name.rfind("-")
                        # dash found
                        if lastDash > 0:
                            # check if anything after the dash is numbers
                            if name[lastDash + 1:].isnumeric():
                                rest = name[:lastDash]
                                if rest in downTunnels and state == "INSTALLED":
                                    downTunnels.remove(rest)
                                    self.logging.debug(f"Tunnel {rest} is up (INSTALLED) with ID suffix")
        except Exception as e:
            self.logging.error(f"Error querying VICI session: {e}")
            return 1

        if len(downTunnels) > 0:
            self.logging.warning(f"The following tunnels were detected as being down: {' '.join(downTunnels)}")
            self.resetTunnels(downTunnels)
            return 1
        else:
            self.logging.info("All monitored tunnels are up")
            return 0


def run_daemon(checker: TunnelChecker, interval: int) -> None:
    """
    Run the tunnel checker in daemon mode with periodic checks.

    Args:
        checker: The TunnelChecker instance to run.
        interval: Time in seconds between checks.
    """
    checker.logging.info(f"Starting daemon mode with {interval} second interval")

    try:
        while True:
            checker.logging.debug("Running tunnel check...")
            checker.run()
            checker.logging.debug(f"Sleeping for {interval} seconds")
            time.sleep(interval)
    except KeyboardInterrupt:
        checker.logging.info("Daemon mode interrupted by user, shutting down")
        sys.exit(0)
    except Exception as e:
        checker.logging.critical(f"Daemon mode encountered critical error: {e}")
        sys.exit(6)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script to monitor and reset StrongSwan IPsec tunnels via VICI."
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
        "--daemon",
        help="Run in daemon mode with continuous monitoring",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--interval",
        help="Interval in seconds between checks in daemon mode (default: 300)",
        type=int,
        default=300,
    )
    parser.add_argument(
        "--max-retries",
        help="Maximum number of retries for failed ipsec commands (default: 3)",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--retry-delay",
        help="Base delay in seconds between retries, uses exponential backoff (default: 2)",
        type=int,
        default=2,
    )
    parser.add_argument(
        "tunnels", nargs="*", help="The list of CHILD_SAs to monitor and reestablish"
    )

    args = parser.parse_args()

    if args.verbose and args.quiet:
        logging.error("--verbose and --quiet can not be used at the same time.")
        sys.exit(1)

    if args.daemon and args.interval < 1:
        logging.error("--interval must be at least 1 second in daemon mode.")
        sys.exit(1)

    checker = TunnelChecker(
        args.tunnels,
        args.socket,
        args.config,
        args.verbose,
        args.quiet,
        args.max_retries,
        args.retry_delay,
    )

    if args.daemon:
        run_daemon(checker, args.interval)
    else:
        sys.exit(checker.run())
