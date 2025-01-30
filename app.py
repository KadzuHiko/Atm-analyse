from flask import Flask, request, jsonify, render_template, redirect, url_for
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
import logging

# Логирование
logging.basicConfig(level=logging.DEBUG)

# Создаем папку для загрузок, если она не существует
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Настройки базы данных
DATABASE_URL = "sqlite:///atm_db.sqlite"
engine = create_engine(DATABASE_URL)
Base = declarative_base()


# Определяем модель
class ATMEvent(Base):
    __tablename__ = 'atm_events'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    device_id = Column(String)
    event_type = Column(String)
    user_id = Column(String)  # Новая колонка
    details = Column(String)
    value = Column(String)  # Новая колонка


# Создаем таблицы в базе данных
Base.metadata.create_all(engine)

# Создаем сессию для работы с базой данных
Session = sessionmaker(bind=engine)
session = Session()

# Флаг для проверки загрузки файла
file_uploaded = False

# Инициализация Flask
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html', file_uploaded=file_uploaded)

@app.route('/data')
def show_data():
    data = session.query(ATMEvent).all()
    return render_template('data.html', data=data, file_uploaded=file_uploaded)

@app.route('/upload', methods=['POST'])
def upload_file():
    global file_uploaded
    if 'file' not in request.files:
        return jsonify({"error": "Файл не выбран"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Файл не выбран"}), 400
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        try:
            df = pd.read_csv(filepath)
            logging.debug(f"Columns in CSV: {df.columns}")
            logging.debug(f"First few rows of CSV: {df.head()}")

            # Переименуем колонку "User  ID" в "User ID" (убираем лишний пробел)
            if 'User  ID' in df.columns:
                df.rename(columns={'User  ID': 'User ID'}, inplace=True)

            # Проверка наличия необходимых колонок
            required_columns = ['EventType', 'Timestamp', 'DeviceID', 'User ID', 'Details', 'Value']
            if not all(column in df.columns for column in required_columns):
                return jsonify({"error": "CSV файл не содержит необходимые колонки"}), 400

            # Преобразование Timestamp в datetime
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')

            # Сохранение данных в базу
            for _, row in df.iterrows():
                atm_event = ATMEvent(
                    timestamp=row['Timestamp'],
                    device_id=row['DeviceID'],
                    event_type=row['EventType'],
                    user_id=row['User ID'],
                    details=row['Details'],
                    value=str(row['Value']) if pd.notna(row['Value']) else None  # Обработка пустых значений
                )
                session.add(atm_event)
            session.commit()

            # Устанавливаем флаг загрузки файла
            file_uploaded = True

            # Перенаправляем на главную страницу
            return redirect(url_for('index'))
        except Exception as e:
            logging.error(f"Error during file processing: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Неверный формат файла"}), 400


@app.route('/reports')
def reports():
    atms = session.query(ATMEvent.device_id).distinct().all()
    atms = [atm[0] for atm in atms]
    return render_template('reports.html', atms=atms, file_uploaded=file_uploaded)


@app.route('/get_atm_report/<device_id>')
def get_atm_report(device_id):
    atm_data = session.query(ATMEvent).filter_by(device_id=device_id).all()

    if not atm_data:
        return render_template('error.html', message=f"Нет данных для банкомата {device_id}")

    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    week_data = [event for event in atm_data if event.timestamp >= week_ago]
    month_data = [event for event in atm_data if event.timestamp >= month_ago]

    uptime_week = calculate_uptime(week_data)
    uptime_month = calculate_uptime(month_data)

    failures_week = len([event for event in week_data if "Ошибка" in event.event_type])
    failures_month = len([event for event in month_data if "Ошибка" in event.event_type])

    return render_template('atm_report.html',
                           device_id=device_id,
                           data=atm_data,
                           uptime_week=uptime_week,
                           uptime_month=uptime_month,
                           failures_week=failures_week,
                           failures_month=failures_month,
                           file_uploaded=True)


@app.route('/analytics')
def analytics():
    repair_needed = session.query(ATMEvent.device_id).filter(ATMEvent.event_type.contains("Ошибка")).distinct().all()
    incasso_needed = session.query(ATMEvent.device_id).filter(
        ATMEvent.details.contains("Низкий уровень наличных")).distinct().all()

    repair_needed = [item[0] for item in repair_needed]
    incasso_needed = [item[0] for item in incasso_needed]

    return render_template('analytics.html', repair_needed=repair_needed, incasso_needed=incasso_needed,
                           file_uploaded=True)


def calculate_uptime(data):
    total_time = (data[-1].timestamp - data[0].timestamp).total_seconds() if data else 0
    downtime = sum((event.timestamp - data[i - 1].timestamp).total_seconds()
                   for i, event in enumerate(data) if "Ошибка" in event.event_type)
    uptime = (total_time - downtime) / total_time * 100 if total_time > 0 else 0
    return round(uptime, 2)


if __name__ == '__main__':
    app.run(debug=True)