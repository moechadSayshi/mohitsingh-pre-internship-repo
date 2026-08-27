import shutil
import socket
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
PORT = 2020

REQUIRED_TOOLS = {
    "node": ["node", "--version"],
    "yarn": ["yarn", "--version"],
    "docker": ["docker", "--version"],
}


def status(message):
    print(f"\n{'=' * 60}")
    print(message)
    print(f"{'=' * 60}")


def success(message):
    print(f"[SUCCESS] {message}")


def error(message):
    print(f"[ERROR] {message}", file=sys.stderr)


def run_command(command, description):
    print(f"\n[RUNNING] {description}")

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        error(f"Command not found: {command[0]}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        error(
            f"{description} failed with exit code {exc.returncode}."
        )
        sys.exit(exc.returncode)


def verify_project_root():
    status("Checking project directory")

    required_files = [
        ".git",
        "package.json",
        ".nvmrc",
        ".yarnrc.yml",
    ]

    missing = [
        filename
        for filename in required_files
        if not (PROJECT_ROOT / filename).exists()
    ]

    if missing:
        error("This script must be run from the CRM project.")
        error("Missing: " + ", ".join(missing))
        sys.exit(1)

    success("CRM project directory verified.")


def check_tools():
    status("Checking required tools")

    for tool, command in REQUIRED_TOOLS.items():
        if shutil.which(tool) is None:
            error(f"{tool} is not installed or not in PATH.")
            sys.exit(1)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        version = result.stdout.strip() or result.stderr.strip()
        print(f"[OK] {tool}: {version}")


def check_docker_access():
    status("Checking Docker access")

    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        success("Docker is available.")
    except subprocess.CalledProcessError:
        error(
            "Docker is installed but the current user "
            "cannot access the Docker daemon."
        )
        error(
            "Make sure Docker is running and your user "
            "has Docker group permissions."
        )
        sys.exit(1)


def install_dependencies():
    status("Installing project dependencies")

    run_command(
        ["yarn", "install"],
        "Installing Yarn dependencies",
    )

    success("Project dependencies installed.")


def start_docker_services():
    status("Starting Twenty Docker services")

    run_command(
        ["yarn", "twenty", "docker:start"],
        "Starting Docker services",
    )

    success("Twenty Docker services started.")


def check_port():
    status(f"Checking port {PORT}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        result = sock.connect_ex(("127.0.0.1", PORT))
    finally:
        sock.close()

    if result == 0:
        success(f"Port {PORT} is already responding.")
    else:
        print(
            f"[INFO] Port {PORT} is not currently responding."
        )


def start_development_server():
    status("Starting Twenty development server")

    print(f"\nApplication URL: http://localhost:{PORT}")
    print("Press Ctrl+C to stop the development server.\n")

    try:
        subprocess.run(
            ["yarn", "twenty", "dev"],
            cwd=PROJECT_ROOT,
            check=True,
        )
    except KeyboardInterrupt:
        print("\nDevelopment server stopped by user.")
    except subprocess.CalledProcessError as exc:
        error(
            f"Development server exited with code {exc.returncode}."
        )
        sys.exit(exc.returncode)


def main():
    try:
        print("\nStarting CRM automated setup...")

        verify_project_root()
        check_tools()
        check_docker_access()
        install_dependencies()
        start_docker_services()
        check_port()
        start_development_server()

    except KeyboardInterrupt:
        print("\nSetup interrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
