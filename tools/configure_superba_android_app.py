from pathlib import Path
import shutil

from PIL import Image, ImageDraw


APP_DIR = Path("D:/torneo-Subbuteo-webapp/android-camp-superba-26-27")
ICON_SOURCE = Path("C:/Users/leonardo/AppData/Local/Temp/codex-clipboard-970fe741-8c32-4949-a98d-9db23fc251af.png")
URL = "https://torneo-subbuteo-superba-ita-all-db.streamlit.app/?torneo=CampionatoSuperba_26_27"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_icon() -> None:
    out = APP_DIR / "app/src/main/res/drawable-nodpi/ic_launcher_superba.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    source = Image.open(ICON_SOURCE).convert("RGBA")
    size = min(source.size)
    left = (source.width - size) // 2
    top = (source.height - size) // 2
    image = source.crop((left, top, left + size, top + size)).resize((512, 512), Image.Resampling.LANCZOS)

    mask = Image.new("L", (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((8, 8, 504, 504), radius=96, fill=255)

    background = Image.new("RGBA", (512, 512), (13, 34, 18, 255))
    background.alpha_composite(image)
    background.putalpha(mask)
    background.save(out)


def main() -> None:
    old_java = APP_DIR / "app/src/main/java/it/dedichemusicaliff/admin/MainActivity.java"
    new_java = APP_DIR / "app/src/main/java/it/torneosubbuteo/superba/MainActivity.java"
    if old_java.exists():
        old_java.unlink()
    new_java.parent.mkdir(parents=True, exist_ok=True)

    write(
        APP_DIR / "settings.gradle",
        """pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Camp Superba 26 27"
include ":app"
""",
    )

    write(
        APP_DIR / "app/build.gradle",
        """plugins {
    id "com.android.application"
}

android {
    namespace "it.torneosubbuteo.superba"
    compileSdk 36

    defaultConfig {
        applicationId "it.torneosubbuteo.superba"
        minSdk 23
        targetSdk 36
        versionCode 1
        versionName "1.0"
    }
}
""",
    )

    write(
        APP_DIR / "app/src/main/AndroidManifest.xml",
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:icon="@drawable/ic_launcher_superba"
        android:label="@string/app_name"
        android:roundIcon="@drawable/ic_launcher_superba"
        android:supportsRtl="true"
        android:theme="@style/AppTheme">
        <activity
            android:name=".MainActivity"
            android:configChanges="keyboardHidden|orientation|screenSize"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
""",
    )

    write(APP_DIR / "app/src/main/res/values/strings.xml", """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Camp Superba 26/27</string>
</resources>
""")

    write(
        new_java,
        f"""package it.torneosubbuteo.superba;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {{
    private static final String STREAMLIT_URL = "{URL}";
    private static final int FILE_CHOOSER_REQUEST_CODE = 1001;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(13, 34, 18));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient() {{
            @Override
            public boolean onShowFileChooser(
                    WebView webView,
                    ValueCallback<Uri[]> filePathCallback,
                    FileChooserParams fileChooserParams
            ) {{
                if (MainActivity.this.filePathCallback != null) {{
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }}

                MainActivity.this.filePathCallback = filePathCallback;
                Intent intent = fileChooserParams.createIntent();

                try {{
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST_CODE);
                    return true;
                }} catch (ActivityNotFoundException error) {{
                    MainActivity.this.filePathCallback = null;
                    return false;
                }}
            }}
        }});
        webView.loadUrl(STREAMLIT_URL);
    }}

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {{
        if (requestCode == FILE_CHOOSER_REQUEST_CODE && filePathCallback != null) {{
            Uri[] results = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
            return;
        }}

        super.onActivityResult(requestCode, resultCode, data);
    }}

    @Override
    public void onBackPressed() {{
        if (webView != null && webView.canGoBack()) {{
            webView.goBack();
            return;
        }}
        super.onBackPressed();
    }}

    @Override
    protected void onDestroy() {{
        if (webView != null) {{
            webView.destroy();
            webView = null;
        }}
        super.onDestroy();
    }}
}}
""",
    )

    write(
        APP_DIR / "README.md",
        f"""# Camp Superba 26/27 Android

Mini app Android WebView per aprire:

`{URL}`

Titolo app: `Camp Superba 26/27`

La WebView ha JavaScript, cookie, storage locale e selettore file abilitati.
""",
    )

    old_package = APP_DIR / "app/src/main/java/it/dedichemusicaliff"
    if old_package.exists():
        shutil.rmtree(old_package)

    make_icon()
    print(APP_DIR)


if __name__ == "__main__":
    main()
