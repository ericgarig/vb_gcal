import shutil
import subprocess


class OnePassword:
    def __init__(self):
        # Check if 1Password CLI is installed
        self.op_path = shutil.which("op")

    def get_secret(self, reference: str) -> str:
        """Fetches a secret from 1Password given a secret reference."""
        if not self.op_path:
            raise EnvironmentError(
                "1Password CLI ('op') not found in PATH. "
                "Install it via 'brew install 1password-cli' and enable CLI integration in the 1Password App."
            )

        if not reference or not reference.startswith("op://"):
            return ""

        try:
            result = subprocess.run([self.op_path, "read", reference], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f">>> ERROR fetching from 1Password: {e.stderr}")
            return ""
