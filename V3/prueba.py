import os
import textwrap
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# --- PALETA DE DISEÑO OSCURA ---
BG_DARK = "#282a36"
BG_CURRENT = "#44475a"
BG_CHIP = "#3a3d4d"
FG_LIGHT = "#f8f8f2"
PURPLE = "#bd93f9"
GREEN = "#50fa7b"
CYAN = "#8be9fd"
PINK = "#ff79c6"

NOMBRES_DIA = {1: "Dom", 2: "Lun", 3: "Mar", 4: "Mié", 5: "Jue", 6: "Vie", 7: "Sáb"}
NOMBRES_MES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}


class ValidationError(Exception):
    pass


# =====================================================================
# ESTADO GLOBAL
# =====================================================================
apps_pool = []          # [{"id": int, "nombre": str, "ruta": str, "enter_auto": bool}, ...]
_next_app_id = [1]

dias_vals = {d: True for d in range(1, 8)}
dias_btns = {}
meses_vals = {m: True for m in range(1, 13)}
meses_btns = {}
dias_mes_vals = {d: True for d in range(1, 32)}
dias_mes_btns = {}

estado = {"sin_hora": False}

horarios = [{
    "hora": "08", "min": "30", "apps": [],
    "dias_vals": dict(dias_vals), "meses_vals": dict(meses_vals),
    "dias_mes_vals": dict(dias_mes_vals),
}]

refs = {
    "combo_hora": None, "combo_min": None, "chk_sin_hora": None,
    "controls_widgets": [], "horarios_container": None,
}

drag_state = {"active": False, "source": None, "app": None, "float_win": None}
pool_row_refs = []


# =====================================================================
# HELPERS DE TOGGLE (días / meses / días del mes)
# =====================================================================
def make_toggle(vals, btns, key, color):
    def _t():
        vals[key] = not vals[key]
        btns[key].config(
            bg=color if vals[key] else BG_CURRENT,
            fg=BG_DARK if vals[key] else FG_LIGHT,
        )
    return _t


def build_dias_semana(parent):
    inner = tk.Frame(parent, bg=BG_CURRENT)
    inner.pack(anchor="center")
    for val, nom in NOMBRES_DIA.items():
        btn = tk.Button(
            inner, text=nom, width=2, bg=PURPLE, fg=BG_DARK,
            font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(dias_vals, dias_btns, val, PURPLE),
        )
        btn.pack(side="left", padx=1, ipady=1)
        dias_btns[val] = btn


def build_meses(parent):
    f_m1 = tk.Frame(parent, bg=BG_CURRENT)
    f_m1.pack(anchor="center", pady=1)
    f_m2 = tk.Frame(parent, bg=BG_CURRENT)
    f_m2.pack(anchor="center", pady=1)
    for val, nom in NOMBRES_MES.items():
        target = f_m1 if val <= 6 else f_m2
        btn = tk.Button(
            target, text=nom, width=2, bg=CYAN, fg=BG_DARK,
            font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(meses_vals, meses_btns, val, CYAN),
        )
        btn.pack(side="left", padx=1, ipady=1)
        meses_btns[val] = btn


def build_dias_mes_grid(parent):
    for row in range(5):
        f_row = tk.Frame(parent, bg=BG_CURRENT)
        f_row.pack(anchor="center", pady=1)
        for col in range(7):
            day_num = row * 7 + col + 1
            if day_num <= 31:
                btn = tk.Button(
                    f_row, text=str(day_num), width=2, bg=CYAN, fg=BG_DARK,
                    font=("Segoe UI", 6, "bold"), relief="flat", cursor="hand2",
                    command=make_toggle(dias_mes_vals, dias_mes_btns, day_num, CYAN),
                )
                btn.pack(side="left", padx=1, ipady=0)
                dias_mes_btns[day_num] = btn


