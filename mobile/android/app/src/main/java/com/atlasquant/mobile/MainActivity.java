package com.atlasquant.mobile;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String PREFS = "atlasquant_mobile";
    private static final String PREF_URL = "server_url";

    private EditText urlInput;
    private TextView status;
    private ProgressBar progress;
    private WebView webView;
    private LinearLayout connectionPanel;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        configureWebView();

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String savedUrl = prefs.getString(PREF_URL, "");
        if (isLoopbackAddress(savedUrl)) {
            prefs.edit().remove(PREF_URL).apply();
            savedUrl = "";
        }
        urlInput.setText(savedUrl);
        showAcademy();
    }

    private TextView makeText(String value, int sizeSp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(sizeSp);
        t.setTextColor(color);
        t.setPadding(0, 4, 0, 4);
        if (bold) {
            t.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        }
        return t;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(5, 15, 28));
        root.setPadding(24, 20, 24, 18);

        TextView brand = makeText("ATLASQUANT", 27, Color.rgb(76, 192, 255), true);
        root.addView(brand);

        TextView subtitle = makeText("Mobile Standalone • Academy offline + conexão privada", 14, Color.rgb(166, 192, 211), false);
        root.addView(subtitle);

        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setPadding(0, 14, 0, 10);

        Button academyButton = new Button(this);
        academyButton.setText("Academy Offline");
        academyButton.setOnClickListener(v -> showAcademy());
        nav.addView(academyButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button desktopButton = new Button(this);
        desktopButton.setText("Conectar ao Desktop");
        desktopButton.setOnClickListener(v -> showDesktopConnection());
        LinearLayout.LayoutParams desktopParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        desktopParams.setMargins(10, 0, 0, 0);
        nav.addView(desktopButton, desktopParams);

        root.addView(nav);

        connectionPanel = new LinearLayout(this);
        connectionPanel.setOrientation(LinearLayout.VERTICAL);
        connectionPanel.setPadding(0, 18, 0, 14);

        TextView help = makeText(
            "No Windows, inicie o AtlasQuant em [9] Modo celular — Wi‑Fi local. " +
            "Digite abaixo o endereço mostrado pelo launcher.",
            15, Color.WHITE, false
        );
        connectionPanel.addView(help);

        urlInput = new EditText(this);
        urlInput.setSingleLine(true);
        urlInput.setHint("http://192.168.1.10:8501");
        urlInput.setTextColor(Color.WHITE);
        urlInput.setHintTextColor(Color.rgb(120, 145, 165));
        urlInput.setBackgroundColor(Color.rgb(16, 45, 70));
        urlInput.setPadding(18, 12, 18, 12);
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        inputParams.setMargins(0, 14, 0, 10);
        connectionPanel.addView(urlInput, inputParams);

        Button connectButton = new Button(this);
        connectButton.setText("Conectar ao AtlasQuant");
        connectButton.setOnClickListener(v -> connect(urlInput.getText().toString()));
        connectionPanel.addView(connectButton);

        status = makeText("Aguardando endereço do AtlasQuant.", 13, Color.rgb(166, 192, 211), false);
        connectionPanel.addView(status);

        progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        connectionPanel.addView(progress);

        root.addView(connectionPanel);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(5, 15, 28));
        LinearLayout.LayoutParams webParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        );
        root.addView(webView, webParams);

        setContentView(root);
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
                status.setText("Conectando…");
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
                    status.setText("Conectado.");
                    connectionPanel.setVisibility(View.GONE);
                }
            }

            @Override
            public void onReceivedError(
                WebView view,
                WebResourceRequest request,
                WebResourceError error
            ) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    progress.setVisibility(View.GONE);
                    connectionPanel.setVisibility(View.VISIBLE);
                    status.setText("Não foi possível conectar. Confira o endereço e o Wi‑Fi.");
                }
            }
        });
    }

    private void showAcademy() {
        connectionPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        status.setText("Academy offline.");
        webView.loadUrl("file:///android_asset/academy.html");
    }

    private void showDesktopConnection() {
        webView.stopLoading();
        webView.setVisibility(View.GONE);
        connectionPanel.setVisibility(View.VISIBLE);
        status.setText("Digite o endereço mostrado no Windows. Não use localhost no celular.");
    }

    private boolean isLoopbackAddress(String rawUrl) {
        String value = rawUrl == null ? "" : rawUrl.trim();
        if (value.isEmpty()) {
            return false;
        }
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://" + value;
        }
        try {
            String host = Uri.parse(value).getHost();
            if (host == null) {
                return false;
            }
            host = host.toLowerCase();
            return host.equals("localhost")
                || host.equals("127.0.0.1")
                || host.equals("0.0.0.0")
                || host.equals("::1");
        } catch (Exception ignored) {
            return false;
        }
    }

    private void connect(String rawUrl) {
        String url = rawUrl == null ? "" : rawUrl.trim();
        if (url.isEmpty()) {
            Toast.makeText(this, "Digite o endereço mostrado no Windows.", Toast.LENGTH_LONG).show();
            return;
        }
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://" + url;
        }
        if (!url.matches("^https?://[^\\s]+$")) {
            Toast.makeText(this, "Endereço inválido.", Toast.LENGTH_LONG).show();
            return;
        }
        if (isLoopbackAddress(url)) {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(PREF_URL).apply();
            urlInput.setText("");
            status.setText("No celular, localhost aponta para o próprio telefone. Use o IP mostrado no Windows.");
            Toast.makeText(
                this,
                "Não use localhost. Use algo como http://192.168.1.10:8501",
                Toast.LENGTH_LONG
            ).show();
            return;
        }

        getSharedPreferences(PREFS, MODE_PRIVATE)
            .edit()
            .putString(PREF_URL, url)
            .apply();

        connectionPanel.setVisibility(View.VISIBLE);
        webView.setVisibility(View.VISIBLE);
        status.setText("Conectando…");
        webView.loadUrl(url);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else if (connectionPanel.getVisibility() == View.VISIBLE) {
            showAcademy();
        } else {
            super.onBackPressed();
        }
    }
}
