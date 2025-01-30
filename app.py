from flask import Flask, request, jsonify, render_template
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)

# Папка для загрузки файлов
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# Загрузка CSV-файла
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.csv'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Чтение CSV-файла
        try:
            df = pd.read_csv(filepath)

            # Анализ данных
            analysis_results = analyze_data(df)

            return jsonify({
                "message": "File uploaded successfully",
                "data": df.to_dict(orient='records'),
                "analysis": analysis_results
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid file type"}), 400

# Функция для анализа данных
def analyze_data(df):
    # Преобразуем Timestamp в datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Анализ событий
    results = {
        "atm_statuses": {},
        "failures": {},
        "maintenance_needed": [],
        "incasso_needed": []
    }

    # Список всех банкоматов
    atm_list = df['DeviceID'].unique()

    for atm in atm_list:
        atm_data = df[df['DeviceID'] == atm]

        # Статус банкомата (последнее событие)
        last_event = atm_data.iloc[-1]['EventType']
        results["atm_statuses"][atm] = last_event

        # Сбои (например, ошибки)
        failures = atm_data[atm_data['EventType'].str.contains('Ошибка|ЗажеваннаяКупюра|Низкий уровень наличных')]
        results["failures"][atm] = failures.shape[0]

        # Необходимость ремонта
        if failures.shape[0] > 0:
            results["maintenance_needed"].append(atm)

        # Необходимость инкассации
        if "Низкий уровень наличных" in atm_data['Details'].values:
            results["incasso_needed"].append(atm)

    return results

# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)