"""Set up Linux test environment and run official netmiko tests for FITELnet.

SSH/Telnet tests: Linux (192.168.100.50) -> FITELnet (192.168.100.40)
Serial tests:     Windows (COM4)         -> FITELnet (console)

Autodetect is SSH-only (SSHDetect class).
"""

import paramiko
import os
import subprocess
import sys
import time

LINUX_HOST = "192.168.100.50"
LINUX_USER = "ubuntu"
LINUX_PASS = "admin"
REMOTE_DIR = "/home/ubuntu/netmiko_test"
NETMIKO_ROOT = r"I:\netmiko"
VSCODE_DIR = os.path.join(NETMIKO_ROOT, ".vscode")


def exec_cmd(ssh, cmd, timeout=60):
    """Execute command on remote Linux and return output."""
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip().encode("ascii", errors="replace").decode("ascii"))
    if err.strip() and rc != 0:
        print(f"  [stderr] {err.rstrip().encode('ascii', errors='replace').decode('ascii')}")
    return out, err, rc


def setup_linux(ssh):
    """Install dependencies and copy source to Linux. Return poetry_bin path."""
    print("=" * 60)
    print("1. Installing pip and poetry on Linux")
    print("=" * 60)
    exec_cmd(
        ssh,
        "echo admin | sudo -S apt-get update -qq 2>/dev/null "
        "&& echo admin | sudo -S apt-get install -y -qq python3-pip python3-venv "
        "> /dev/null 2>&1 && echo 'apt install done'",
        timeout=120,
    )
    exec_cmd(
        ssh,
        "pip3 install --user --break-system-packages poetry 2>/dev/null "
        "|| pip3 install --user poetry 2>&1 | tail -3",
        timeout=120,
    )

    print()
    print("=" * 60)
    print("2. Copying netmiko source to Linux")
    print("=" * 60)
    exec_cmd(ssh, f"rm -rf {REMOTE_DIR}")
    exec_cmd(ssh, f"mkdir -p {REMOTE_DIR}")

    sftp = ssh.open_sftp()

    dirs_to_copy = ["netmiko", "tests"]
    files_to_copy = [
        "pyproject.toml", "setup.cfg", "README.md", "LICENSE", "MANIFEST.in",
    ]

    def sftp_makedirs(sftp_conn, remote_dir):
        dirs = []
        while True:
            try:
                sftp_conn.stat(remote_dir)
                break
            except FileNotFoundError:
                dirs.append(remote_dir)
                remote_dir = os.path.dirname(remote_dir)
        for d in reversed(dirs):
            sftp_conn.mkdir(d)

    def copy_tree(local_base, remote_base, dir_name):
        local_dir = os.path.join(local_base, dir_name)
        for root, subdirs, filenames in os.walk(local_dir):
            subdirs[:] = [
                d for d in subdirs
                if d not in ("__pycache__", ".git", ".venv", ".pytest_cache", ".mypy_cache")
            ]
            rel_path = os.path.relpath(root, local_base).replace("\\", "/")
            remote_path = f"{remote_base}/{rel_path}"
            try:
                sftp.stat(remote_path)
            except FileNotFoundError:
                sftp_makedirs(sftp, remote_path)
            for fname in filenames:
                if fname.endswith((".pyc", ".pyo")):
                    continue
                sftp.put(os.path.join(root, fname), f"{remote_path}/{fname}")

    for d in dirs_to_copy:
        print(f"  Copying {d}/...")
        copy_tree(NETMIKO_ROOT, REMOTE_DIR, d)

    for f in files_to_copy:
        local_path = os.path.join(NETMIKO_ROOT, f)
        if os.path.exists(local_path):
            print(f"  Copying {f}")
            sftp.put(local_path, f"{REMOTE_DIR}/{f}")

    print()
    print("=" * 60)
    print("3. Creating test config files")
    print("=" * 60)
    test_etc_dir = f"{REMOTE_DIR}/tests/etc"
    try:
        sftp.stat(test_etc_dir)
    except FileNotFoundError:
        sftp_makedirs(sftp, test_etc_dir)

    for cfg_file in ["test_devices.yml", "commands.yml", "responses.yml", "fitelnet_config.txt"]:
        local_f = os.path.join(VSCODE_DIR, cfg_file)
        if os.path.exists(local_f):
            sftp.put(local_f, f"{test_etc_dir}/{cfg_file}")
            print(f"  Copied {cfg_file} -> tests/etc/{cfg_file}")

    sftp.close()

    print()
    print("=" * 60)
    print("4. Installing netmiko dependencies")
    print("=" * 60)
    poetry_bin = "/home/ubuntu/.local/bin/poetry"
    exec_cmd(ssh, f"cd {REMOTE_DIR} && {poetry_bin} install 2>&1 | tail -5", timeout=300)
    return poetry_bin


