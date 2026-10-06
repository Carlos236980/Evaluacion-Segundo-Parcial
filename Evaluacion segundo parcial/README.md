# Veterinaria Patitas

Sistema web en Flask para registrar y consultar pacientes y citas. Incluye diez casos ficticios con fotografía, dos cuentas de empleados, edición, eliminación, búsqueda y exportación CSV para Excel.

## Ejecutar

Requiere Python 3.10 o posterior. Abre una terminal dentro de esta carpeta y ejecuta:

```bash
python -m pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000 en el navegador. En Windows también puedes ejecutar `iniciar.bat`.

## Cuentas de demostración

| Usuario | Contraseña |
| --- | --- |
| empleado1 | Patitas#2026A |
| empleado2 | Patitas#2026B |

Las contraseñas se almacenan como hashes de Werkzeug. Las claves iniciales incluidas en el código son para la evaluación académica.

## Guardado y exportación

La primera ejecución crea automáticamente `instance/veterinaria.db`, la clave de sesión y los diez registros iniciales. Los datos permanecen al reiniciar y no se duplican. Las fotos se guardan en `static/img/`. El botón Exportar CSV descarga los datos actuales en UTF-8 con BOM. Si Excel los muestra en una sola columna, importa el archivo con Datos → Desde texto/CSV y selecciona coma como delimitador.

## Archivos

- `app.py`: servidor, autenticación, base de datos y exportación.
- `index.html`: login, panel, ficha y formulario.
- `script.js`: interacciones y consultas al servidor.
- `style.css`: diseño adaptable.
- `casos_iniciales.json`: diez casos ficticios de ejemplo.
- `static/img/`: fotografías de los pacientes.
- `requirements.txt`: dependencias.

El archivo `.gitignore` excluye la base de datos, la clave de sesión y los entornos virtuales. Esta aplicación se ejecuta localmente con Flask; GitHub Pages no ejecuta Python.
