plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "ru.prostokvn.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "ru.prostokvn.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 8
        versionName = "0.1.7-test"
    }
    // Ship one native VPN engine per CPU architecture instead of all four in every APK.
    // Builds: app-arm64-v8a-debug.apk (current Samsung/most phones), plus
    // armeabi-v7a, x86 and x86_64 variants for older phones and emulators.
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
            isUniversalApk = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    testOptions {
        unitTests.all {
            it.systemProperty("gwzhub.assets", file("src/main/assets/routing").absolutePath)
            it.systemProperty("kvn.validation.json", file("build/ci-validation/vpn-auto.json").absolutePath)
        }
    }
}
dependencies {
    // The pinned AAR is fetched by scripts/fetch_libbox.py and verified by SHA-256.
    implementation(files("libs/libbox.aar"))
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