# =====================================================================
# DRAG & DROP INTERNO
# =====================================================================
def walk_up_for_attr(widget, attr):
    w = widget
    for _ in range(8):
        if w is None:
            return None
        if hasattr(w, attr):
            return getattr(w, attr)
        try:
            w = w.master
        except AttributeError:
            return None
    return None


def start_drag(event, app_copy, source):
    drag_state["active"] = True
    drag_state["app"] = dict(app_copy)
    drag_state["source"] = source

    fw = tk.Toplevel(root)
    fw.overrideredirect(True)
    fw.attributes("-topmost", True)
    txt_label = "📦 " + app_copy["nombre"] + (" ↵" if app_copy.get("enter_auto") else "")
    tk.Label(
        fw, text=txt_label, bg=PURPLE, fg=BG_DARK,
        font=("Segoe UI", 8, "bold"), padx=6, pady=2,
    ).pack()
    fw.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
    drag_state["float_win"] = fw


def on_drag_motion(event):
    if not drag_state["active"] or drag_state["float_win"] is None:
        return
    drag_state["float_win"].geometry(f"+{event.x_root + 12}+{event.y_root + 12}")


def on_drag_release(event):
    if not drag_state["active"]:
        return
    drag_state["active"] = False
    if drag_state["float_win"] is not None:
        drag_state["float_win"].destroy()
        drag_state["float_win"] = None

    target_widget = root.winfo_containing(event.x_root, event.y_root)
    drop_horario = walk_up_for_attr(target_widget, "_drop_target")
    drop_pool = walk_up_for_attr(target_widget, "_pool_target")

    app = drag_state["app"]
    source = drag_state["source"]

    if drop_horario is not None:
        h_idx = drop_horario
        nuevo = {
            "nombre": app["nombre"],
            "ruta": app["ruta"],
            "enter_auto": app.get("enter_auto", False),
            "titulo": "Ejecutar flujo"
        }
        if source[0] == "horario":
            _quitar_app_de_horario(*source[1:])
        horarios[h_idx]["apps"].append(nuevo)
        refresh_horarios_ui()

    elif drop_pool is not None:
        if source[0] == "pool":
            idx = compute_pool_drop_index(event.y_root)
            actual_idx = next((i for i, a in enumerate(apps_pool) if a["id"] == app["id"]), None)
            if actual_idx is not None:
                item = apps_pool.pop(actual_idx)
                if idx > actual_idx:
                    idx -= 1
                apps_pool.insert(idx, item)
                refresh_pool_ui()
        elif source[0] == "horario":
            _quitar_app_de_horario(*source[1:])
            refresh_horarios_ui()

    drag_state["app"] = None
    drag_state["source"] = None


def _quitar_app_de_horario(h_idx, a_idx):
    apps = horarios[h_idx]["apps"]
    if 0 <= a_idx < len(apps):
        apps.pop(a_idx)


def compute_pool_drop_index(y_root):
    if not pool_row_refs:
        return 0
    for i, row in enumerate(pool_row_refs):
        try:
            ry = row.winfo_rooty() + row.winfo_height() / 2
        except tk.TclError:
            continue
        if y_root < ry:
            return i
    return len(pool_row_refs)


