package com.apj.teacher;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        WebView w = new WebView(this);
        w.setWebViewClient(new WebViewClient());
        w.getSettings().setJavaScriptEnabled(true);
        w.getSettings().setDomStorageEnabled(true);
        w.getSettings().setAllowFileAccessFromFileURLs(false);
        w.getSettings().setAllowUniversalAccessFromFileURLs(false);
        w.addJavascriptInterface(new ApiBridge(), "AndroidApi");
        w.loadUrl("file:///android_asset/index.html");
        setContentView(w);
    }

    private static final class ApiBridge {
        private static final String API_HOST = "apj-teacher-api--ajitjadav0888.replit.app";

        @JavascriptInterface
        public String request(String method, String requestUrl, String requestBody) {
            HttpURLConnection connection = null;
            try {
                URL url = new URL(requestUrl);
                if (!"https".equalsIgnoreCase(url.getProtocol())
                        || !API_HOST.equalsIgnoreCase(url.getHost())
                        || (!"/health".equals(url.getPath())
                        && !"/api/v1/auth/login".equals(url.getPath()))) {
                    return result(false, 0, "Request is not allowed");
                }

                connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod(method);
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(15000);
                connection.setUseCaches(false);
                connection.setRequestProperty("Accept", "application/json");

                if (requestBody != null && !requestBody.isEmpty()) {
                    connection.setDoOutput(true);
                    connection.setRequestProperty("Content-Type", "application/json");
                    try (OutputStream output = connection.getOutputStream()) {
                        output.write(requestBody.getBytes(StandardCharsets.UTF_8));
                    }
                }

                int status = connection.getResponseCode();
                InputStream stream = status >= 400
                        ? connection.getErrorStream()
                        : connection.getInputStream();
                String body = readBody(stream);
                return result(status >= 200 && status < 300, status, body);
            } catch (Exception error) {
                return result(false, 0, "Unable to reach the API");
            } finally {
                if (connection != null) connection.disconnect();
            }
        }

        private static String readBody(InputStream stream) throws Exception {
            if (stream == null) return "";
            StringBuilder body = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
            }
            return body.toString();
        }

        private static String result(boolean ok, int status, String body) {
            try {
                return new JSONObject()
                        .put("ok", ok)
                        .put("status", status)
                        .put("body", body == null ? "" : body)
                        .toString();
            } catch (Exception ignored) {
                return "{\"ok\":false,\"status\":0,\"body\":\"\"}";
            }
        }
    }
}
