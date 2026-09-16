# A simple http server that renders csv data files into plots and presents them

#!/usr/bin/env python3
from flask import Flask, render_template_string, send_from_directory, abort
import os
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime

app = Flask(__name__)
LOG_DIR = "/home/grass/netzfrequenz"  # Pfad zu den CSV-Dateien

# HTML-Template für die Dateiliste
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Netzfrequenz-Logs</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        a { display: block; margin: 5px 0; }
        img { max-width: 100%; height: auto; }
        .file-item { display: flex; justify-content: space-between; align-items: center; }
        .download-btn { margin-left: 10px; }
    </style>
</head>
<body>
    <h1>Netzfrequenz-Logs</h1>
    <h2>Verfügbare Dateien:</h2>
    <ul>
        {% for file in files %}
        <li class="file-item">
            <a href="/plot/{{ file }}">{{ file }}</a>
            <a href="/download/{{ file }}" class="download-btn">[Download]</a>
        </li>
        {% endfor %}
    </ul>
</body>
</html>
"""

# HTML-Template für die Plot-Ansicht
PLOT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Plot: {{ filename }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        img { max-width: 100%; height: auto; }
        .actions { margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Plot: {{ filename }}</h1>
    <div class="actions">
        <a href="/">Zurück zur Übersicht</a>
        <a href="/download/{{ filename }}" style="margin-left: 10px;">[Download CSV]</a>
    </div>
    <div>
        <img src="data:image/png;base64,{{ plot_url }}" alt="Frequenz-Plot">
    </div>
</body>
</html>
"""

@app.route("/")
def list_files():
    """Listet alle CSV-Dateien auf."""
    files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith(".csv")], reverse=True)
    return render_template_string(HTML_TEMPLATE, files=files)

@app.route("/plot/<filename>")
def plot_file(filename):
    """Erzeugt einen Plot für die angegebene CSV-Datei."""
    filepath = os.path.join(LOG_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)

    # CSV einlesen
    df = pd.read_csv(filepath)

    # Plot erstellen
    plt.figure(figsize=(12, 6))
    plt.plot(pd.to_datetime(df["Timestamp"]), df["Frequenz (Hz)"], label="Frequenz (Hz)")
    plt.title(f"Netzfrequenz - {filename}")
    plt.xlabel("Zeit")
    plt.ylabel("Frequenz (Hz)")
    plt.grid(True)
    plt.legend()

    # Plot als Base64 kodieren
    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode("utf-8")
    plt.close()

    return render_template_string(PLOT_TEMPLATE, filename=filename, plot_url=plot_url)

@app.route("/download/<filename>")
def download_file(filename):
    """Ermöglicht den Download der CSV-Datei."""
    filepath = os.path.join(LOG_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    return send_from_directory(LOG_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=31337, debug=False)