# =====================================================================
# POOL DE APPS GUARDADAS
# =====================================================================
def abrir_dialogo_nueva_app():
    top = tk.Toplevel(root)
    top.title("Nueva app")
    top.config(bg=BG_CURRENT, padx=10, pady=10)
    top.resizable(False, False)

    tk.Label(top, text="Nombre:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 8, "bold")).pack(anchor="w")
    entry_nombre = tk.Entry(top, bg=BG_DARK, fg=FG_LIGHT,
                             insertbackground=FG_LIGHT, relief="flat",
                             font=("Segoe UI", 9), width=28)
    entry_nombre.pack(fill="x", ipady=2, pady=(0, 6))

    tk.Label(top, text="Ruta del archivo / enlace URI:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 8, "bold")).pack(anchor="w")
    f_ruta = tk.Frame(top, bg=BG_CURRENT)
    f_ruta.pack(fill="x", pady=(0, 6))
    entry_ruta = tk.Entry(f_ruta, bg=BG_DARK, fg=FG_LIGHT,
                           insertbackground=FG_LIGHT, relief="flat",
                           font=("Segoe UI", 9))
    entry_ruta.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))

    def examinar():
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo o aplicación",
            filetypes=[("Todos los archivos", "*.*"), ("Ejecutables", "*.exe")],
        )
        if archivo:
            entry_ruta.delete(0, tk.END)
            entry_ruta.insert(0, archivo)
            if not entry_nombre.get().strip():
                entry_nombre.insert(0, os.path.splitext(os.path.basename(archivo))[0])

    tk.Button(f_ruta, text="Examinar", bg=PURPLE, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=examinar).pack(side="right")

    # Checkbox para Enter automático
    enter_var = tk.BooleanVar(value=False)
    chk_enter = tk.Checkbutton(
        top, text="Presionar Enter automáticamente", variable=enter_var,
        bg=BG_CURRENT, fg=FG_LIGHT, selectcolor=BG_DARK,
        activebackground=BG_CURRENT, activeforeground=FG_LIGHT,
        font=("Segoe UI", 8)
    )
    chk_enter.pack(anchor="w", pady=(0, 8))

    f_btns = tk.Frame(top, bg=BG_CURRENT)
    f_btns.pack(fill="x")

    def agregar():
        ruta = entry_ruta.get().strip()
        if not ruta:
            messagebox.showerror("Atención", "Falta la ruta o el enlace.", parent=top)
            return
        nombre = entry_nombre.get().strip() or os.path.basename(ruta.strip('"'))
        apps_pool.append({
            "id": _next_app_id[0],
            "nombre": nombre,
            "ruta": ruta.strip('"'),
            "enter_auto": enter_var.get()
        })
        _next_app_id[0] += 1
        refresh_pool_ui()
        top.destroy()

    tk.Button(f_btns, text="Agregar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=agregar).pack(side="left", expand=True, fill="x", padx=(0, 3))
    tk.Button(f_btns, text="Cancelar", bg=BG_DARK, fg=FG_LIGHT,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=top.destroy).pack(side="left", expand=True, fill="x", padx=(3, 0))


def eliminar_app_pool(app_id):
    idx = next((i for i, a in enumerate(apps_pool) if a["id"] == app_id), None)
    if idx is not None:
        apps_pool.pop(idx)
        refresh_pool_ui()


def on_desktop_drop(event):
    try:
        paths = root.tk.splitlist(event.data)
    except Exception:
        paths = [event.data]
    for ruta in paths:
        nombre = os.path.splitext(os.path.basename(ruta.strip('"')))[0]
        apps_pool.append({
            "id": _next_app_id[0],
            "nombre": nombre,
            "ruta": ruta.strip('"'),
            "enter_auto": False
        })
        _next_app_id[0] += 1
    refresh_pool_ui()


def refresh_pool_ui():
    for w in pool_list_frame.winfo_children():
        w.destroy()
    pool_row_refs.clear()

    if not apps_pool:
        tk.Label(pool_list_frame, text="Sin apps.",
                 bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 7)).pack(
            anchor="w", padx=4, pady=6)
        return

    for app in apps_pool:
        row = tk.Frame(pool_list_frame, bg=BG_CHIP)
        row.pack(fill="x", pady=1, padx=2)

        handle = tk.Label(row, text="≡", bg=BG_CHIP, fg=PINK,
                           font=("Segoe UI", 8, "bold"), cursor="fleur")
        handle.pack(side="left", padx=(2, 2))
        
        texto_app = app["nombre"] + (" ↵" if app.get("enter_auto") else "")
        lbl = tk.Label(row, text=texto_app, bg=BG_CHIP, fg=FG_LIGHT,
                        font=("Segoe UI", 7), cursor="fleur", anchor="w")
        lbl.pack(side="left", fill="x", expand=True, padx=2, pady=2)
        
        btn_del = tk.Button(row, text="×", bg=BG_CHIP, fg=PINK, relief="flat",
                             font=("Segoe UI", 7, "bold"), cursor="hand2", bd=0,
                             command=lambda aid=app["id"]: eliminar_app_pool(aid))
        btn_del.pack(side="right", padx=2)

        for w in (row, handle, lbl):
            w.bind("<ButtonPress-1>", lambda e, a=app: start_drag(e, a, ("pool",)))

        pool_row_refs.append(row)


