# MIPsec - StrongSwan Tunnel Monitor

A lightweight Python tool for monitoring and managing StrongSwan IPsec tunnels via the VICI (Versatile IKE Control Interface) protocol.

## Overview

MIPsec monitors configured IPsec CHILD_SA tunnels and automatically resets connections that are down. It's designed to work as a monitoring script that can be run periodically via cron or other schedulers.

## Features

- 🔍 **Tunnel Status Monitoring**: Checks if configured tunnels are in INSTALLED state
- 🔄 **Automatic Recovery**: Downs and brings back up tunnels that are detected as non-operational
- 🔁 **Retry Logic**: Configurable retry attempts with exponential backoff for failed operations
- 🤖 **Daemon Mode**: Continuous monitoring with configurable check intervals
- 📝 **Flexible Configuration**: Support for YAML config files and command-line arguments
- 🔧 **Version Compatibility**: Handles both old and new StrongSwan naming conventions
- 📊 **Configurable Logging**: Verbose, normal, and quiet modes
- 🎯 **Custom VICI Socket**: Support for non-standard socket paths
- 📐 **Type Safe**: Full type hints for better IDE support and code quality

## Requirements

- Python 3.6+
- StrongSwan with VICI plugin enabled
- Python packages:
  - `vici` - StrongSwan VICI protocol library
  - `PyYAML` - YAML configuration parsing

## Installation

### 1. Clone or Download

```bash
git clone <repository-url>
cd mipsec
```

### 2. Install Python Dependencies

Using requirements.txt:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install vici PyYAML
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

Run in daemon mode (continuous monitoring):
```bash
./mipsec.py --daemon --interval 60
```

Configure retry behavior:
```bash
./mipsec.py --max-retries 5 --retry-delay 3
```

### Full Options

```
usage: mipsec.py [-h] [--socket SOCKET] [--config CONFIG] [--verbose] [--quiet]
                 [--daemon] [--interval INTERVAL] [--max-retries MAX_RETRIES]
                 [--retry-delay RETRY_DELAY]
                 [tunnels ...]

A script to monitor and reset StrongSwan IPsec tunnels via VICI.

positional arguments:
  tunnels                       The list of CHILD_SAs to monitor and reestablish

optional arguments:
  -h, --help                    show this help message and exit
  --socket SOCKET               If a non-standard path to the VICI socket is used
  --config CONFIG               The path to the optional configuration file (default: /opt/mipsec/mipsec.yaml)
  --verbose                     Print additional information
  --quiet                       Disable any non-error output from the script
  --daemon                      Run in daemon mode with continuous monitoring
  --interval INTERVAL           Interval in seconds between checks in daemon mode (default: 300)
  --max-retries MAX_RETRIES     Maximum number of retries for failed ipsec commands (default: 3)
  --retry-delay RETRY_DELAY     Base delay in seconds between retries, uses exponential backoff (default: 2)
```

## Configuration File Format

The configuration file should be a YAML list of tunnel names (CHILD_SA configuration names):

```yaml
- office-tunnel
- datacenter-vpn
- remote-site
```

## Daemon Mode and Service Integration

### Daemon Mode

Run as a persistent daemon with continuous monitoring:

```bash
./mipsec.py --daemon --interval 60
```

This will check tunnels every 60 seconds and run indefinitely.

### Systemd Service

Create `/etc/systemd/system/mipsec.service`:

```ini
[Unit]
Description=MIPsec StrongSwan Tunnel Monitor
After=network.target strongswan.service
Wants=strongswan.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/mipsec/mipsec.py --daemon --interval 300 --config /opt/mipsec/mipsec.yaml
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable mipsec
sudo systemctl start mipsec
sudo systemctl status mipsec
```

### Cron Integration (Alternative)

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
5. **Reset Down Tunnels**: For any non-operational tunnels:
   - Executes `ipsec down <tunnel>` to tear down the connection
   - Waits 1 second
   - Executes `ipsec up <tunnel>` to re-establish the connection
6. **Retry on Failure**: If ipsec commands fail, retries with exponential backoff (configurable)
7. **Continuous Monitoring** (Daemon Mode): Repeats the check at configured intervals

### Version Compatibility

