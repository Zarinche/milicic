import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def explorar_archivo():
    archivo = filedialog.askopenfilename(
        title="Seleccionar archivo o aplicación",
        filetypes=[
            ("Todos los archivos", "*.*"),
            ("Ejecutables", "*.exe"),
            ("Archivos Batch", "*.bat"),
            ("Acceso directo", "*.lnk"),
        ],
    )
    if archivo:
        entry_comando.delete(0, tk.END)
        entry_comando.insert(0, f'"{archivo}"')


def toggle_sin_hora():
    if var_sin_hora.get():
        combo_hora.config(state="disabled")
        combo_min.config(state="disabled")
        btn_add_hora.config(state="disabled")
        btn_del_hora.config(state="disabled")
        listbox_horarios.config(state="disabled")
    else:
        combo_hora.config(state="readonly")
        combo_min.config(state="readonly")
        btn_add_hora.config(state="normal")
        btn_del_hora.config(state="normal")
        listbox_horarios.config(state="normal")


def agregar_horario():
    h = combo_hora.get()
    m = combo_min.get()
    tiempo = f"{h}:{m}"
    horarios_actuales = list(listbox_horarios.get(0, tk.END))
    if tiempo not in horarios_actuales:
        listbox_horarios.insert(tk.END, tiempo)


def quitar_horario():
    seleccion = listbox_horarios.curselection()
    if seleccion:
        listbox_horarios.delete(seleccion[0])
    else:
        messagebox.showwarning(
            "Atención", "Selecciona un horario de la lista para quitar."
        )


def toggle_tipo():
    if var_tipo.get() == "app":
        btn_explorar.config(state="normal")
    else:
        btn_explorar.config(state="disabled")
        entry_comando.delete(0, tk.END)
        entry_comando.insert(
            0,
            "ms-powerautomate:/console/flow/run?environmentid=...&workflowid=...",
        )