# =====================================================================
# HORARIOS + APPS
# =====================================================================
def _resumen_calendario(h):
    def _fmt(vals, nombres):
        activos = [k for k, v in vals.items() if v]
        if len(activos) == len(vals):
            return "todos"
        if not activos:
            return "ninguno"
        return ",".join(nombres[k] for k in activos) if nombres else ",".join(str(k) for k in activos)

    dias_txt = _fmt(h["dias_vals"], NOMBRES_DIA)
    meses_txt = _fmt(h["meses_vals"], NOMBRES_MES)
    return f"D: {dias_txt} | M: {meses_txt}"


def toggle_sin_hora():
    estado["sin_hora"] = not estado["sin_hora"]
    tk_estado = "disabled" if estado["sin_hora"] else "readonly"
    btn_estado = "disabled" if estado["sin_hora"] else "normal"
    refs["combo_hora"].config(state=tk_estado)
    refs["combo_min"].config(state=tk_estado)
    for w in refs["controls_widgets"]:
        w.config(state=btn_estado)
    refs["chk_sin_hora"].config(
        bg=CYAN if estado["sin_hora"] else BG_CURRENT,
        fg=BG_DARK if estado["sin_hora"] else CYAN,
    )


def agregar_horario():
    h = refs["combo_hora"].get()
    m = refs["combo_min"].get()
    horarios.append({
        "hora": h, "min": m, "apps": [],
        "dias_vals": dict(dias_vals), "meses_vals": dict(meses_vals),
        "dias_mes_vals": dict(dias_mes_vals),
    })
    refresh_horarios_ui()


def quitar_horario(h_idx):
    if 0 <= h_idx < len(horarios):
        horarios.pop(h_idx)
    refresh_horarios_ui()


def quitar_app_chip(h_idx, a_idx):
    _quitar_app_de_horario(h_idx, a_idx)
    refresh_horarios_ui()


def refresh_horarios_ui():
    container = refs["horarios_container"]
    if container is None:
        return
    for w in container.winfo_children():
        w.destroy()

    if not horarios:
        tk.Label(container, text="Sin horarios.", bg=BG_DARK,
                 fg=FG_LIGHT, font=("Segoe UI", 7)).pack(anchor="w", pady=4)
        return

    for h_idx, h in enumerate(horarios):
        row = tk.Frame(container, bg=BG_DARK)
        row.pack(fill="x", pady=(0, 4))

        top_row = tk.Frame(row, bg=BG_DARK)
        top_row.pack(fill="x")
        tk.Label(top_row, text=f"⏰ {h['hora']}:{h['min']}", bg=BG_DARK, fg=CYAN,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(2, 4))
        tk.Button(top_row, text="×", bg=BG_CURRENT, fg=FG_LIGHT,
                  font=("Segoe UI", 7), relief="flat", cursor="hand2",
                  command=lambda hi=h_idx: quitar_horario(hi)).pack(side="right")

        tk.Label(row, text=_resumen_calendario(h), bg=BG_DARK, fg=FG_LIGHT,
                 font=("Segoe UI", 6, "italic"), wraplength=110, justify="left"
                 ).pack(anchor="w", padx=(2, 0))

        drop_zone = tk.Frame(row, bg=BG_CURRENT, padx=2, pady=2)
        drop_zone.pack(fill="x", pady=(2, 0))
        drop_zone._drop_target = h_idx

        if not h["apps"]:
            ph = tk.Label(drop_zone, text="Arrastrá app acá",
                          bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 6, "italic"))
            ph.pack(anchor="w")
            ph._drop_target = h_idx
        else:
            for a_idx, app in enumerate(h["apps"]):
                chip = tk.Frame(drop_zone, bg=BG_CHIP)
                chip.pack(fill="x", pady=1)
                chip._drop_target = h_idx

                texto_chip = "📦 " + app["nombre"] + (" ↵" if app.get("enter_auto") else "")
                lbl = tk.Label(chip, text=texto_chip, bg=BG_CHIP,
                               fg=FG_LIGHT, font=("Segoe UI", 7), cursor="fleur")
                lbl.pack(side="left", padx=2, pady=2)
                lbl._drop_target = h_idx
                lbl.bind("<ButtonPress-1>",
                         lambda e, a=app, hi=h_idx, ai=a_idx:
                         start_drag(e, a, ("horario", hi, ai)))

                tk.Button(chip, text="×", bg=BG_CHIP, fg=PINK, relief="flat", bd=0,
                          font=("Segoe UI", 7, "bold"), cursor="hand2",
                          command=lambda hi=h_idx, ai=a_idx: quitar_app_chip(hi, ai)
                          ).pack(side="right", padx=2)


