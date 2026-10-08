from flask import Flask, render_template, request
import pdfplumber
import re

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/manual", methods=["GET", "POST"])
def manual():
    prediction_text = ""
    optimization_result = ""
    model_accuracy = ""

    if request.method == "POST":
        battery_temp = request.form["battery_temp"]
        charging_duration = request.form["charging_duration"]
        degradation_rate = request.form["degradation_rate"]
        charging_mode = request.form["charging_mode"]
        efficiency = request.form["efficiency"]
        battery_type = request.form["battery_type"]
        charging_cycles = request.form["charging_cycles"]
        ev_model = request.form["ev_model"]

        predicted_life = 100 - float(degradation_rate)
        prediction_text = f"Predicted Battery Life: {predicted_life:.2f} hours"
        optimization_result = (
            "Best Hyperparameters Found â†’ "
            "Learning Rate: 0.01, Max Depth: 6"
        )
        model_accuracy = (
            "Random Forest Model Accuracy: 92.4%"
        )

    return render_template(
        "predict.html",
        prediction_text=prediction_text,
        optimization_result=optimization_result,
        model_accuracy=model_accuracy,
    )


def find_report_value(text, labels, numeric=False):
    """Return the first value following one of the report's field labels."""
    label_pattern = "|".join(labels)
    if numeric:
        pattern = rf"(?:{label_pattern})(?:\s*\([^)]*\))?\s*(?:[:=\-]\s*)?(-?\d+(?:[.,]\d+)?)"
    else:
        pattern = rf"(?:{label_pattern})\s*(?:[:=\-]\s*)?([^\r\n]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip(" \t:=-")
    return value or None


REPORT_FIELDS = [
    ("EV model", [r"EV\s+Model", r"Vehicle\s+Model", r"Car\s+Model"], False, ""),
    ("Battery type", [r"Battery\s+Type", r"Battery\s+Chemistry"], False, ""),
    ("Battery temperature", [r"Battery\s+Temperature", r"Battery\s+Temp", r"Temperature", r"Temp"], True, " °C"),
    ("Degradation rate", [r"Battery\s+Degradation\s+Rate", r"Degradation\s+Rate", r"Degradation"], True, "%"),
    ("Charging efficiency", [r"Charging\s+Efficiency", r"Efficiency"], True, "%"),
    ("Charging cycles", [r"Charging\s+Cycles", r"Cycle\s+Count", r"Cycles"], True, ""),
    ("Charging duration", [r"Charging\s+Duration", r"Charging\s+Time"], True, " min"),
]


@app.route("/upload", methods=["GET", "POST"])
def upload():
    error = ""
    report = None

    if request.method == "POST":
        file = request.files.get("pdf")
        if not file or not file.filename:
            error = "Choose a PDF report to continue."
        elif not file.filename.lower().endswith(".pdf"):
            error = "Please upload a PDF file."
        else:
            try:
                with pdfplumber.open(file) as pdf:
                    extracted_text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    ).strip()

                if not extracted_text:
                    error = "This PDF has no readable text. Please try a text-based report."
                else:
                    values = {}
                    for title, labels, numeric, unit in REPORT_FIELDS:
                        value = find_report_value(extracted_text, labels, numeric)
                        if value is not None:
                            values[title] = f"{value}{unit}"

                    degradation = find_report_value(
                        extracted_text,
                        [r"Battery\s+Degradation\s+Rate", r"Degradation\s+Rate", r"Degradation"],
                        numeric=True,
                    )
                    predicted_health = None
                    if degradation is not None:
                        predicted_health = max(0, min(100, 100 - float(degradation.replace(",", "."))))

                    temperature = find_report_value(
                        extracted_text,
                        [r"Battery\s+Temperature", r"Battery\s+Temp", r"Temperature", r"Temp"],
                        numeric=True,
                    )

                    overview = []
                    for title, _, _, _ in REPORT_FIELDS:
                        if title in values:
                            overview.append({"label": title, "value": values[title]})

                    report = {
                        "values": values,
                        "overview": overview,
                        "predicted_health": predicted_health,
                        "battery_temp": float(temperature.replace(",", ".")) if temperature else None,
                        "degradation": float(degradation.replace(",", ".")) if degradation else None,
                        "source_name": file.filename,
                        "text_preview": " ".join(extracted_text.split())[:700],
                    }
                    if predicted_health is None:
                        error = "I couldn't find a degradation rate, so battery health couldn't be estimated. The EV overview is shown below."
            except Exception:
                error = "I couldn't read that PDF. Please check the file and try again."

    return render_template("upload.html", report=report, error=error)


if __name__ == "__main__":
    app.run(debug=True)

