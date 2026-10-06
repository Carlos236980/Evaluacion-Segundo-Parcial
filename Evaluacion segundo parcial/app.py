from flask import Flask, request, session, jsonify, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from functools import wraps
from datetime import datetime
from PIL import Image
import sqlite3, json, secrets, io, csv, uuid, os

BASE = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
secret_file = BASE / 'instance' / 'secret.key'
secret_file.parent.mkdir(exist_ok=True)
if not secret_file.exists():
    secret_file.write_text(secrets.token_hex(32))
app.secret_key = os.environ.get('SECRET_KEY') or secret_file.read_text().strip()
app.config.update(MAX_CONTENT_LENGTH=5*1024*1024, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax')

def db():
    con = sqlite3.connect(BASE / 'instance' / 'veterinaria.db')
    con.row_factory = sqlite3.Row
    return con

def initialize():
    with db() as con:
        con.executescript("""CREATE TABLE IF NOT EXISTS usuarios (
          id INTEGER PRIMARY KEY, usuario TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pacientes (
          id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL,
          servicio TEXT NOT NULL, fecha TEXT NOT NULL, hora TEXT NOT NULL,
          costo REAL NOT NULL CHECK(costo>=0), caso TEXT NOT NULL, foto TEXT NOT NULL);""" )
        for user, password in [('empleado1','Patitas#2026A'),('empleado2','Patitas#2026B')]:
            if not con.execute('SELECT id FROM usuarios WHERE usuario=?',(user,)).fetchone():
                con.execute('INSERT INTO usuarios(usuario,password_hash) VALUES (?,?)',
                            (user, generate_password_hash(password)))
        # La marca evita regenerar los casos si el usuario elimina todos los registros.
        marker = BASE / 'instance' / 'seed_done'
        if not marker.exists():
            for row in json.loads((BASE/'casos_iniciales.json').read_text()):
                con.execute('INSERT INTO pacientes VALUES (?,?,?,?,?,?,?,?,?)',tuple(row[k] for k in
                    ['id','nombre','tipo','servicio','fecha','hora','costo','caso','foto']))
            con.commit()
            marker.touch()
initialize()

def protected(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('usuario'): return jsonify(error='Inicia sesión para continuar.'),401
        if request.method not in ['GET','HEAD'] and not secrets.compare_digest(
            request.headers.get('X-CSRF-Token',''),session.get('csrf','')):
            return jsonify(error='Sesión inválida. Recarga la página.'),403
        return fn(*args, **kwargs)
    return wrapped

@app.get('/')
def home(): return send_file(BASE/'index.html')
@app.get('/style.css')
def css(): return send_file(BASE/'style.css')
@app.get('/script.js')
def js(): return send_file(BASE/'script.js')
@app.get('/api/session')
def current():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(32)
    return jsonify(usuario=session.get('usuario'), csrf=session['csrf'])
@app.post('/api/login')
def login():
    data=request.get_json(silent=True) or {}
    if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','')):
        return jsonify(error='Recarga la página e intenta de nuevo.'),403
    with db() as con:
        user=con.execute('SELECT * FROM usuarios WHERE usuario=?',(data.get('usuario',''),)).fetchone()
    if not user or not check_password_hash(user['password_hash'],data.get('password','')):
        return jsonify(error='Usuario o contraseña incorrectos.'),401
    session.clear();session['usuario']=user['usuario'];session['csrf']=secrets.token_hex(32)
    return jsonify(usuario=session['usuario'],csrf=session['csrf'])
@app.post('/api/logout')
@protected
def logout(): session.clear();return jsonify(ok=True)
@app.get('/api/pacientes')
@protected
def patients():
    with db() as con: rows=con.execute('SELECT * FROM pacientes ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])
@app.get('/foto/<path:filename>')
@protected
def photo(filename): return send_from_directory(BASE/'static'/'img',filename)

def validated(data):
    fields={k:str(data.get(k,'')).strip() for k in ['nombre','tipo','servicio','fecha','hora','caso']}
    if not all(fields.values()): raise ValueError('Completa todos los campos.')
    if any(len(v)>2000 for v in fields.values()): raise ValueError('El texto es demasiado largo.')
    if fields['tipo'] not in ['Perro','Gato','Otro']: raise ValueError('Tipo de animal inválido.')
    datetime.strptime(fields['fecha'],'%Y-%m-%d'); datetime.strptime(fields['hora'],'%H:%M')
    cost=float(data.get('costo',''))
    if not 0<=cost<=1000000: raise ValueError('Costo inválido.')
    fields['costo']=round(cost,2)
    return fields

@app.route('/api/pacientes',methods=['POST'])
@app.route('/api/pacientes/<int:pid>',methods=['PUT'])
@protected
def save(pid=None):
    try: data=validated(request.form)
    except (ValueError,TypeError): return jsonify(error='Revisa los campos, la fecha, la hora y el costo.'),400
    with db() as con:
        old=con.execute('SELECT * FROM pacientes WHERE id=?',(pid,)).fetchone() if pid else None
        if pid and not old: return jsonify(error='Paciente no encontrado.'),404
        foto=old['foto'] if old else None
        upload=request.files.get('foto')
        if upload and upload.filename:
            try:
                im=Image.open(upload.stream); im.load(); im.thumbnail((1400,1400))
                filename=uuid.uuid4().hex+'.jpg';im.convert('RGB').save(BASE/'static'/'img'/filename,quality=88)
                foto=filename
            except Exception: return jsonify(error='Sube una fotografía válida en JPG o PNG.'),400
        if not foto: return jsonify(error='Selecciona una fotografía.'),400
        vals=[data[k] for k in ['nombre','tipo','servicio','fecha','hora','costo','caso']]+[foto]
        if pid: con.execute('UPDATE pacientes SET nombre=?,tipo=?,servicio=?,fecha=?,hora=?,costo=?,caso=?,foto=? WHERE id=?',vals+[pid])
        else: pid=con.execute('INSERT INTO pacientes(nombre,tipo,servicio,fecha,hora,costo,caso,foto) VALUES (?,?,?,?,?,?,?,?)',vals).lastrowid
    return jsonify(id=pid)
@app.delete('/api/pacientes/<int:pid>')
@protected
def delete(pid):
    with db() as con:
        cur=con.execute('DELETE FROM pacientes WHERE id=?',(pid,))
        if not cur.rowcount:return jsonify(error='Paciente no encontrado.'),404
    return jsonify(ok=True)

def csv_safe(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
@app.get('/api/exportar')
@protected
def export():
    buf=io.StringIO(newline='');writer=csv.writer(buf,delimiter=',',lineterminator='\r\n')
    writer.writerow(['ID','Nombre','Tipo de animal','Servicio','Fecha','Hora','Costo (MXN)','Caso clínico','Fotografía'])
    with db() as con:
        for r in con.execute('SELECT * FROM pacientes ORDER BY id'):
            writer.writerow([csv_safe(v) for v in r])
    return send_file(io.BytesIO(buf.getvalue().encode('utf-8-sig')),mimetype='text/csv; charset=utf-8',
                     as_attachment=True,download_name='pacientes.csv')
@app.errorhandler(413)
def too_large(e):return jsonify(error='La fotografía debe pesar menos de 5 MB.'),413
if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=False)
