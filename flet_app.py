import flet as ft
import requests

# CONFIGURACIÓN
HOST = "http://127.0.0.1:8000"
PELUQUERIA_SLUG = "mi-salon"  # <--- ¡CAMBIA ESTO POR TU SLUG REAL!
BASE_API = f"{HOST}/api/v1/{PELUQUERIA_SLUG}"

def main(page: ft.Page):
    page.title = f"Gestión: {PELUQUERIA_SLUG}"
    page.window_width = 400
    page.window_height = 700
    page.padding = 20

    lbl_status = ft.Text("Listo", color="grey")
    dd_servicio = ft.Dropdown(label="Servicio", width=350)
    dd_empleado = ft.Dropdown(label="Empleado (Opcional)", width=350)
    txt_fecha = ft.TextField(label="Fecha (YYYY-MM-DD)", width=350, value="2025-12-06")
    col_resultados = ft.Column(scroll=ft.ScrollMode.AUTO, height=400)

    def cargar_inicio():
        try:
            # 1. Cargar Servicios
            r = requests.get(f"{BASE_API}/servicios/")
            if r.status_code == 200:
                dd_servicio.options = [ft.dropdown.Option(key=str(s['id']), text=s['nombre']) for s in r.json()]
            
            # 2. Cargar Empleados
            r = requests.get(f"{BASE_API}/empleados/")
            if r.status_code == 200:
                dd_empleado.options = [ft.dropdown.Option(key="todos", text="Cualquiera")]
                for e in r.json():
                    dd_empleado.options.append(ft.dropdown.Option(key=str(e['id']), text=e['nombre']))
            
            page.update()
        except Exception as e:
            lbl_status.value = f"Error conectando: {e}"
            lbl_status.color = "red"
            page.update()

    def reservar(hora, emp_nombre, emp_id):
        try:
            payload = {
                "empleado_id": emp_id, # La API ahora espera IDs reales, no nombres
                "servicio_id": dd_servicio.value,
                "fecha": txt_fecha.value,
                "hora_inicio": hora,
                "cliente_nombre": "Cliente Local"
            }
            r = requests.post(f"{BASE_API}/citas/crear/", json=payload)
            
            if r.status_code == 201:
                page.snack_bar = ft.SnackBar(ft.Text(f"✅ Cita agendada: {hora}"), bgcolor="green")
                col_resultados.controls.clear() # Limpiar para no duplicar
            elif r.status_code == 409:
                page.snack_bar = ft.SnackBar(ft.Text("⚠️ ¡Ese horario ya se ocupó!"), bgcolor="orange")
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Error al agendar"), bgcolor="red")
            
            page.snack_bar.open = True
            page.update()
            
        except Exception as e:
            print(e)

    def buscar(e):
        if not dd_servicio.value: return
        
        lbl_status.value = "Buscando..."
        col_resultados.controls.clear()
        page.update()

        try:
            # Si seleccionó "todos", mandamos vacío o 'todos'
            emp_val = dd_empleado.value if dd_empleado.value else "todos"
            
            url = f"{BASE_API}/disponibilidad/?fecha={txt_fecha.value}&service_id={dd_servicio.value}&empleado_id={emp_val}"
            r = requests.get(url)
            data = r.json()

            if not data:
                col_resultados.controls.append(ft.Text("No hay horarios libres."))
            
            # Recorremos resultados { "Juan": [{"hora_inicio": "10:00"}], ... }
            
            for nombre_emp, bloques in data.items():
                # Truco para encontrar ID
                emp_id_real = None
                for opt in dd_empleado.options:
                    if opt.text in nombre_emp: emp_id_real = opt.key
                
                if not emp_id_real: continue # Si no hallamos ID, saltamos

                col_resultados.controls.append(ft.Text(f"Agenda de {nombre_emp}:", weight="bold"))
                
                row = ft.Row(wrap=True)
                for b in bloques:
                    h = b['hora_inicio']
                    btn = ft.ElevatedButton(
                        text=h, 
                        on_click=lambda e, h=h, en=nombre_emp, eid=emp_id_real: reservar(h, en, eid)
                    )
                    row.controls.append(btn)
                col_resultados.controls.append(row)
                col_resultados.controls.append(ft.Divider())

            lbl_status.value = "Actualizado"
            
        except Exception as ex:
            lbl_status.value = f"Error: {ex}"
        
        page.update()

    btn_buscar = ft.ElevatedButton("Buscar", on_click=buscar, bgcolor="blue", color="white")
    
    page.add(ft.Text("App Peluquería", size=20), dd_servicio, dd_empleado, txt_fecha, btn_buscar, lbl_status, col_resultados)
    cargar_inicio()

ft.app(target=main)