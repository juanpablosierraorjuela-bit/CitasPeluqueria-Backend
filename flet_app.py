import flet as ft
import requests

# Configuración de URLs
BASE_URL = "http://127.0.0.1:8000/api"

def main(page: ft.Page):
    page.title = "Sistema de Citas (Versión Blindada)"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    
    # --- VARIABLES GLOBALES DE LA APP ---
    lista_empleados_cache = [] # Guardaremos aquí los empleados para que no se pierdan
    
    # --- ELEMENTO VISUAL PARA VER ERRORES EN PANTALLA ---
    estado_texto = ft.Text("Esperando acción...", color="grey", size=14)

    # --- 1. FUNCIÓN PARA GUARDAR LA CITA ---
    def guardar_cita_en_django(e, nombre_emp, id_emp, id_serv, hora_ini, hora_fin, fecha):
        estado_texto.value = f"⏳ Procesando reserva para {nombre_emp}..."
        estado_texto.color = "blue"
        page.update()

        print(f"INTENTO DE RESERVA: EmpleadoID={id_emp}, ServicioID={id_serv}, Fecha={fecha}")

        try:
            datos = {
                "servicio_id": int(id_serv),
                "empleado_id": int(id_emp),
                "fecha": fecha,
                "hora_inicio": hora_ini,
                "hora_fin": hora_fin
            }
            
            # Petición a Django
            url = f"{BASE_URL}/citas/crear/"
            respuesta = requests.post(url, json=datos)
            
            if respuesta.status_code == 201:
                estado_texto.value = f"✅ ¡CITA CONFIRMADA CON {nombre_emp}!"
                estado_texto.color = "green"
                page.snack_bar = ft.SnackBar(ft.Text("¡Reserva Exitosa!"), bgcolor="green")
            else:
                estado_texto.value = f"❌ Error del servidor: {respuesta.text}"
                estado_texto.color = "red"
                page.snack_bar = ft.SnackBar(ft.Text("Falló la reserva"), bgcolor="red")

        except Exception as ex:
            estado_texto.value = f"❌ Error de conexión: {str(ex)}"
            estado_texto.color = "red"

        page.snack_bar.open = True
        page.update()

    # --- 2. CARGAR DATOS INICIALES ---
    dd_servicio = ft.Dropdown(label="Selecciona Servicio", width=300)
    dd_empleado = ft.Dropdown(label="Empleado (Opcional)", width=300)
    campo_fecha = ft.TextField(label="Fecha (YYYY-MM-DD)", hint_text="2025-11-29", width=300)
    lista_resultados = ft.Column(spacing=10)

    def cargar_datos_iniciales():
        nonlocal lista_empleados_cache
        try:
            # Cargar Servicios
            res_s = requests.get(f"{BASE_URL}/servicios/")
            for s in res_s.json():
                dd_servicio.options.append(ft.dropdown.Option(key=str(s['id']), text=s['nombre']))
            
            # Cargar Empleados
            res_e = requests.get(f"{BASE_URL}/empleados/")
            lista_empleados_cache = res_e.json() # Guardamos en la variable global
            
            dd_empleado.options.append(ft.dropdown.Option(key="todos", text="Cualquiera"))
            for emp in lista_empleados_cache:
                dd_empleado.options.append(ft.dropdown.Option(key=str(emp['id']), text=emp['nombre']))
            
            estado_texto.value = "✅ Datos cargados correctamente. Listo para buscar."
            estado_texto.color = "green"
            
        except Exception as e:
            estado_texto.value = f"⚠️ Error cargando datos: {e} (¿Django está corriendo?)"
            estado_texto.color = "orange"
        page.update()

  # --- 3. BOTÓN DE BÚSQUEDA CON FILTRO DE EMPLEADO ---
    def buscar_horarios(e):
        lista_resultados.controls.clear()
        sid = dd_servicio.value
        fecha = campo_fecha.value
        id_empleado_seleccionado = dd_empleado.value # Obtenemos a quién eligió el usuario
        
        if not sid or not fecha:
            estado_texto.value = "⚠️ Falta servicio o fecha"
            estado_texto.color = "yellow"
            page.update()
            return

        try:
            # Pedimos TODOS los horarios a Django
            url = f"{BASE_URL}/disponibilidad/?service_id={sid}&fecha={fecha}"
            resp = requests.get(url)
            data = resp.json()

            if not data:
                lista_resultados.controls.append(ft.Text("No hay horarios libres."))
            
            horarios_encontrados = False

            for nombre_emp, horarios in data.items():
                # Buscamos el objeto empleado para saber su ID real
                emp_obj = next((emp for emp in lista_empleados_cache if emp['nombre'] == nombre_emp), None)
                
                if emp_obj:
                    # --- EL PORTERO (FILTRO) ---
                    # Si el usuario eligió a alguien específico (no "todos") 
                    # Y ese alguien NO es el empleado actual del bucle...
                    # ¡SALTAMOS AL SIGUIENTE! (No creamos botón)
                    if id_empleado_seleccionado != "todos" and str(id_empleado_seleccionado) != str(emp_obj['id']):
                        continue 
                    # ---------------------------

                    horarios_encontrados = True
                    for h in horarios:
                        btn = ft.ElevatedButton(
                            text=f"Reservar {h['hora_inicio']} con {nombre_emp}",
                            bgcolor="blue",
                            color="white",
                            on_click=lambda e, en=nombre_emp, eid=emp_obj['id'], s=sid, hi=h['hora_inicio'], hf=h['hora_fin'], f=fecha: guardar_cita_en_django(e, en, eid, s, hi, hf, f)
                        )
                        lista_resultados.controls.append(btn)
            
            if not horarios_encontrados:
                 lista_resultados.controls.append(ft.Text(f"No hay horarios para ese empleado en esta fecha.", color="orange"))

            estado_texto.value = "Resultados actualizados."
            estado_texto.color = "white"

        except Exception as ex:
            estado_texto.value = f"Error al buscar: {ex}"
            estado_texto.color = "red"
        
        page.update()

    # --- 4. ARMADO DE LA PANTALLA ---
    btn_buscar = ft.ElevatedButton("Buscar Disponibilidad", on_click=buscar_horarios, bgcolor="green", color="white")
    
    page.add(
        ft.Text("Sistema de Agendamiento", size=30),
        dd_servicio,
        dd_empleado,
        campo_fecha,
        btn_buscar,
        ft.Divider(),
        ft.Text("Estado del Sistema:", size=12, weight="bold"),
        estado_texto, # <--- AQUÍ VERÁS LOS MENSAJES
        ft.Divider(),
        ft.Text("Horarios:"),
        lista_resultados
    )
    
    cargar_datos_iniciales()

ft.app(target=main)