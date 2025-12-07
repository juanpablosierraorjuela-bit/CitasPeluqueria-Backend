import flet as ft
import requests

# ==============================================================================
# ⚙️ CONFIGURACIÓN
# ==============================================================================
HOST = "http://127.0.0.1:8000"
PELUQUERIA_SLUG = "mi-salon"  # <--- ¡CAMBIA ESTO POR TU SLUG REAL (ej: 'estilo-juan')!

# 🛡️ SEGURIDAD: Esta clave debe ser IGUAL a 'API_SECRET_KEY' en tu settings.py
API_KEY = "mi-clave-super-secreta-cambiame" 

# Preparamos los encabezados para todas las peticiones protegidas
HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

BASE_API = f"{HOST}/api/v1/{PELUQUERIA_SLUG}"

def main(page: ft.Page):
    page.title = f"Gestión: {PELUQUERIA_SLUG}"
    page.window_width = 400
    page.window_height = 700
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT

    # Elementos de la UI
    lbl_status = ft.Text("Listo para reservar", color="grey")
    dd_servicio = ft.Dropdown(label="Servicio", width=350)
    dd_empleado = ft.Dropdown(label="Empleado (Opcional)", width=350)
    
    # Fecha por defecto: Hoy
    from datetime import date
    fecha_hoy = date.today().strftime("%Y-%m-%d")
    txt_fecha = ft.TextField(label="Fecha (YYYY-MM-DD)", width=350, value=fecha_hoy)
    
    col_resultados = ft.Column(scroll=ft.ScrollMode.AUTO, height=400)

    def cargar_inicio():
        """Carga los datos iniciales (Servicios y Empleados)"""
        try:
            # 1. Cargar Servicios
            # Nota: Las peticiones GET públicas no suelen necesitar API Key, pero no hace daño enviarla
            r = requests.get(f"{BASE_API}/servicios/")
            if r.status_code == 200:
                dd_servicio.options = [ft.dropdown.Option(key=str(s['id']), text=f"{s['nombre']} (${s['precio']})") for s in r.json()]
            
            # 2. Cargar Empleados
            r = requests.get(f"{BASE_API}/empleados/")
            if r.status_code == 200:
                dd_empleado.options = [ft.dropdown.Option(key="todos", text="Cualquiera")]
                for e in r.json():
                    dd_empleado.options.append(ft.dropdown.Option(key=str(e['id']), text=e['nombre']))
            
            page.update()
        except Exception as e:
            lbl_status.value = f"Error conectando al servidor: {e}"
            lbl_status.color = "red"
            page.update()

    def reservar(hora, emp_nombre, emp_id):
        """Envía la solicitud de reserva PROTEGIDA al backend"""
        try:
            payload = {
                "empleado_id": emp_id,
                "servicio_id": dd_servicio.value,
                "fecha": txt_fecha.value,
                "hora_inicio": hora,
                "cliente_nombre": "Cliente Local (App)", # Podrías agregar un campo de texto para esto
                "cliente_telefono": "0000000000"
            }
            
            # 👇 AQUÍ ESTÁ EL CAMBIO IMPORTANTE: Agregamos headers=HEADERS
            r = requests.post(f"{BASE_API}/citas/crear/", json=payload, headers=HEADERS)
            
            if r.status_code == 201:
                page.show_snack_bar(ft.SnackBar(ft.Text(f"✅ Cita agendada: {hora} con {emp_nombre}"), bgcolor="green"))
                col_resultados.controls.clear() # Limpiamos para evitar duplicados
                buscar(None) # Refrescamos disponibilidad
            elif r.status_code == 409:
                page.show_snack_bar(ft.SnackBar(ft.Text("⚠️ ¡Ese horario ya se ocupó! Intenta otro."), bgcolor="orange"))
            elif r.status_code == 403:
                page.show_snack_bar(ft.SnackBar(ft.Text("⛔ Error de Seguridad: API Key incorrecta."), bgcolor="red"))
            else:
                page.show_snack_bar(ft.SnackBar(ft.Text(f"Error: {r.text}"), bgcolor="red"))
            
            page.update()
            
        except Exception as e:
            print(e)
            lbl_status.value = f"Error de conexión: {e}"
            page.update()

    def buscar(e):
        """Busca horarios disponibles"""
        if not dd_servicio.value:
            lbl_status.value = "⚠️ Selecciona un servicio primero"
            lbl_status.color = "orange"
            page.update()
            return
        
        lbl_status.value = "Buscando disponibilidad..."
        lbl_status.color = "blue"
        col_resultados.controls.clear()
        page.update()

        try:
            emp_val = dd_empleado.value if dd_empleado.value else "todos"
            
            url = f"{BASE_API}/disponibilidad/?fecha={txt_fecha.value}&service_id={dd_servicio.value}&empleado_id={emp_val}"
            
            # Las GET también pueden llevar headers si decides protegerlas en el futuro
            r = requests.get(url, headers=HEADERS) 
            data = r.json()

            if not data or "error" in data:
                if "error" in data: print(f"Error Server: {data['error']}")
                col_resultados.controls.append(ft.Text("No hay horarios disponibles para esta fecha.", color="red"))
            else:
                # Generar botones por cada empleado
                for nombre_emp, bloques in data.items():
                    # Buscamos el ID real del empleado en el dropdown
                    emp_id_real = None
                    for opt in dd_empleado.options:
                        if opt.text in nombre_emp or (opt.text != "Cualquiera" and opt.text.split()[0] in nombre_emp):
                             emp_id_real = opt.key
                             break
                    
                    # Fallback si no encontramos match exacto (usamos el seleccionado o saltamos)
                    if not emp_id_real and emp_val != "todos": 
                        emp_id_real = emp_val

                    if not emp_id_real: continue 

                    col_resultados.controls.append(ft.Container(
                        content=ft.Text(f"📅 Agenda de {nombre_emp}", weight="bold", size=16),
                        bgcolor=ft.colors.BLUE_50,
                        padding=10,
                        border_radius=5
                    ))
                    
                    row = ft.Row(wrap=True, spacing=10, run_spacing=10)
                    for b in bloques:
                        h = b['hora_inicio']
                        btn = ft.ElevatedButton(
                            text=h, 
                            on_click=lambda e, h=h, en=nombre_emp, eid=emp_id_real: reservar(h, en, eid),
                            bgcolor="white",
                            color="black"
                        )
                        row.controls.append(btn)
                    
                    col_resultados.controls.append(row)
                    col_resultados.controls.append(ft.Divider())

            lbl_status.value = "Búsqueda completada"
            lbl_status.color = "green"
            
        except Exception as ex:
            lbl_status.value = f"Error: {ex}"
            lbl_status.color = "red"
        
        page.update()

    btn_buscar = ft.ElevatedButton("🔍 Buscar Horarios", on_click=buscar, bgcolor="black", color="white", height=50)
    
    # Armado de la página
    page.add(
        ft.Text("App Peluquería", size=30, weight="bold", color="#ec4899"),
        ft.Divider(),
        dd_servicio, 
        dd_empleado, 
        txt_fecha, 
        ft.Container(height=10),
        btn_buscar, 
        ft.Container(height=10),
        lbl_status, 
        ft.Divider(),
        col_resultados
    )
    
    cargar_inicio()

ft.app(target=main)
