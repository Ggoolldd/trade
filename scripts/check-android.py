"""Run actual Android Gradle checks; missing scaffold is blocked, never success."""

import platform
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
android = root / "android"
wrapper = android / ("gradlew.bat" if platform.system() == "Windows" else "gradlew")
required = [
    wrapper,
    android / "gradle/wrapper/gradle-wrapper.jar",
    android / "gradle/wrapper/gradle-wrapper.properties",
]
if any(not path.is_file() for path in required) or not any(
    (android / name).is_file() for name in ["settings.gradle.kts", "settings.gradle"]
):
    print("BLOCKED: real Android Gradle scaffold is absent (TAI-129); no Gradle PASS claimed")
    sys.exit(2)
command = [str(wrapper)] if platform.system() == "Windows" else ["bash", str(wrapper)]
result = subprocess.run(command + ["--no-daemon", "--console=plain", "test", "lint", "assembleDebug"], cwd=android)
sys.exit(result.returncode)
