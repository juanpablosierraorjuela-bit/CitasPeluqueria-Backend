import flet as ft
import requests
from datetime import date

# ==============================================================================
# ⚙️ CONFIGURACIÓN
# ==============================================================================
HOST = "http://127.0.0.1:8000"
PELUQUERIA_SLUG = "salon-temp" # ¡Asegúrate que esto coincida con tu slug en Admin!
API_KEY = "mi-clave-super-secreta-cambiame" 

HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

BASE_API = f"{HOST}/api/v1/{PELUQUERIA_SLUG}"

def main(page: ft.Page):
    page.title = f"Gestión: {PELUQUERIA_SLUG}"
    page.window_width = 450
    page.window_height = 800
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    # --- UI Elements ---
    lbl_status = ft.Text("Listo para reservar", color="grey", size=12)
    
    # Datos del Cliente
    txt_cliente = ft.TextField(label="Nombre del Cliente", icon=ft.icons.PERSON)
    txt_telefono = ft.TextField(label="Teléfono / WhatsApp", icon=ft.icons.PHONE, keyboard_type=ft.KeyboardType.PHONE)
    
    # Datos de la Reserva
    dd_servicio = ft.Dropdown(label="Seleccionar Servicio", prefix_icon=ft.icons.CUT)
    dd_empleado = ft.Dropdown(label="Estilista (Opcional)", prefix_icon=ft.icons.PERSON_SEARCH)
    
    fecha_hoy = date.today().strftime("%Y-%m-%d")
    txt_fecha = ft.TextField(label="Fecha (YYYY-MM-DD)", value=fecha_hoy, icon=ft.icons.CALENDAR_MONTH)
    
    col_resultados = ft.Column(spacing=10)

    def cargar_datos_iniciales():
        """Carga servicios y empleados al iniciar"""
        try:
            # 1. Servicios
            r_serv = requests.get(f"{BASE_API}/servicios/", headers=HEADERS)
            if r_serv.status_code == 200:
                dd_servicio.options = [
                    ft.dropdown.Option(key=str(s['id']), text=f"{s['nombre']} (${s['precio']:,.0f})") 
                    for s in r_serv.json()
                ]
            else:
                lbl_status.value = "Error cargando servicios."
            
            # 2. Empleados
            r_emp = requests.get(f"{BASE_API}/empleados/", headers=HEADERS)
            if r_emp.status_code == 200:
                dd_empleado.options = [ft.dropdown.Option(key="todos", text="Cualquiera")]
                for e in r_emp.json():
                    dd_empleado.options.append(ft.dropdown.Option(key=str(e['id']), text=e['nombre']))
            
            page.update()
        except Exception as e:
            lbl_status.value = f"Error de conexión: {e}"
            lbl_status.color = "red"
            page.update()

    def realizar_reserva(hora, empleado_nombre, empleado_id):
        """Envía la reserva a la API"""
        if not txt_cliente.value or not txt_telefono.value:
            page.show_snack_bar(ft.SnackBar(content=ft.Text("⚠️ Falta nombre o teléfono del cliente"), bgcolor="orange"))
            return

        payload = {
            "empleado_id": empleado_id,
            "servicio_id": dd_servicio.value,
            "fecha": txt_fecha.value,
            "hora_inicio": hora,
            "cliente_nombre": txt_cliente.value,
            "cliente_telefono": txt_telefono.value
        }
        
        try:
            r = requests.post(f"{BASE_API}/citas/crear/", json=payload, headers=HEADERS)
            
            if r.status_code == 201:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(f"✅ Cita creada: {hora} con {empleado_nombre}"), bgcolor="green"))
                col_resultados.controls.clear()
                # Limpiar campos de cliente para la siguiente
                txt_cliente.value = ""
                txt_telefono.value = ""
                buscar_disponibilidad(None) # Refrescar grid
            elif r.status_code == 409:
                page.show_snack_bar(ft.SnackBar(content=ft.Text("⛔ Ese horario ya se ocupó."), bgcolor="red"))
            else:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {r.text}"), bgcolor="red"))
            
            page.update()
        except Exception as e:
            print(e)

    def buscar_disponibilidad(e):
        if not dd_servicio.value:
            page.show_snack_bar(ft.SnackBar(content=ft.Text("Selecciona un servicio primero"), bgcolor="orange"))
            return
        
        lbl_status.value = "Consultando agenda..."
        lbl_status.color = "blue"
        col_resultados.controls.clear()
        page.update()

        try:
            emp_query = dd_empleado.value if dd_empleado.value else "todos"
            url = f"{BASE_API}/disponibilidad/?fecha={txt_fecha.value}&service_id={dd_servicio.value}&empleado_id={emp_query}"
            
            r = requests.get(url, headers=HEADERS)
            data = r.json()

            if not data or "error" in data:
                col_resultados.controls.append(
                    ft.Container(content=ft.Text("No hay disponibilidad o el local está cerrado.", color="red"), padding=10)
                )
            else:
                # Iterar sobre los resultados (Nombre Empleado -> Lista Horas)
                for nombre_emp, horas in data.items():
                    # Buscar el ID del empleado basado en el nombre devuelto o la selección
                    # Esto es un truco porque la API devuelve dict {nombre: [horas]}
                    emp_id_target = None
                    
                    # Si seleccionó uno específico, usamos ese ID
                    if emp_query != "todos":
                        emp_id_target = emp_query
                    else:
                        # Si fue "todos", intentamos buscar el ID en el dropdown haciendo match con el nombre
                        for opt in dd_empleado.options:
                            if opt.text in nombre_emp:
                                emp_id_target = opt.key
                                break
                    
                    if not emp_id_target: continue # Skip si no podemos identificar al empleado

                    # Crear Tarjeta de Empleado
                    grid_horas = ft.Row(wrap=True, spacing=5, run_spacing=5)
                    
                    for h in horas:
                        hora_str = h['hora_inicio']
                        btn = ft.ElevatedButton(
                            text=hora_str,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e, hr=hora_str, en=nombre_emp, eid=emp_id_target: realizar_reserva(hr, en, eid)
                        )
                        grid_horas.controls.append(btn)

                    col_resultados.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"👤 {nombre_emp}", weight="bold", size=16, color="blue"),
                                ft.Divider(height=1),
                                grid_horas
                            ]),
                            bgcolor=ft.colors.BLUE_50,
                            padding=15,
                            border_radius=10,
                            border=ft.border.all(1, ft.colors.BLUE_100)
                        )
                    )

            lbl_status.value = "Búsqueda finalizada"
            lbl_status.color = "green"

        except Exception as ex:
            lbl_status.value = f"Error: {str(ex)}"
            lbl_status.color = "red"
        
        page.update()

    btn_buscar = ft.ElevatedButton("🔍 Buscar Disponibilidad", on_click=buscar_disponibilidad, bgcolor="#0f172a", color="white", height=50)

    page.add(
        ft.Text("Gestor de Citas", size=28, weight="bold", color="#db2777"),
        ft.Divider(),
        ft.Text("1. Datos del Cliente", weight="bold"),
        txt_cliente,
        txt_telefono,
        ft.Divider(),
        ft.Text("2. Configuración Cita", weight="bold"),
        dd_servicio,
        dd_empleado,
        txt_fecha,
        ft.Container(height=10),
        btn_buscar,
        lbl_status,
        ft.Divider(),
        col_resultados
    )
    
    cargar_datos_iniciales()

ft.app(target=main)