# =====================================================================
# VISTA PREVIA (pestaña "Flujo")
# =====================================================================
def refresh_preview(*_):
    preview_text.config(state="normal")
    preview_text.delete("1.0", tk.END)

    if estado["sin_hora"]:
        preview_text.insert(tk.END, "⚡ Modo 'Sin hora' activo.\n\n")
        for h in horarios:
            for app in h["apps"]:
                extra = " [Enter automático]" if app.get("enter_auto") else ""
                preview_text.insert(tk.END, f"  📦 {app['nombre']}{extra}\n")
    else:
        for h in horarios:
            preview_text.insert(tk.END, f"⏰ {h['hora']}:{h['min']}\n")
            for app in h["apps"]:
                extra = " [Enter automático]" if app.get("enter_auto") else ""
                preview_text.insert(tk.END, f"    📦 {app['nombre']}{extra}\n")
            preview_text.insert(tk.END, "\n")

    preview_text.config(state="disabled")


# =====================================================================
# GENERACIÓN DEL SCRIPT .VBS
# =====================================================================
def run_app_vbs(app, espera=False):
    ruta_limpia = app["ruta"].strip('"')
    flag = "True" if espera else "False"
    lineas = [
        f'WshShell.Run "cmd /c start " & Chr(34) & Chr(34) & " " & Chr(34) & "{ruta_limpia}" & Chr(34), 0, {flag}'
    ]
    if app.get("enter_auto", False):
        lineas.append('WScript.Sleep 1500')
        lineas.append('WshShell.SendKeys "{ENTER}"')
    return "\n".join(lineas)


def _calcular_espera_por_horario(horarios_con_apps):
    grupos = {}
    for h in horarios_con_apps:
        clave = (h["hora"], h["min"])
        grupos.setdefault(clave, []).append(h)
    espera = {}
    for clave, lista in grupos.items():
        for i, h in enumerate(lista):
            espera[id(h)] = i < len(lista) - 1
    return espera


