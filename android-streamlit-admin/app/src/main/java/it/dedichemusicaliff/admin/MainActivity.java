package it.dedichemusicaliff.admin;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.webkit.ValueCallback;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String STREAMLIT_URL = "https://dediche-musicali-ff.streamlit.app/";
    private static final int FILE_CHOOSER_REQUEST_CODE = 1001;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(7, 18, 33));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setSupportMultipleWindows(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return request.isForMainFrame() && openWhatsApp(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return openWhatsApp(Uri.parse(url));
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onCreateWindow(WebView view, boolean isDialog,
                    boolean isUserGesture, Message resultMsg) {
                if (!isUserGesture) {
                    return false;
                }
                WebView popup = new WebView(MainActivity.this);
                popup.setWebViewClient(new WebViewClient() {
                    private boolean route(Uri uri) {
                        if ("about".equalsIgnoreCase(uri.getScheme())) {
                            return false;
                        }
                        if (!openWhatsApp(uri)
                                && ("https".equalsIgnoreCase(uri.getScheme())
                                || "http".equalsIgnoreCase(uri.getScheme()))) {
                            try {
                                startActivity(new Intent(Intent.ACTION_VIEW, uri)
                                        .addCategory(Intent.CATEGORY_BROWSABLE));
                            } catch (ActivityNotFoundException error) {
                                Toast.makeText(MainActivity.this,
                                        "Nessuna app disponibile per aprire il link.",
                                        Toast.LENGTH_LONG).show();
                            }
                        }
                        popup.post(popup::destroy);
                        return true;
                    }

                    @Override
                    public boolean shouldOverrideUrlLoading(WebView child, WebResourceRequest request) {
                        return route(request.getUrl());
                    }

                    @Override
                    public boolean shouldOverrideUrlLoading(WebView child, String url) {
                        return route(Uri.parse(url));
                    }
                });
                WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(popup);
                resultMsg.sendToTarget();
                return true;
            }

            @Override
            public boolean onShowFileChooser(
                    WebView webView,
                    ValueCallback<Uri[]> filePathCallback,
                    FileChooserParams fileChooserParams
            ) {
                if (MainActivity.this.filePathCallback != null) {
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }

                MainActivity.this.filePathCallback = filePathCallback;
                Intent intent = fileChooserParams.createIntent();

                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST_CODE);
                    return true;
                } catch (ActivityNotFoundException error) {
                    MainActivity.this.filePathCallback = null;
                    return false;
                }
            }
        });
        webView.loadUrl(STREAMLIT_URL);
    }

    private boolean openWhatsApp(Uri uri) {
        String scheme = uri.getScheme();
        String host = uri.getHost();
        boolean whatsappScheme = "whatsapp".equalsIgnoreCase(scheme);
        boolean whatsappLink = ("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme))
                && ("wa.me".equalsIgnoreCase(host) || "api.whatsapp.com".equalsIgnoreCase(host)
                || "web.whatsapp.com".equalsIgnoreCase(host));
        if (!whatsappScheme && !whatsappLink) {
            return false;
        }

        // Explicit packages avoid relying on Android's verified-link defaults.
        for (String packageName : new String[]{"com.whatsapp", "com.whatsapp.w4b"}) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, uri)
                        .setPackage(packageName).addCategory(Intent.CATEGORY_BROWSABLE));
                return true;
            } catch (ActivityNotFoundException error) {
                // Try the other WhatsApp variant, then the system handler.
            }
        }

        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE));
        } catch (ActivityNotFoundException error) {
            Toast.makeText(this, "Nessuna app disponibile per aprire WhatsApp.", Toast.LENGTH_LONG).show();
        }
        return true;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST_CODE && filePathCallback != null) {
            Uri[] results = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
            return;
        }

        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
