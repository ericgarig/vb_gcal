import platform


def get_platform_key() -> str:
    """
    Maps the current system's OS and architecture to a standardized
    key used for binary downloads (e.g., Chromedriver).
    """
    os_name = platform.system().lower()
    machine = platform.machine().lower()

    if os_name == "linux":
        return "linux64"

    if os_name == "darwin":
        # Apple Silicon vs Intel
        return "mac-arm64" if "arm" in machine else "mac-x64"

    if os_name == "windows":
        # Chrome uses win64 for most modern 64-bit systems
        return "win64" if "64" in machine or "amd64" in machine else "win32"

    raise RuntimeError(f"Unsupported Platform: {os_name} {machine}")