The tool handles two StrongSwan naming conventions:
- **Older versions**: CHILD_SA name = configuration name
- **Newer versions**: CHILD_SA name = `<config-name>-<ID>` (e.g., `tunnel1-42`)

## Exit Codes

- `0` - Success (all tunnels up)
- `1` - Some tunnels were down (may have been reset), or VICI query error, or no tunnels configured
- `2` - Configuration file format error (not a list)
- `3` - Configuration file contains non-string items
- `4` - Critical error reading configuration file
- `5` - Failed to connect to VICI socket
- `6` - Critical error in daemon mode

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

## Recent Improvements

### Version 2.0 Changes

**Fixed Issues:**
- ✅ Fixed critical bug on line 88 (variable name mismatch when removing tunnels)
- ✅ Renamed class to `TunnelChecker` (PEP 8 compliance)
- ✅ Added complete type hints throughout the codebase
- ✅ Added comprehensive docstrings for all methods
- ✅ Fixed logging handler duplication issue
- ✅ Fixed typos: "Reseting" → "Resetting", "occured" → "occurred"

**New Features:**
- ✅ Auto-Recovery: Now executes `ipsec up` after `ipsec down` to restore tunnels
- ✅ Daemon Mode: Continuous monitoring with configurable intervals
- ✅ Retry Logic: Exponential backoff retry mechanism for failed operations
- ✅ Better Error Handling: Improved VICI connection error handling with informative messages

**Infrastructure:**
- ✅ Added `requirements.txt` for dependency management
- ✅ Documented systemd service integration

### Future Improvement Suggestions

**Functional Enhancements:**
1. **Health Checks**: Ping through tunnel to verify actual connectivity (not just SA state)
2. **Metrics Export**: Support for Prometheus, InfluxDB, or other monitoring systems
3. **Configurable Paths**: Make `/usr/sbin/ipsec` path configurable
4. **Notification System**: Email/webhook alerts when tunnels go down
5. **Multiple Check Strategies**: Support for active probing, not just passive SA monitoring

**Infrastructure:**
6. Add unit and integration tests
7. Add GitHub Actions for CI/CD
8. Create pre-built packages (deb, rpm)
9. Add configuration validation tool
10. Support for multiple configuration file formats (JSON, TOML)

## Architecture

```
┌─────────────────────────┐
│     mipsec.py           │
│   (Main Script)         │
│  ┌─────────────────┐    │
│  │ TunnelChecker   │    │
│  │ - Type Safe     │    │
│  │ - Retry Logic   │    │
│  │ - Auto-Recovery │    │
│  └─────────────────┘    │
└────────┬────────────────┘
         │
         ├─── Reads ────────────────► mipsec.yaml (Config)
         │
         ├─── Connects ─────────────► /var/run/charon.vici (VICI Socket)
         │
         ├─── Queries ──────────────► StrongSwan (SA Status via VICI)
         │
         └─── For Down Tunnels:
              ├─── Execute ────────► /usr/sbin/ipsec down <tunnel>
              ├─── Wait 1s
              ├─── Execute ────────► /usr/sbin/ipsec up <tunnel>
              └─── Retry on Failure (Exponential Backoff)

         ┌──────────────────┐
         │  Daemon Mode     │
         │  (Optional)      │
         │  Repeats every   │
         │  N seconds       │
         └──────────────────┘
```

## Contributing

Contributions are welcome! Priority areas for future development:
1. **Testing**: Add unit and integration tests
2. **Health Checks**: Implement active connectivity verification (ping through tunnel)
3. **Metrics Export**: Add Prometheus/InfluxDB support
4. **Notification System**: Email/webhook alerts for tunnel failures
5. **CI/CD**: Set up GitHub Actions for automated testing and releases
6. **Packaging**: Create deb/rpm packages for easy installation

## License

[Specify your license here]

## Author

[Specify author/maintainer here]

## See Also

- [StrongSwan Documentation](https://docs.strongswan.org/)
- [VICI Protocol](https://github.com/strongswan/strongswan/blob/master/src/libcharon/plugins/vici/README.md)
- [python-vici](https://github.com/strongswan/strongswan/tree/master/src/libcharon/plugins/vici/python)