def run_contributing_checks(ssh, poetry_bin):
    """Run CONTRIBUTING.md required checks: black, pylama, mypy, unit tests."""
    print()
    print("=" * 60)
    print("5. CONTRIBUTING.md Checks (black, pylama, mypy, unit tests)")
    print("=" * 60)
    cd = f"cd {REMOTE_DIR}"

    checks = [
        ("black --check .", f"{cd} && {poetry_bin} run black --check . 2>&1"),
        ("pylama .", f"{cd} && {poetry_bin} run pylama . 2>&1"),
        ("mypy netmiko/", f"{cd} && {poetry_bin} run mypy netmiko/ 2>&1"),
        (
            "py.test tests/unit/",
            f"{cd} && PATH=$PATH:$HOME/.local/bin "
            f"{poetry_bin} run py.test tests/unit/ -q 2>&1",
        ),
    ]
    results = {}
    for label, cmd in checks:
        print()
        print(f"  --- {label} ---")
        out, err, rc = exec_cmd(ssh, cmd, timeout=180)
        results[label] = (out, err, rc)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"  Result: {status} (exit code {rc})")
    return results


def run_linux_suite(ssh, poetry_bin, test_device, test_file, label):
    """Run a single test suite on Linux. Return (output, returncode)."""
    print()
    print("-" * 40)
    print(f"{label} ({test_device})")
    print("-" * 40)
    pytest_base = (
        f"cd {REMOTE_DIR}/tests && "
        f"PYTHONPATH={REMOTE_DIR}/tests "
        f"{poetry_bin} run py.test -s -v"
    )
    out, err, rc = exec_cmd(
        ssh,
        f"{pytest_base} {test_file} --test_device {test_device} 2>&1",
        timeout=180,
    )
    return out, rc


def setup_local_test_etc():
    """Copy .vscode YAML configs to tests/etc/ for local Windows testing."""
    etc_dir = os.path.join(NETMIKO_ROOT, "tests", "etc")
    os.makedirs(etc_dir, exist_ok=True)
    for cfg_file in ["test_devices.yml", "commands.yml", "responses.yml", "fitelnet_config.txt"]:
        src = os.path.join(VSCODE_DIR, cfg_file)
        dst = os.path.join(etc_dir, cfg_file)
        if os.path.exists(src):
            with open(src, "rb") as f_in:
                with open(dst, "wb") as f_out:
                    f_out.write(f_in.read())


def run_local_suite(test_device, test_file, label):
    """Run a single test suite locally on Windows. Return (output, returncode)."""
    print()
    print("-" * 40)
    print(f"{label} ({test_device})")
    print("-" * 40)
    tests_dir = os.path.join(NETMIKO_ROOT, "tests")
    cmd = [
        sys.executable, "-m", "pytest", "-s", "-v",
        os.path.join(tests_dir, test_file),
        "--test_device", test_device,
    ]
    print(f"  $ {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = tests_dir
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=tests_dir, env=env)
    combined = proc.stdout + proc.stderr
    print(combined.rstrip())
    return combined, proc.returncode


def main():
    # --- Setup Linux ---
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(LINUX_HOST, username=LINUX_USER, password=LINUX_PASS, timeout=10)
    poetry_bin = setup_linux(ssh)

    # --- CONTRIBUTING.md checks (run first) ---
    run_contributing_checks(ssh, poetry_bin)

    suites = [
        ("Show Tests", "test_netmiko_show.py"),
        ("Config Tests", "test_netmiko_config.py"),
        ("Save Tests", "test_netmiko_save.py"),
    ]

    # --- SSH tests (Linux -> FITELnet) ---
    print()
    print("=" * 60)
    print("6. SSH Tests (Linux -> FITELnet)")
    print("=" * 60)
    run_linux_suite(ssh, poetry_bin, "furukawa_fitelnet",
                    "test_netmiko_autodetect.py", "Autodetect Test")
    for label, test_file in suites:
        run_linux_suite(ssh, poetry_bin, "furukawa_fitelnet", test_file, label)

    # --- Telnet tests (Linux -> FITELnet) ---
    print()
    print("=" * 60)
    print("7. Telnet Tests (Linux -> FITELnet)")
    print("=" * 60)
    for label, test_file in suites:
        run_linux_suite(ssh, poetry_bin, "furukawa_fitelnet_telnet", test_file, label)

    ssh.close()

    # --- Serial tests (Windows COM4 -> FITELnet) ---
    print()
    print("=" * 60)
    print("8. Serial Tests (Windows COM4 -> FITELnet)")
    print("=" * 60)
    setup_local_test_etc()
    for label, test_file in suites:
        run_local_suite("furukawa_fitelnet_serial", test_file, label)

    print()
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