def build_vbs():
    horarios_con_apps = [h for h in horarios if h["apps"]]
    if not horarios_con_apps:
        raise ValidationError("Agregá al menos un horario y una app.")

    cabecera = [
        "On Error Resume Next",
        'Set WshShell = WScript.CreateObject("WScript.Shell")',
        "Dim t, runKey, intentos",
        'executedTimes = ","',
    ]

    if estado["sin_hora"]:
        cuerpo = ["WScript.Sleep 5000"]
        for h in horarios_con_apps:
            for app in h["apps"]:
                cuerpo.append(run_app_vbs(app))
        return "\n".join(cabecera + cuerpo) + "\n"

    espera_por_horario = _calcular_espera_por_horario(horarios_con_apps)

    bloques = []
    for h_idx, h in enumerate(horarios_con_apps):
        dias_sel = [str(k) for k, v in h["dias_vals"].items() if v]
        meses_sel = [str(k) for k, v in h["meses_vals"].items() if v]
        diasmes_sel = [str(k) for k, v in h["dias_mes_vals"].items() if v]

        str_dias = "*" if len(dias_sel) == 7 else ",".join(dias_sel)
        str_meses = "*" if len(meses_sel) == 12 else ",".join(meses_sel)
        str_diasmes = "*" if len(diasmes_sel) == 31 else ",".join(diasmes_sel)

        vars_bloque = textwrap.dedent(f"""\
            targetDays{h_idx} = ",{str_dias},"
            targetMonths{h_idx} = ",{str_meses},"
            targetMonthDays{h_idx} = ",{str_diasmes},"
            okDay{h_idx} = False
            If targetDays{h_idx} = ",*," Then okDay{h_idx} = True
            If InStr(targetDays{h_idx}, "," & wd & ",") > 0 Then okDay{h_idx} = True
            okMonth{h_idx} = False
            If targetMonths{h_idx} = ",*," Then okMonth{h_idx} = True
            If InStr(targetMonths{h_idx}, "," & m & ",") > 0 Then okMonth{h_idx} = True
            okMonthDay{h_idx} = False
            If targetMonthDays{h_idx} = ",*," Then okMonthDay{h_idx} = True
            If InStr(targetMonthDays{h_idx}, "," & d & ",") > 0 Then okMonthDay{h_idx} = True""")

        hhmm = f"{h['hora']}:{h['min']}:00"
        runkey = f"h{h_idx}_{h['hora']}{h['min']}"
        espera = espera_por_horario.get(id(h), False)
        cuerpo = "\n".join(run_app_vbs(app, espera=espera) for app in h["apps"])
        cuerpo_indent = textwrap.indent(cuerpo, " " * 8)

        if_bloque = textwrap.dedent(f"""\
            If okDay{h_idx} And okMonth{h_idx} And okMonthDay{h_idx} And currTime >= TimeValue("{hhmm}") Then
                runKey = CStr(currDate) & "_{runkey}"
                If InStr(executedTimes, "," & runKey & ",") = 0 Then
            {cuerpo_indent}
                    executedTimes = executedTimes & runKey & ","
                End If
            End If""")

        bloques.append(vars_bloque + "\n" + if_bloque)

    cuerpo_loop = "\n\n".join(bloques)
    partes = cabecera + [textwrap.dedent("""\
        Do While True
            On Error Resume Next
            currDate = Date
            currTime = Time
            wd = CStr(Weekday(currDate))
            m = CStr(Month(currDate))
            d = CStr(Day(currDate))""")]
    partes.append(textwrap.indent(cuerpo_loop, " " * 4))
    partes.append("    WScript.Sleep 15000\nLoop")
    return "\n".join(partes) + "\n"


def generar_script():
    try:
        vbs_content = build_vbs()
    except ValidationError as e:
        messagebox.showerror("Atención", str(e))
        return

    startup_dir = os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    )
    archivo_guardado = filedialog.asksaveasfilename(
        initialdir=startup_dir,
        defaultextension=".vbs",
        filetypes=[("Script VBScript Nativo (.vbs)", "*.vbs")],
        initialfile="Automatizador.vbs",
    )
    if archivo_guardado:
        with open(archivo_guardado, "w", encoding="utf-8-sig") as f:
            f.write(vbs_content)
        messagebox.showinfo("Éxito", "¡Guardado correctamente!")


# =====================================================================
# VENTANA PRINCIPAL (260x580)
# =====================================================================
root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
root.title("Auto")
root.geometry("260x580")
root.resizable(False, False)
root.config(bg=BG_DARK)

root.bind_all("<B1-Motion>", on_drag_motion)
root.bind_all("<ButtonRelease-1>", on_drag_release)

