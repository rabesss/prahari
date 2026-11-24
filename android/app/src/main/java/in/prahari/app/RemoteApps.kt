package `in`.prahari.app

import android.content.pm.PackageManager
import android.os.Build

/**
 * Screen-sharing and remote-control apps that scammers ask victims to install. Each package is
 * declared in AndroidManifest.xml <queries>, so no QUERY_ALL_PACKAGES permission is needed, and
 * android/tools/test_remote_apps.py keeps the two lists equal. Package IDs were checked against
 * their Google Play listings on 24 Nov 2026; RustDesk is not on Play, so its ID comes from its
 * F-Droid listing and upstream applicationId. The result is shown on screen only: it is never
 * logged, stored in History or sent anywhere.
 */
internal object RemoteApps {
    val APPS: Map<String, String> = linkedMapOf(
        "com.anydesk.anydeskandroid" to "AnyDesk",
        "com.teamviewer.quicksupport.market" to "TeamViewer QuickSupport",
        "com.teamviewer.host.market" to "TeamViewer Host",
        "com.teamviewer.teamviewer.market.mobile" to "TeamViewer",
        "com.carriez.flutter_hbb" to "RustDesk",
        "com.sand.airdroid" to "AirDroid",
        "com.sand.airsos" to "AirDroid Remote Support",
        "com.sand.aircast" to "AirDroid Cast",
    )

    /** Display names of the listed apps that are installed, in list order. */
    fun installed(pm: PackageManager): List<String> = APPS.mapNotNull { (pkg, name) ->
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                pm.getPackageInfo(pkg, PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(pkg, 0)
            }
            name
        } catch (_: PackageManager.NameNotFoundException) {
            null
        } catch (_: Throwable) {
            null
        }
    }
}