def generar_script():
    # Días de la semana
    dias_sel = [str(k) for k, v in dias_vals.items() if v]
    if not dias_sel:
        messagebox.showerror(
            "Atención", "Selecciona al menos un día de la semana."
        )
        return
    str_dias = "*" if len(dias_sel) == 7 else ",".join(dias_sel)

    # Meses
    meses_sel = [str(k) for k, v in meses_vals.items() if v]
    if not meses_sel:
        messagebox.showerror("Atención", "Selecciona al menos un mes.")
        return
    str_meses = "*" if len(meses_sel) == 12 else ",".join(meses_sel)

    # Días del mes (1 al 31)
    dias_mes_sel = [str(k) for k, v in dias_mes_vals.items() if v]
    if not dias_mes_sel:
        messagebox.showerror(
            "Atención", "Selecciona al menos un día del mes (1-31)."
        )
        return
    str_dias_mes = "*" if len(dias_mes_sel) == 31 else ",".join(dias_mes_sel)

    sin_hora = var_sin_hora.get()
    horarios_lista = list(listbox_horarios.get(0, tk.END))

    if not sin_hora and not horarios_lista:
        messagebox.showerror(
            "Atención", "Agrega al menos un horario o marca 'Sin hora'."
        )
        return

    comando = entry_comando.get().strip()
    if not comando:
        messagebox.showerror("Atención", "Falta la ruta o el enlace.")
        return

    # Limpiamos comillas externas para manejarlas de forma segura con Chr(34)
    comando_limpio = comando.strip('"')

    # Convertimos la lista de horas a formato VBScript Array (ej. Array("08:00:00", "14:30:00"))
    vbs_times_array = (
        ", ".join([f'"{h}:00"' for h in horarios_lista])
        if horarios_lista
        else '"00:00:00"'
    )

    logica_espera = ""
    if not sin_hora:
        logica_espera = f"""
targetDays = ",{str_dias},"
targetMonths = ",{str_meses},"
targetMonthDays = ",{str_dias_mes},"
timesArr = Array({vbs_times_array})
executedTimes = ","

Do While True
    On Error Resume Next
    currDate = Date
    currTime = Time
    wd = CStr(Weekday(currDate))
    m = CStr(Month(currDate))
    d = CStr(Day(currDate))
    
    okDay = False
    If targetDays = ",*," Then okDay = True
    If InStr(targetDays, "," & wd & ",") > 0 Then okDay = True
    
    okMonth = False
    If targetMonths = ",*," Then okMonth = True
    If InStr(targetMonths, "," & m & ",") > 0 Then okMonth = True

    okMonthDay = False
    If targetMonthDays = ",*," Then okMonthDay = True
    If InStr(targetMonthDays, "," & d & ",") > 0 Then okMonthDay = True
    
    If okDay And okMonth And okMonthDay Then
        Dim t, runKey
        For Each t In timesArr
            runKey = CStr(currDate) & "_" & t
            If currTime >= TimeValue(t) And InStr(executedTimes, "," & runKey & ",") = 0 Then
                ' Ejecución segura del comando
                WshShell.Run "cmd /c start " & Chr(34) & Chr(34) & " " & Chr(34) & "{comando_limpio}" & Chr(34), 0, False
                
                {logica_clic_indentada(var_clic.get(), entry_titulo.get())}
                
                executedTimes = executedTimes & runKey & ","
            End If
        Next
    End If
    WScript.Sleep 15000
Loop
"""
    else:
        logica_espera = f"""
' Ejecución inmediata sin esperas de horario
WshShell.Run "cmd /c start " & Chr(34) & Chr(34) & " " & Chr(34) & "{comando_limpio}" & Chr(34), 0, False
{logica_clic_indentada(var_clic.get(), entry_titulo.get())}
"""

    vbs_content = f"""On Error Resume Next
Set WshShell = WScript.CreateObject("WScript.Shell")



{logica_espera}
"""

    startup_dir = os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    )
    archivo_guardado = filedialog.asksaveasfilename(
        initialdir=startup_dir,
        defaultextension=".vbs",
        filetypes=[
            ("Script VBScript Nativo (.vbs)", "*.vbs"),
            ("Todos los archivos", "*.*"),
        ],
        initialfile="Automatizador.vbs",
    )

    if archivo_guardado:
        with open(archivo_guardado, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        messagebox.showinfo(
            "Éxito", "¡Guardado correctamente en la carpeta de inicio!"
        )


def logica_clic_indentada(activo, titulo_txt):
    if not activo:
        return ""
    titulo = titulo_txt.strip() or "Ejecutar flujo"
    return f"""
Dim intentos
intentos = 0
Do While intentos < 120
    On Error Resume Next
    If WshShell.AppActivate("{titulo}") Then
        WScript.Sleep 400
        WshShell.SendKeys "{{ENTER}}"
        Exit Do
    End If
    intentos = intentos + 1
    WScript.Sleep 1000
Loop
"""


# Configuración de la Interfaz Principal
root = tk.Tk()
root.title("Automatizador Avanzado")
root.geometry("460x550")
root.resizable(False, False)

BG_DARK = "#282a36"
BG_CURRENT = "#44475a"
FG_LIGHT = "#f8f8f2"
PURPLE = "#bd93f9"
GREEN = "#50fa7b"
CYAN = "#8be9fd"

root.config(bg=BG_DARK)

dias_vals = {i: True for i in range(1, 8)}
meses_vals = {i: True for i in range(1, 13)}
dias_mes_vals = {i: True for i in range(1, 32)}

dias_btns = {}
meses_btns = {}
dias_mes_btns = {}


def toggle_dia(v):
    dias_vals[v] = not dias_vals[v]
    dias_btns[v].config(
        bg=PURPLE if dias_vals[v] else BG_CURRENT,
        fg=BG_DARK if dias_vals[v] else FG_LIGHT,
    )


def toggle_mes(v):
    meses_vals[v] = not meses_vals[v]
    meses_btns[v].config(
        bg=CYAN if meses_vals[v] else BG_CURRENT,
        fg=BG_DARK if meses_vals[v] else FG_LIGHT,
    )


def toggle_dia_mes(v):
    dias_mes_vals[v] = not dias_mes_vals[v]
    dias_mes_btns[v].config(
        bg=CYAN if dias_mes_vals[v] else BG_CURRENT,
        fg=BG_DARK if dias_mes_vals[v] else FG_LIGHT,
    )


f = tk.Frame(root, bg=BG_DARK)
f.pack(fill="both", expand=True, padx=12, pady=8)

# --- MESES ---
tk.Label(
    f,
    text="Meses permitidos:",
    bg=BG_DARK,
    fg=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(anchor="center", pady=(0, 1))
f_meses1 = tk.Frame(f, bg=BG_DARK)
f_meses1.pack(anchor="center", pady=(0, 1))
f_meses2 = tk.Frame(f, bg=BG_DARK)
f_meses2.pack(anchor="center", pady=(0, 3))

meses_info = [
    ("Ene", 1),
    ("Feb", 2),
    ("Mar", 3),
    ("Abr", 4),
    ("May", 5),
    ("Jun", 6),
    ("Jul", 7),
    ("Ago", 8),
    ("Sep", 9),
    ("Oct", 10),
    ("Nov", 11),
    ("Dic", 12),
]
for i, (nom, val) in enumerate(meses_info):
    target = f_meses1 if i < 6 else f_meses2
    btn = tk.Button(
        target,
        text=nom,
        width=4,
        bg=CYAN,
        fg=BG_DARK,
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        command=lambda v=val: toggle_mes(v),
    )
    btn.pack(side="left", padx=1, ipady=1)
    meses_btns[val] = btn

# --- DÍAS DE LA SEMANA ---
tk.Label(
    f,
    text="Días de la semana:",
    bg=BG_DARK,
    fg=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(anchor="center", pady=(2, 1))
f_dias = tk.Frame(f, bg=BG_DARK)
f_dias.pack(anchor="center", pady=(0, 3))
for nom, val in [
    ("Dom", 1),
    ("Lun", 2),
    ("Mar", 3),
    ("Mié", 4),
    ("Jue", 5),
    ("Vie", 6),
    ("Sáb", 7),
]:
    btn = tk.Button(
        f_dias,
        text=nom,
        width=4,
        bg=PURPLE,
        fg=BG_DARK,
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        command=lambda v=val: toggle_dia(v),
    )
    btn.pack(side="left", padx=1, ipady=1)
    dias_btns[val] = btn

# --- DÍAS DEL MES (1 al 31) ---
tk.Label(
    f,
    text="Días del mes específicos (1-31):",
    bg=BG_DARK,
    fg=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(anchor="center", pady=(2, 1))

f_dias_mes_main = tk.Frame(f, bg=BG_DARK)
f_dias_mes_main.pack(anchor="center", pady=(0, 4))

for row in range(5):
    f_row = tk.Frame(f_dias_mes_main, bg=BG_DARK)
    f_row.pack(anchor="center", pady=1)
    for col in range(7):
        day_num = row * 7 + col + 1
        if day_num <= 31:
            btn = tk.Button(
                f_row,
                text=str(day_num),
                width=3,
                bg=CYAN,
                fg=BG_DARK,
                font=("Segoe UI", 7, "bold"),
                relief="flat",
                command=lambda v=day_num: toggle_dia_mes(v),
            )
            btn.pack(side="left", padx=1, ipady=0)
            dias_mes_btns[day_num] = btn



# --- MÚLTIPLES HORARIOS ---
f2 = tk.Frame(f, bg=BG_DARK)
f2.pack(fill="x", pady=(2, 3))

tk.Label(
    f2,
    text="Horarios de ejecución:",
    bg=BG_DARK,
    fg=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(anchor="w", pady=(0, 1))

f_h_controls = tk.Frame(f2, bg=BG_DARK)
f_h_controls.pack(fill="x", pady=(0, 2))

combo_hora = ttk.Combobox(
    f_h_controls,
    values=[f"{i:02d}" for i in range(24)],
    width=3,
    state="readonly",
    font=("Segoe UI", 8),
)
combo_hora.set("08")
combo_hora.pack(side="left", padx=(0, 2))

tk.Label(
    f_h_controls, text=":", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 9)
).pack(side="left")

combo_min = ttk.Combobox(
    f_h_controls,
    values=[f"{i:02d}" for i in range(60)],
    width=3,
    state="readonly",
    font=("Segoe UI", 8),
)
combo_min.set("30")
combo_min.pack(side="left", padx=(2, 6))

btn_add_hora = tk.Button(
    f_h_controls,
    text="+ Agregar",
    bg=PURPLE,
    fg=BG_DARK,
    font=("Segoe UI", 8, "bold"),
    relief="flat",
    command=agregar_horario,
)
btn_add_hora.pack(side="left", padx=2)

btn_del_hora = tk.Button(
    f_h_controls,
    text="- Quitar",
    bg=BG_CURRENT,
    fg=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
    relief="flat",
    command=quitar_horario,
)
btn_del_hora.pack(side="left", padx=2)

var_sin_hora = tk.BooleanVar(value=False)
chk_sin_hora = tk.Checkbutton(
    f_h_controls,
    text="Sin hora",
    variable=var_sin_hora,
    command=toggle_sin_hora,
    bg=BG_DARK,
    fg=CYAN,
    selectcolor=BG_CURRENT,
    activebackground=BG_DARK,
    activeforeground=CYAN,
    font=("Segoe UI", 8, "bold"),
)
chk_sin_hora.pack(side="right")

# Listbox de horarios agregados
f_list = tk.Frame(f2, bg=BG_DARK)
f_list.pack(fill="x", pady=(1, 2))

listbox_horarios = tk.Listbox(
    f_list,
    height=3,
    bg=BG_CURRENT,
    fg=FG_LIGHT,
    font=("Segoe UI", 8),
    relief="flat",
    selectbackground=PURPLE,
)
listbox_horarios.pack(side="left", fill="x", expand=True)
listbox_horarios.insert(tk.END, "08:30")  # Horario por defecto inicial

scrollbar_h = tk.Scrollbar(
    f_list, orient="vertical", command=listbox_horarios.yview
)
scrollbar_h.pack(side="right", fill="y")
listbox_horarios.config(yscrollcommand=scrollbar_h.set)
# --- SELECTOR APP VS LINK ---
f_tipo = tk.Frame(f, bg=BG_DARK)
f_tipo.pack(anchor="center", pady=(2, 3))
var_tipo = tk.StringVar(value="app")
tk.Radiobutton(
    f_tipo,
    text="Aplicación / Archivo",
    variable=var_tipo,
    value="app",
    command=toggle_tipo,
    bg=BG_DARK,
    fg=FG_LIGHT,
    selectcolor=BG_CURRENT,
    activebackground=BG_DARK,
    activeforeground=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(side="left", padx=8)
tk.Radiobutton(
    f_tipo,
    text="Enlace (URI)",
    variable=var_tipo,
    value="link",
    command=toggle_tipo,
    bg=BG_DARK,
    fg=FG_LIGHT,
    selectcolor=BG_CURRENT,
    activebackground=BG_DARK,
    activeforeground=FG_LIGHT,
    font=("Segoe UI", 8, "bold"),
).pack(side="left", padx=8)
# --- RUTA O ENLACE ---
tk.Label(
    f,
    text="Ruta del Archivo o Enlace URI:",
    bg=BG_DARK,
    fg=CYAN,
    font=("Segoe UI", 8, "bold"),
).pack(anchor="w", pady=(1, 1))
f3 = tk.Frame(f, bg=BG_DARK)
f3.pack(fill="x", pady=(0, 3))

entry_comando = tk.Entry(
    f3,
    bg=BG_CURRENT,
    fg=FG_LIGHT,
    insertbackground=FG_LIGHT,
    relief="flat",
    font=("Segoe UI", 9),
)
entry_comando.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 5))
btn_explorar = tk.Button(
    f3,
    text="Examinar",
    bg=PURPLE,
    fg=BG_DARK,
    font=("Segoe UI", 8, "bold"),
    relief="flat",
    command=explorar_archivo,
)
btn_explorar.pack(side="right")

# --- ENTER AUTOMÁTICO ---
var_clic = tk.BooleanVar(value=False)
chk_clic = tk.Checkbutton(
    f,
    text="Enter automático en ventana:",
    variable=var_clic,
    bg=BG_DARK,
    fg=FG_LIGHT,
    selectcolor=BG_CURRENT,
    activebackground=BG_DARK,
    activeforeground=FG_LIGHT,
    font=("Segoe UI", 8),
)
chk_clic.pack(anchor="w", pady=(2, 1))

entry_titulo = tk.Entry(
    f,
    bg=BG_CURRENT,
    fg=FG_LIGHT,
    insertbackground=FG_LIGHT,
    relief="flat",
    font=("Segoe UI", 9),
)
entry_titulo.insert(0, "Ejecutar flujo")
entry_titulo.pack(fill="x", ipady=2, pady=(0, 4))

# --- BOTÓN GUARDAR ---
tk.Button(
    f,
    text="¡Guardar en Inicio (Shell:Startup)!",
    bg=GREEN,
    fg=BG_DARK,
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    command=generar_script,
).pack(fill="x", ipady=5, pady=(2, 0))

root.mainloop()