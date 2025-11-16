# MIPsec - StrongSwan Tunnel Monitor

A lightweight Python tool for monitoring and managing StrongSwan IPsec tunnels via the VICI (Versatile IKE Control Interface) protocol.

## Overview

MIPsec monitors configured IPsec CHILD_SA tunnels and automatically resets connections that are down. It's designed to work as a monitoring script that can be run periodically via cron or other schedulers.

## Features

- 🔍 **Tunnel Status Monitoring**: Checks if configured tunnels are in INSTALLED state
- 🔄 **Automatic Reset**: Downs tunnels that are detected as non-operational
- 📝 **Flexible Configuration**: Support for YAML config files and command-line arguments
- 🔧 **Version Compatibility**: Handles both old and new StrongSwan naming conventions
- 📊 **Configurable Logging**: Verbose, normal, and quiet modes
- 🎯 **Custom VICI Socket**: Support for non-standard socket paths

## Requirements

- Python 3.6+
- StrongSwan with VICI plugin enabled
- Python packages:
  - `vici` - StrongSwan VICI protocol library
  - `PyYAML` - YAML configuration parsing

## Installation

### 1. Install Python Dependencies

```bash
pip install vici PyYAML
```

### 2. Clone or Download

```bash
git clone <repository-url>
cd mipsec
```

### 3. Make Executable

```bash
chmod +x mipsec.py
```

### 4. Configure

Create a configuration file at `/opt/mipsec/mipsec.yaml` (or specify custom path):

```yaml
- tunnel-name-1
- tunnel-name-2
- tunnel-name-3
```

## Usage

### Basic Usage

Monitor tunnels defined in config file:
```bash
./mipsec.py
```

### Command-Line Arguments

Monitor specific tunnels:
```bash
./mipsec.py tunnel1 tunnel2 tunnel3
```

Use custom config file:
```bash
./mipsec.py --config /path/to/config.yaml
```

Custom VICI socket path:
```bash
./mipsec.py --socket /var/run/charon.vici
```

Verbose output:
```bash
./mipsec.py --verbose
```

Quiet mode (errors only):
```bash
./mipsec.py --quiet
```

### Full Options

```
usage: mipsec.py [-h] [--socket SOCKET] [--config CONFIG] [--verbose] [--quiet] [tunnels ...]

A script to monitor and reset tunnels.

positional arguments:
  tunnels          The list of CHILD_SAs to monitor and reestablish

optional arguments:
  -h, --help       show this help message and exit
  --socket SOCKET  If a non-standard path to the VICI socket is used, the path to it is set with this argument.
  --config CONFIG  The path to the optional configuration file.
  --verbose        Print additional information
  --quiet          Disable any non-error output from the script
```

## Configuration File Format

The configuration file should be a YAML list of tunnel names (CHILD_SA configuration names):

```yaml
- office-tunnel
- datacenter-vpn
- remote-site
```

## Cron Integration

To run every 5 minutes:

```cron
*/5 * * * * /usr/bin/python3 /opt/mipsec/mipsec.py --config /opt/mipsec/mipsec.yaml
```

To run with logging:

```cron
*/5 * * * * /usr/bin/python3 /opt/mipsec/mipsec.py --config /opt/mipsec/mipsec.yaml >> /var/log/mipsec.log 2>&1
```

## How It Works

1. **Load Configuration**: Reads tunnel names from config file and/or command-line arguments
2. **Connect to VICI**: Establishes connection to StrongSwan's VICI socket
3. **Query Status**: Lists all Security Associations (SAs) and their CHILD_SAs
4. **Check State**: Verifies each configured tunnel is in `INSTALLED` state
5. **Reset Down Tunnels**: Executes `ipsec down <tunnel>` for any non-operational tunnels

### Version Compatibility

The tool handles two StrongSwan naming conventions:
- **Older versions**: CHILD_SA name = configuration name
- **Newer versions**: CHILD_SA name = `<config-name>-<ID>` (e.g., `tunnel1-42`)

## Exit Codes

- `0` - Success (all tunnels up or successfully reset)
- `1` - No tunnels configured or invalid arguments
- `2` - Configuration file format error (not a list)
- `3` - Configuration file contains non-string items
- `4` - Critical error reading configuration file

## Permissions

The script requires:
- Read access to VICI socket (typically `/var/run/charon.vici`)
- Execute permissions for `/usr/sbin/ipsec`
- Appropriate permissions to down IPsec connections

Usually requires running as `root` or with `CAP_NET_ADMIN` capability.

## Troubleshooting

### "Could not open the configuration file"
- Check the config file path (default: `/opt/mipsec/mipsec.yaml`)
- Ensure file exists and is readable
- Use `--config` to specify alternative path

### "No tunnels to monitor were configured"
- Provide tunnel names via command-line or config file
- Verify config file is valid YAML list

### VICI Connection Errors
- Ensure StrongSwan is running: `systemctl status strongswan`
- Check VICI socket exists: `ls -l /var/run/charon.vici`
- Verify permissions to access socket

### Tunnels Not Resetting
- Check script has permission to execute `/usr/sbin/ipsec`
- Verify tunnel names match CHILD_SA configuration names
- Run with `--verbose` to see detailed output

## Known Issues & Improvement Suggestions

### Critical Bugs
1. **Line 88 Bug**: Variable name mismatch when removing tunnels from list (uses `childSAName` instead of matched variant)

### Code Quality Improvements
2. PEP 8 violation: Class name should be `TunnelChecker` not `tunnelChecker`
3. Missing type hints throughout
4. Incomplete docstrings
5. Logging setup creates duplicate handlers on re-instantiation
6. Typos: "Reseting" → "Resetting", "occured" → "occurred"

### Functional Enhancements
7. **No Auto-Recovery**: Currently only downs tunnels; should attempt `ipsec up` to restore
8. **No Daemon Mode**: Runs once and exits; could support continuous monitoring
9. **No Retry Logic**: Doesn't retry failed operations
10. **Limited Metrics**: Could output statistics (uptime, failure counts, etc.)
11. **Hardcoded Paths**: `/usr/sbin/ipsec` and default config path should be configurable
12. **No Health Checks**: Could ping through tunnel to verify actual connectivity

### Infrastructure Improvements
13. Add `requirements.txt` for dependency management
14. Add unit and integration tests
15. Add GitHub Actions for CI/CD
16. Better error handling for VICI connection failures
17. Add systemd service file for daemon mode
18. Support for metrics export (Prometheus, InfluxDB, etc.)

## Architecture

```
┌─────────────────┐
│   mipsec.py     │
│  (Main Script)  │
└────────┬────────┘
         │
         ├─── Reads ───► mipsec.yaml (Config)
         │
         ├─── Connects ───► /var/run/charon.vici (VICI Socket)
         │
         ├─── Queries ───► StrongSwan (SA Status)
         │
         └─── Executes ───► /usr/sbin/ipsec down <tunnel>
```

## Contributing

Contributions are welcome! Priority areas:
1. Fix the line 88 variable bug
2. Add type hints
3. Implement auto-recovery (ipsec up)
4. Add daemon mode with continuous monitoring
5. Create unit tests
6. Add systemd service file

## License

[Specify your license here]

## Author

[Specify author/maintainer here]

## See Also

- [StrongSwan Documentation](https://docs.strongswan.org/)
- [VICI Protocol](https://github.com/strongswan/strongswan/blob/master/src/libcharon/plugins/vici/README.md)
- [python-vici](https://github.com/strongswan/strongswan/tree/master/src/libcharon/plugins/vici/python)
