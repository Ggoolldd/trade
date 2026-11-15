# Android CI application

TAI-024 introduces a real minimal Kotlin/Compose application to make Android CI
executable before TAI-129. This is an intentional prerequisite adjustment requested
by the owner on 2026-11-15. TAI-129 remains pending: Hilt, lifecycle/client integration
and product functionality are not claimed here.

The initial app displays PAPER/unavailable only. It requests no permissions,
contains no API client, secrets, authentication or order controls. Manifest safety
is tested on the JVM. No broker or backend is contacted.

Pinned toolchain: AGP 8.11.1, Gradle 8.13, Kotlin/Compose compiler 2.1.20,
Compose BOM 2025.04.01, JDK 17, compile/target SDK 35 and min SDK 26.
Versions are deliberately pinned, not described as latest. Dependencies are
resolved from Google, Maven Central and the official Gradle plugin portal.
Gradle distribution checksum is pinned in wrapper properties. The checked-in wrapper
JAR matches Gradle's official SHA256:
81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f.

Set JAVA_HOME to JDK 17 and ANDROID_HOME to your Android SDK (platform 35,
build-tools 35.0.0 installed). Local SDK paths go only in ignored local.properties.
From the repository root:

```text
python scripts/check-android.py
```

This executes actual Gradle test, lint and assembleDebug. Test XML and lint reports
are in app/build; debug APK is in app/build/outputs/apk/debug. Build outputs,
caches, SDK paths and debug signing keys are ignored. No release signing is set up.
Android UI/device testing is not covered by these JVM/build checks.

Official compatibility references:
[AGP 8.11](https://developer.android.com/build/releases/agp-8-11-0-release-notes),
[Compose compiler plugin](https://developer.android.com/develop/ui/compose/setup-compose-dependencies-and-compiler),
[Gradle wrapper](https://docs.gradle.org/8.13/userguide/gradle_wrapper.html).
