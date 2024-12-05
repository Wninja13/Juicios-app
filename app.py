
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
import sqlite3
import pandas as pd
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

DB_NAME = "juicios.db"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS juicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_expediente TEXT NOT NULL,
            caratula TEXT NOT NULL,
            tema TEXT NOT NULL,
            ultimo_movimiento TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            juicio_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            archivo TEXT,
            FOREIGN KEY (juicio_id) REFERENCES juicios (id)
        )
    ''')
    conn.commit()
    conn.close()

def update_db_schema():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE movimientos ADD COLUMN archivo TEXT")
        conn.commit()
        print("Columna 'archivo' añadida con éxito.")
    except sqlite3.OperationalError as e:
        print(f"Error al modificar la tabla: {e}")
    conn.close()

# Initialize the database and update the schema
init_db()
update_db_schema()

@app.route('/')
def index():
    search_query = request.args.get('search', '')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if search_query:
        cursor.execute(
            "SELECT id, numero_expediente || ' - ' || caratula || ' - ' || tema AS title, ultimo_movimiento FROM juicios WHERE numero_expediente LIKE ? OR caratula LIKE ? OR tema LIKE ?",
            (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
        )
    else:
        cursor.execute(
            "SELECT id, numero_expediente || ' - ' || caratula || ' - ' || tema AS title, ultimo_movimiento FROM juicios"
        )
    juicios = cursor.fetchall()
    conn.close()

    # Check if no results were found
    not_found = len(juicios) == 0

    return render_template("index.html", juicios=juicios, search_query=search_query, not_found=not_found)


@app.route('/add', methods=['POST'])
def add_juicio():
    numero_expediente = request.form['numero_expediente']
    caratula = request.form['caratula']
    tema = request.form['tema']
    ultimo_movimiento = request.form['ultimo_movimiento']
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO juicios (numero_expediente, caratula, tema, ultimo_movimiento) VALUES (?, ?, ?, ?)",(numero_expediente, caratula, tema, ultimo_movimiento))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:juicio_id>', methods=['GET', 'POST'])
def edit_juicio(juicio_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if request.method == 'POST':
        numero_expediente = request.form['numero_expediente']
        caratula = request.form['caratula']
        tema = request.form['tema']
        ultimo_movimiento = request.form['ultimo_movimiento']
        cursor.execute("UPDATE juicios SET numero_expediente = ?, caratula = ?, tema = ?, ultimo_movimiento = ? WHERE id = ?",(numero_expediente, caratula, tema, ultimo_movimiento, juicio_id))
        cursor.execute("INSERT INTO movimientos (juicio_id, fecha, descripcion) VALUES (?, date('now'), ?)",(juicio_id, ultimo_movimiento))
        conn.commit()
        return redirect(url_for('index'))
    cursor.execute("SELECT * FROM juicios WHERE id = ?", (juicio_id,))
    juicio = cursor.fetchone()
    conn.close()
    return render_template("edit.html", juicio=juicio)

@app.route('/movimientos/<int:juicio_id>')
def movimientos(juicio_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT numero_expediente, caratula FROM juicios WHERE id = ?", (juicio_id,))
    juicio = cursor.fetchone()
    cursor.execute("SELECT * FROM movimientos WHERE juicio_id = ?", (juicio_id,))
    movimientos = cursor.fetchall()
    conn.close()
    return render_template("movimientos.html", movimientos=movimientos, juicio_id=juicio_id,numero_expediente=juicio[0], caratula=juicio[1])

@app.route('/add_movimiento/<int:juicio_id>', methods=['POST'])
def add_movimiento(juicio_id):
    fecha = request.form['fecha']
    descripcion = request.form['descripcion']
    archivo = request.files['archivo']
    
    archivo_nombre = None
    if archivo and archivo.filename.endswith('.pdf'):
        archivo_nombre = secure_filename(archivo.filename)
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], archivo_nombre))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO movimientos (juicio_id, fecha, descripcion, archivo) VALUES (?, ?, ?, ?)",(juicio_id, fecha, descripcion, archivo_nombre))
    cursor.execute("UPDATE juicios SET ultimo_movimiento = ? WHERE id = ?",(descripcion, juicio_id))
    conn.commit()
    conn.close()
    return redirect(url_for('movimientos', juicio_id=juicio_id))

@app.route('/delete_movimiento/<int:movimiento_id>')
def delete_movimiento(movimiento_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimientos WHERE id = ?", (movimiento_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/export')
def export_to_excel():
    conn = sqlite3.connect(DB_NAME)
    juicios_df = pd.read_sql_query("SELECT * FROM juicios", conn)
    movimientos_df = pd.read_sql_query("SELECT * FROM movimientos", conn)
    conn.close()

    file_path = "Juicios_Report.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        juicios_df.to_excel(writer, sheet_name='Juicios', index=False)
        movimientos_df.to_excel(writer, sheet_name='Movimientos', index=False)

    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
