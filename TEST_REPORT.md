# Furukawa FITELnet Driver - Official Test Report

- Date: 2026-02-20
- Device: Furukawa FITELnet F220 (192.168.100.40)
- Driver: `netmiko/furukawa/furukawa_fitelnet.py`
- Test suite: netmiko official tests (`tests/test_netmiko_*.py`)

## Test Environment

| Connection | Runner | Target | Details |
|---|---|---|---|
| SSH | Linux (192.168.100.50) | FITELnet (192.168.100.40:22) | Ubuntu 24.04, Python 3.12.3 |
| Telnet | Linux (192.168.100.50) | FITELnet (192.168.100.40:23) | Ubuntu 24.04, Python 3.12.3 |
| Serial | Windows (COM4) | FITELnet (console) | Windows 11, Python 3.12.10, 9600baud |

Note: Serial tests run on Windows because the serial cable (USB-serial adapter)
is physically connected to the Windows host. The Ubuntu machine is a Hyper-V VM
and cannot access the host's USB serial port via passthrough.

## Results Summary

### SSH (furukawa_fitelnet)

| Test Suite | Passed | Skipped | Failed | Error |
|---|---|---|---|---|
| Autodetect | 1 | 0 | 0 | 0 |
| Show | 13 | 12 | 0 | 0 |
| Config | 11 | 2 | 0 | 0 |
| Save | 2 | 0 | 0 | 0 |
| **Total** | **27** | **14** | **0** | **0** |

### Telnet (furukawa_fitelnet_telnet)

| Test Suite | Passed | Skipped | Failed | Error |
|---|---|---|---|---|
| Show | 13 | 12 | 0 | 0 |
| Config | 11 | 2 | 0 | 0 |
| Save | 2 | 0 | 0 | 0 |
| **Total** | **26** | **14** | **0** | **0** |

Note: Autodetect is SSH-only (uses `SSHDetect` class).

### Serial (furukawa_fitelnet_serial)

| Test Suite | Passed | Skipped | Failed | Error |
|---|---|---|---|---|
| Show | 12 | 12 | 0 | 1 |
| Config | 11 | 2 | 0 | 0 |
| Save | 2 | 0 | 0 | 0 |
| **Total** | **25** | **14** | **0** | **1** |

Note: The 1 error is `test_ssh_connect_cm` (see "Known Limitations" below).

### Grand Total (All Connections)

| | Passed | Skipped | Failed | Error |
|---|---|---|---|---|
| **Total** | **78** | **42** | **0** | **1** |

## Skipped Tests - Reasons

### Show Tests (12 skipped per connection)

| Test | Reason | Category |
|---|---|---|
| `test_failed_key` | SSH key auth not configured | Infra: requires SSH key setup |
| `test_send_command_timing_no_cmd_verify` | `fast_cli=True` (default) | By design: cmd_verify=False test only runs when fast_cli=False |
| `test_send_command_no_cmd_verify` | `fast_cli=True` (default) | By design: same as above |
| `test_complete_on_space_disabled` | Hardcoded for Juniper/Nokia only | Not applicable: test code only supports juniper_junos, nokia_sros |
| `test_send_command_textfsm` | No TextFSM templates for FITELnet | Not applicable: ntc-templates has no furukawa_fitelnet entries |
| `test_send_command_ttp` | No TTP templates for FITELnet | Not applicable: test only supports cisco_ios |
| `test_send_command_genie` | Genie is Cisco-only | Not applicable: PyATS/Genie only supports Cisco platforms |
| `test_send_multiline_timing` | Hardcoded for Cisco IOS/XE only | Not applicable: uses Cisco-specific interactive ping |
| `test_send_multiline` | Hardcoded for Cisco IOS/XE only | Not applicable: same as above |
| `test_send_multiline_prompt` | Hardcoded for Cisco IOS/XE only | Not applicable: same as above |
| `test_send_multiline_simple` | Hardcoded for Cisco IOS/XE only | Not applicable: same as above |
| `test_disconnect_no_enable` | Hardcoded for Cisco IOS only | Not applicable: test code only supports cisco_ios |

### Config Tests (2 skipped per connection)

| Test | Reason | Category |
|---|---|---|
| `test_banner` | FITELnet does not support `banner login` command | Not applicable: `banner login` returns `<ERROR> Unrecognized command` |
| `test_global_cmd_verify` | Depends on banner support | Not applicable: same as above |

## Known Limitations

### Serial: test_ssh_connect_cm ERROR

The `test_ssh_connect_cm` test creates a second connection using a context manager.
Serial ports (COM4) have exclusive access -- only one process can open the port at a
time. Since the module-scoped `net_connect` fixture already holds COM4 open, the
context manager fixture cannot open a second connection. This is a physical constraint
of serial communication, not a driver bug. All other serial tests (12 passed) use the
single module-scoped connection and work correctly.

## Test Configuration Files

Located in `.vscode/` (copied to `tests/etc/` at test time):

- `test_devices.yml` - Device connection parameters for SSH/Telnet/Serial
- `commands.yml` - Commands and expected patterns for each device_type
- `responses.yml` - Expected response strings for validation
- `fitelnet_config.txt` - Config file for `test_config_from_file` test
- `setup_linux_test.py` - Test runner script (sets up Linux env, runs all tests)

## Raw Test Output

See `test_output.txt` in the same directory for the complete pytest output.
