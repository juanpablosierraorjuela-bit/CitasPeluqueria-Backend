import os

path = 'salon/templates/salon/index.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# REEMPLAZO QUIRÚRGICO:
# Cambiamos la lógica vieja (perfil.es_dueño) por la nueva (tenants.exists)
old_logic = "{% if request.user.perfil.es_dueño %}"
new_logic = "{% if request.user.tenants.exists %}"

if old_logic in content:
    new_content = content.replace(old_logic, new_logic)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ LOGICA CORREGIDA: Ahora el botón 'Mi Negocio' aparecerá para los dueños.")
else:
    print("⚠️ No encontré la línea vieja, quizás ya estaba corregida o es diferente.")

# TAMBIÉN ASEGURAMOS QUE EL LINK DE "SOY DUEÑO" LLEVE AL LOGIN SIEMPRE
# (Por si acaso)