main_frame = tk.Frame(root, bg=BG_DARK)
main_frame.pack(fill="both", expand=True, padx=4, pady=4)

# --- BOTÓN GUARDAR FINAL (Anclado abajo para que nunca se oculte) ---
tk.Button(
    main_frame, text="Guardar en Inicio", bg=GREEN, fg=BG_DARK,
    font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
    command=generar_script,
).pack(side="bottom", fill="x", ipady=6, pady=(4, 0))

notebook = ttk.Notebook(main_frame)
notebook.pack(side="top", fill="both", expand=True, pady=(0, 2))

# --- PESTAÑA 1: HORARIOS ---
tab_horarios = tk.Frame(notebook, bg=BG_DARK)
notebook.add(tab_horarios, text="Horarios")
inner_h = tk.Frame(tab_horarios, bg=BG_DARK)
inner_h.pack(fill="both", expand=True, padx=2, pady=2)

tk.Label(inner_h, text="DÍAS", bg=BG_DARK, fg=PURPLE,
         font=("Segoe UI", 7, "bold")).pack(anchor="w")
f_dias = tk.Frame(inner_h, bg=BG_CURRENT, padx=1, pady=1)
f_dias.pack(fill="x", pady=(0, 2))
build_dias_semana(f_dias)

tk.Label(inner_h, text="MESES", bg=BG_DARK, fg=CYAN,
         font=("Segoe UI", 7, "bold")).pack(anchor="w")
f_meses = tk.Frame(inner_h, bg=BG_CURRENT, padx=1, pady=1)
f_meses.pack(fill="x", pady=(0, 2))
build_meses(f_meses)

tk.Label(inner_h, text="DÍAS MES", bg=BG_DARK, fg=CYAN,
         font=("Segoe UI", 7, "bold")).pack(anchor="w")
f_dmes = tk.Frame(inner_h, bg=BG_CURRENT, padx=1, pady=1)
f_dmes.pack(fill="x", pady=(0, 2))
build_dias_mes_grid(f_dmes)

f_hor = tk.Frame(inner_h, bg=BG_CURRENT, padx=2, pady=2)
f_hor.pack(fill="both", expand=True, pady=(1, 0))

controls = tk.Frame(f_hor, bg=BG_CURRENT)
controls.pack(fill="x", pady=(0, 2))
combo_hora = ttk.Combobox(controls, values=[f"{i:02d}" for i in range(24)],
                           width=2, state="readonly", font=("Segoe UI", 7))
combo_hora.set("08")
combo_hora.pack(side="left", padx=(0, 1))
tk.Label(controls, text=":", bg=BG_CURRENT, fg=FG_LIGHT,
         font=("Segoe UI", 7)).pack(side="left")
combo_min = ttk.Combobox(controls, values=[f"{i:02d}" for i in range(60)],
                          width=2, state="readonly", font=("Segoe UI", 7))
combo_min.set("00")
combo_min.pack(side="left", padx=(1, 2))
btn_add = tk.Button(controls, text="+", bg=PURPLE, fg=BG_DARK,
                     font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
                     command=agregar_horario)
btn_add.pack(side="left", padx=1)
chk_sin_hora = tk.Button(controls, text="S/H", bg=BG_CURRENT, fg=CYAN,
                          font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
                          command=toggle_sin_hora)
chk_sin_hora.pack(side="right", padx=(2, 0))

# --- DIVIDIDO: izquierda = HORAS con scroll, derecha = APPS con scroll ---
split = tk.Frame(f_hor, bg=BG_CURRENT)
split.pack(fill="both", expand=True)
split.columnconfigure(0, weight=1, uniform="split")
split.columnconfigure(1, weight=1, uniform="split")
split.rowconfigure(0, weight=1)

# 1. PARTE HORA (Con Barra de Desplazamiento Vertical)
f_horarios_outer = tk.Frame(split, bg=BG_DARK)
f_horarios_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 1))

