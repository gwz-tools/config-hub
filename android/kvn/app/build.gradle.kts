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
        versionCode = 15
        versionName = "0.1.14-xray-test"
    }
    // Experimental Xray proof-of-concept is ARM64 ONLY, matching test Samsung.
    // Restore other ABI splits after confirming native Xray on a real device.
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a")
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
            it.systemProperty("kvn.xray.validation.json", file("build/ci-validation/xray-kvn.json").absolutePath)
        }
    }
}
dependencies {
    // Official AndroidLibXrayLite 26.9.30, SHA-256 pinned in fetch_libv2ray.py.
    // Do NOT combine libbox and libv2ray: both bundle incompatible go.Seq classes.
    implementation(files("libs/libv2ray.aar"))
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