canvas_h = tk.Canvas(f_horarios_outer, bg=BG_DARK, highlightthickness=0)
scrollbar_h = ttk.Scrollbar(f_horarios_outer, orient="vertical", command=canvas_h.yview)
horarios_container = tk.Frame(canvas_h, bg=BG_DARK, padx=2, pady=2)

horarios_container.bind("<Configure>", lambda e: canvas_h.configure(scrollregion=canvas_h.bbox("all")))
canvas_window_h = canvas_h.create_window((0, 0), window=horarios_container, anchor="nw")
canvas_h.bind("<Configure>", lambda e: canvas_h.itemconfig(canvas_window_h, width=e.width))
canvas_h.configure(yscrollcommand=scrollbar_h.set)

canvas_h.pack(side="left", fill="both", expand=True)
scrollbar_h.pack(side="right", fill="y")

# 2. PARTE GUARDAR APPS (Con Barra de Desplazamiento Vertical)
f_pool_card = tk.Frame(split, bg=BG_DARK)
f_pool_card.grid(row=0, column=1, sticky="nsew", padx=(1, 0))

f_pool_header = tk.Frame(f_pool_card, bg=BG_DARK)
f_pool_header.pack(fill="x", pady=(0, 2))
tk.Label(f_pool_header, text="APPS", bg=BG_DARK, fg=CYAN,
         font=("Segoe UI", 7, "bold")).pack(side="left")
tk.Button(f_pool_header, text="+", bg=PURPLE, fg=BG_DARK,
          font=("Segoe UI", 6, "bold"), relief="flat", cursor="hand2",
          command=abrir_dialogo_nueva_app).pack(side="right")

f_pool_scroll_outer = tk.Frame(f_pool_card, bg=BG_DARK)
f_pool_scroll_outer.pack(fill="both", expand=True)

canvas_p = tk.Canvas(f_pool_scroll_outer, bg=BG_DARK, highlightthickness=0)
scrollbar_p = ttk.Scrollbar(f_pool_scroll_outer, orient="vertical", command=canvas_p.yview)
pool_list_frame = tk.Frame(canvas_p, bg=BG_DARK)

pool_list_frame.bind("<Configure>", lambda e: canvas_p.configure(scrollregion=canvas_p.bbox("all")))
canvas_window_p = canvas_p.create_window((0, 0), window=pool_list_frame, anchor="nw")
canvas_p.bind("<Configure>", lambda e: canvas_p.itemconfig(canvas_window_p, width=e.width))
canvas_p.configure(yscrollcommand=scrollbar_p.set)

canvas_p.pack(side="left", fill="both", expand=True)
scrollbar_p.pack(side="right", fill="y")
pool_list_frame._pool_target = True

if HAS_DND:
    pool_list_frame.drop_target_register(DND_FILES)
    pool_list_frame.dnd_bind("<<Drop>>", on_desktop_drop)

refs["combo_hora"] = combo_hora
refs["combo_min"] = combo_min
refs["chk_sin_hora"] = chk_sin_hora
refs["controls_widgets"] = [btn_add]
refs["horarios_container"] = horarios_container
refresh_horarios_ui()
refresh_pool_ui()

# --- PESTAÑA 2: FLUJO ---
tab_flujo = tk.Frame(notebook, bg=BG_DARK)
notebook.add(tab_flujo, text="Flujo")
inner_f = tk.Frame(tab_flujo, bg=BG_DARK)
inner_f.pack(fill="both", expand=True, padx=4, pady=4)

f_preview_card = tk.Frame(inner_f, bg=BG_CURRENT, padx=4, pady=4)
f_preview_card.pack(fill="both", expand=True)

preview_text = tk.Text(f_preview_card, bg=BG_DARK, fg=FG_LIGHT, wrap="word",
                        font=("Consolas", 7), relief="flat", state="disabled")
preview_text.pack(fill="both", expand=True)

notebook.bind("<<NotebookTabChanged>>", refresh_preview)
refresh_preview()

root.mainloop()