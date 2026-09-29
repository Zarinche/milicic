import os
import json
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

CONFIG_FILE = os.path.join(os.path.expandvars(r"%TEMP%"), "automatizador_state.json")


class ValidationError(Exception):
    pass


# =====================================================================
# ESTADO GLOBAL Y CONTROL DE SUBVENTANAS ÚNICAS
# =====================================================================
apps_pool = []          
_next_app_id = [1]

dias_vals = {d: True for d in range(1, 8)}
meses_vals = {m: True for m in range(1, 13)}
dias_mes_vals = {d: True for d in range(1, 32)}

s_h_active = False  # Estado temporal para el próximo horario a agregar

horarios = [{
    "hora": "08", "min": "30", "sin_hora": False, "apps": [],
    "dias_vals": dict(dias_vals), "meses_vals": dict(meses_vals),
    "dias_mes_vals": dict(dias_mes_vals),
}]

refs = {
    "combo_hora": None, "combo_min": None, "chk_sin_hora": None,
    "horarios_container": None, "resumen_text": None, "flujo_text": None,
    "lbl_resumen_dias": None, "lbl_resumen_meses": None, "lbl_resumen_diasmes": None,
}

drag_state = {"active": False, "source": None, "app": None, "float_win": None}
pool_row_refs = []

# Control global estricto: máximo 1 subventana activa a la vez en toda la app
_subventana_activa = [None]

def _asegurar_ventana_unica():
    if _subventana_activa[0] is not None:
        try:
            if _subventana_activa[0].winfo_exists():
                _subventana_activa[0].lift()
                _subventana_activa[0].focus_set()
                return True
            else:
                _subventana_activa[0] = None
        except Exception:
            _subventana_activa[0] = None
    return False


# =====================================================================
# PERSISTENCIA Y CARGA DE ESTADO (%TEMP%)
# =====================================================================
def guardar_estado():
    estado = {
        "apps_pool": apps_pool,
        "next_app_id": _next_app_id[0],
        "dias_vals": {str(k): v for k, v in dias_vals.items()},
        "meses_vals": {str(k): v for k, v in meses_vals.items()},
        "dias_mes_vals": {str(k): v for k, v in dias_mes_vals.items()},
        "horarios": horarios
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error al guardar estado: {e}")


def cargar_estado():
    global apps_pool, horarios, _next_app_id
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            estado = json.load(f)
        
        _next_app_id[0] = estado.get("next_app_id", 1)

        loaded_dias = estado.get("dias_vals", {})
        for k, v in loaded_dias.items():
            if int(k) in dias_vals:
                dias_vals[int(k)] = v

        loaded_meses = estado.get("meses_vals", {})
        for k, v in loaded_meses.items():
            if int(k) in meses_vals:
                meses_vals[int(k)] = v

        loaded_dmes = estado.get("dias_mes_vals", {})
        for k, v in loaded_dmes.items():
            if int(k) in dias_mes_vals:
                dias_mes_vals[int(k)] = v

        raw_pool = estado.get("apps_pool", [])
        valid_pool = []
        valid_ids = set()
        for app in raw_pool:
            es_link = app.get("es_link", False)
            ruta = app.get("ruta", "")
            if es_link or os.path.exists(ruta):
                valid_pool.append(app)
                valid_ids.add(app["id"])
        
        apps_pool = valid_pool

        raw_horarios = estado.get("horarios", [])
        valid_horarios = []
        for h in raw_horarios:
            h_dias = {int(k): v for k, v in h.get("dias_vals", {}).items()}
            h_meses = {int(k): v for k, v in h.get("meses_vals", {}).items()}
            h_dmes = {int(k): v for k, v in h.get("dias_mes_vals", {}).items()}
            
            h_apps = [app for app in h.get("apps", []) if app.get("id") in valid_ids]
            
            h["dias_vals"] = h_dias
            h["meses_vals"] = h_meses
            h["dias_mes_vals"] = h_dmes
            h["apps"] = h_apps
            valid_horarios.append(h)

        if valid_horarios:
            horarios = valid_horarios

    except Exception as e:
        print(f"Error al cargar estado: {e}")


# =====================================================================
# HELPERS DE TOGGLE GENERALES
# =====================================================================
def make_toggle(vals, btns, key, color):
    def _t():
        vals[key] = not vals[key]
        btns[key].config(
            bg=color if vals[key] else BG_CURRENT,
            fg=BG_DARK if vals[key] else FG_LIGHT,
        )
        refresh_previews()
    return _t


# =====================================================================
# DIÁLOGOS DE FILTROS GLOBALES
# =====================================================================
def abrir_selector_dias():
    if _asegurar_ventana_unica():
        return
    top = tk.Toplevel(root)
    _subventana_activa[0] = top
    top.title("Filtrar Días de la Semana")
    top.config(bg=BG_CURRENT, padx=10, pady=10)
    top.resizable(False, False)
    top.attributes("-topmost", True)

    tk.Label(top, text="Seleccioná los días activos por defecto:", bg=BG_CURRENT, fg=PURPLE,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))

    f_btns = tk.Frame(top, bg=BG_CURRENT)
    f_btns.pack(anchor="w", pady=(0, 8))

    sub_dias_btns = {}
    for val, nom in NOMBRES_DIA.items():
        btn = tk.Button(
            f_btns, text=nom, width=3,
            bg=PURPLE if dias_vals[val] else BG_DARK,
            fg=BG_DARK if dias_vals[val] else FG_LIGHT,
            font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(dias_vals, sub_dias_btns, val, PURPLE),
        )
        btn.pack(side="left", padx=2, ipady=2)
        sub_dias_btns[val] = btn

    def cerrar():
        actualizar_etiquetas_filtros()
        refresh_previews()
        if _subventana_activa[0] == top:
            _subventana_activa[0] = None
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", cerrar)

    tk.Button(top, text="Aceptar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=cerrar).pack(fill="x", ipady=3)


def abrir_selector_meses():
    if _asegurar_ventana_unica():
        return
    top = tk.Toplevel(root)
    _subventana_activa[0] = top
    top.title("Filtrar Meses")
    top.config(bg=BG_CURRENT, padx=10, pady=10)
    top.resizable(False, False)
    top.attributes("-topmost", True)

    tk.Label(top, text="Seleccioná los meses activos por defecto:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))

    f_grid = tk.Frame(top, bg=BG_CURRENT)
    f_grid.pack(anchor="w", pady=(0, 8))

    sub_meses_btns = {}
    for idx, (val, nom) in enumerate(NOMBRES_MES.items()):
        btn = tk.Button(
            f_grid, text=nom, width=3,
            bg=CYAN if meses_vals[val] else BG_DARK,
            fg=BG_DARK if meses_vals[val] else FG_LIGHT,
            font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(meses_vals, sub_meses_btns, val, CYAN),
        )
        row_idx = idx // 6
        col_idx = idx % 6
        btn.grid(row=row_idx, column=col_idx, padx=2, pady=2, ipady=1)
        sub_meses_btns[val] = btn

    def cerrar():
        actualizar_etiquetas_filtros()
        refresh_previews()
        if _subventana_activa[0] == top:
            _subventana_activa[0] = None
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", cerrar)

    tk.Button(top, text="Aceptar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=cerrar).pack(fill="x", ipady=3)


def abrir_selector_dias_mes():
    if _asegurar_ventana_unica():
        return
    top = tk.Toplevel(root)
    _subventana_activa[0] = top
    top.title("Filtrar Días del Mes")
    top.config(bg=BG_CURRENT, padx=10, pady=10)
    top.resizable(False, False)
    top.attributes("-topmost", True)

    tk.Label(top, text="Seleccioná los días del mes (1 al 31):", bg=BG_CURRENT, fg=PINK,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))

    f_grid = tk.Frame(top, bg=BG_CURRENT)
    f_grid.pack(anchor="w", pady=(0, 8))

    sub_diasmes_btns = {}
    for val in range(1, 32):
        btn = tk.Button(
            f_grid, text=str(val), width=2,
            bg=PINK if dias_mes_vals[val] else BG_DARK,
            fg=BG_DARK if dias_mes_vals[val] else FG_LIGHT,
            font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(dias_mes_vals, sub_diasmes_btns, val, PINK),
        )
        row_idx = (val - 1) // 10
        col_idx = (val - 1) % 10
        btn.grid(row=row_idx, column=col_idx, padx=1, pady=1, ipady=1)
        sub_diasmes_btns[val] = btn

    def cerrar():
        actualizar_etiquetas_filtros()
        refresh_previews()
        if _subventana_activa[0] == top:
            _subventana_activa[0] = None
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", cerrar)

    tk.Button(top, text="Aceptar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=cerrar).pack(fill="x", ipady=3)


def actualizar_etiquetas_filtros():
    if refs["lbl_resumen_dias"]:
        activos = [k for k, v in dias_vals.items() if v]
        txt = "Todos" if len(activos) == 7 else (",".join(NOMBRES_DIA[k] for k in activos) if activos else "Ninguno")
        refs["lbl_resumen_dias"].config(text=f"Días: {txt}")
    if refs["lbl_resumen_meses"]:
        activos = [k for k, v in meses_vals.items() if v]
        txt = "Todos" if len(activos) == 12 else (",".join(NOMBRES_MES[k] for k in activos) if activos else "Ninguno")
        refs["lbl_resumen_meses"].config(text=f"Meses: {txt}")
    if refs["lbl_resumen_diasmes"]:
        activos = [k for k, v in dias_mes_vals.items() if v]
        txt = "Todos" if len(activos) == 31 else f"{len(activos)} días sel."
        refs["lbl_resumen_diasmes"].config(text=f"Día mes: {txt}")


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
    simbolo = "🔗 " if app_copy.get("es_link") else "📦 "
    txt_label = simbolo + app_copy["nombre"] + (" ↵" if app_copy.get("enter_auto") else "")
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
        nuevo = dict(app)
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
# POOL DE APPS / ENLACES GUARDADOS
# =====================================================================
def abrir_dialogo_nueva_app():
    if _asegurar_ventana_unica():
        return
    top = tk.Toplevel(root)
    _subventana_activa[0] = top
    top.title("Nueva App o Enlace")
    top.config(bg=BG_CURRENT, padx=10, pady=10)
    top.resizable(False, False)
    top.attributes("-topmost", True)

    def cerrar_y_destruir():
        if _subventana_activa[0] == top:
            _subventana_activa[0] = None
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", cerrar_y_destruir)

    tk.Label(top, text="Nombre:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w")
    entry_nombre = tk.Entry(top, bg=BG_DARK, fg=FG_LIGHT,
                            insertbackground=FG_LIGHT, relief="flat",
                            font=("Segoe UI", 9), width=35)
    entry_nombre.pack(fill="x", ipady=2, pady=(0, 6))

    # --- SELECTOR EXCLUSIVO: ARCHIVO O LINK ---
    tk.Label(top, text="Tipo de elemento:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
    
    tipo_var = tk.StringVar(value="archivo")
    f_tipo = tk.Frame(top, bg=BG_CURRENT)
    f_tipo.pack(anchor="w", pady=(0, 6))

    lbl_ubicacion = tk.Label(top, text="Ubicación del Archivo:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold"))
    lbl_ubicacion.pack(anchor="w")

    f_ruta = tk.Frame(top, bg=BG_CURRENT)
    f_ruta.pack(fill="x", pady=(0, 6))
    entry_ruta = tk.Entry(f_ruta, bg=BG_DARK, fg=FG_LIGHT,
                           insertbackground=FG_LIGHT, relief="flat",
                           font=("Segoe UI", 9))
    entry_ruta.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))

    def actualizar_modo_tipo():
        if tipo_var.get() == "archivo":
            btn_examinar.config(state="normal", bg=PURPLE)
            lbl_ubicacion.config(text="Ubicación del Archivo:")
        else:
            btn_examinar.config(state="disabled", bg=BG_DARK)
            lbl_ubicacion.config(text="Enlace Web (URL):")

    rb_archivo = tk.Radiobutton(f_tipo, text="Archivo", variable=tipo_var, value="archivo",
                                bg=BG_CURRENT, fg=FG_LIGHT, selectcolor=BG_DARK,
                                activebackground=BG_CURRENT, activeforeground=FG_LIGHT,
                                font=("Segoe UI", 8, "bold"), command=actualizar_modo_tipo)
    rb_archivo.pack(side="left", padx=(0, 12))

    rb_link = tk.Radiobutton(f_tipo, text="Enlace Web", variable=tipo_var, value="link",
                             bg=BG_CURRENT, fg=FG_LIGHT, selectcolor=BG_DARK,
                             activebackground=BG_CURRENT, activeforeground=FG_LIGHT,
                             font=("Segoe UI", 8, "bold"), command=actualizar_modo_tipo)
    rb_link.pack(side="left")

    def examinar():
        if tipo_var.get() == "link":
            return
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo o ejecutable",
            filetypes=[("Todos los archivos", "*.*"), ("Ejecutables", "*.exe")],
            parent=top
        )
        if archivo:
            entry_ruta.delete(0, tk.END)
            entry_ruta.insert(0, archivo)
            if not entry_nombre.get().strip():
                entry_nombre.insert(0, os.path.splitext(os.path.basename(archivo))[0])

    btn_examinar = tk.Button(f_ruta, text="Examinar", bg=PURPLE, fg=BG_DARK,
              font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
              command=examinar)
    btn_examinar.pack(side="right")

    tk.Label(top, text="Detalles / Descripción:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w")
    entry_detalles = tk.Entry(top, bg=BG_DARK, fg=FG_LIGHT,
                              insertbackground=FG_LIGHT, relief="flat",
                              font=("Segoe UI", 9), width=35)
    entry_detalles.pack(fill="x", ipady=2, pady=(0, 6))

    f_enter_box = tk.Frame(top, bg=BG_CURRENT)
    f_enter_box.pack(fill="x", pady=(0, 6))

    enter_var = tk.BooleanVar(value=False)
    
    f_win_name = tk.Frame(top, bg=BG_CURRENT)
    f_win_name.pack(fill="x", pady=(0, 8))
    
    tk.Label(f_win_name, text="Nombre exacto de ventana:", bg=BG_CURRENT, fg=FG_LIGHT,
             font=("Segoe UI", 8)).pack(anchor="w")
    entry_ventana = tk.Entry(f_win_name, bg=BG_DARK, fg=FG_LIGHT,
                             insertbackground=FG_LIGHT, relief="flat",
                             font=("Segoe UI", 8), state="disabled")
    entry_ventana.pack(fill="x", ipady=1, pady=(2, 0))

    def toggle_enter_state():
        if enter_var.get():
            entry_ventana.config(state="normal")
        else:
            entry_ventana.delete(0, tk.END)
            entry_ventana.config(state="disabled")

    chk_enter = tk.Checkbutton(
        f_enter_box, text="Habilitar Auto Enter ↵", variable=enter_var,
        bg=BG_CURRENT, fg=FG_LIGHT, selectcolor=BG_DARK,
        activebackground=BG_CURRENT, activeforeground=FG_LIGHT,
        font=("Segoe UI", 8, "bold"), command=toggle_enter_state
    )
    chk_enter.pack(anchor="w")

    f_btns = tk.Frame(top, bg=BG_CURRENT)
    f_btns.pack(fill="x")

    def agregar():
        ruta = entry_ruta.get().strip()
        if not ruta:
            messagebox.showerror("Atención", "Falta la ruta o enlace.", parent=top)
            return
        
        es_link = (tipo_var.get() == "link")
        if es_link:
            if not ruta.startswith("http://") and not ruta.startswith("https://"):
                ruta = "https://" + ruta

        nombre = entry_nombre.get().strip() or (os.path.basename(ruta.strip('"')) if not es_link else ruta)
        
        apps_pool.append({
            "id": _next_app_id[0],
            "nombre": nombre,
            "ruta": ruta.strip('"'),
            "detalles": entry_detalles.get().strip(),
            "enter_auto": enter_var.get(),
            "ventana_nombre": entry_ventana.get().strip(),
            "es_link": es_link
        })
        _next_app_id[0] += 1
        refresh_pool_ui()
        cerrar_y_destruir()

    tk.Button(f_btns, text="Guardar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
              command=agregar).pack(side="left", expand=True, fill="x", padx=(0, 4))
    tk.Button(f_btns, text="Cancelar", bg=BG_DARK, fg=FG_LIGHT,
              font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
              command=cerrar_y_destruir).pack(side="left", expand=True, fill="x", padx=(4, 0))


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
        ruta_limpia = ruta.strip('"')
        nombre = os.path.splitext(os.path.basename(ruta_limpia))[0]
        es_link = ruta_limpia.startswith("http://") or ruta_limpia.startswith("https://")
        apps_pool.append({
            "id": _next_app_id[0],
            "nombre": nombre,
            "ruta": ruta_limpia,
            "detalles": "Arrastrado desde escritorio",
            "enter_auto": False,
            "ventana_nombre": "",
            "es_link": es_link
        })
        _next_app_id[0] += 1
    refresh_pool_ui()


def refresh_pool_ui():
    for w in pool_list_frame.winfo_children():
        w.destroy()
    pool_row_refs.clear()

    if not apps_pool:
        tk.Label(pool_list_frame, text="Sin apps o enlaces guardados.",
                 bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 8, "italic")).pack(
            anchor="w", padx=6, pady=8)
        return

    for app in apps_pool:
        row = tk.Frame(pool_list_frame, bg=BG_CHIP)
        row.pack(fill="x", pady=2, padx=2)

        handle = tk.Label(row, text="≡", bg=BG_CHIP, fg=PINK,
                          font=("Segoe UI", 9, "bold"), cursor="fleur")
        handle.pack(side="left", padx=(4, 4))
        
        simbolo = "🔗 " if app.get("es_link") else "📦 "
        texto_app = simbolo + app["nombre"] + (" ↵" if app.get("enter_auto") else "")
        lbl = tk.Label(row, text=texto_app, bg=BG_CHIP, fg=FG_LIGHT,
                        font=("Segoe UI", 8), cursor="fleur", anchor="w")
        lbl.pack(side="left", fill="x", expand=True, padx=2, pady=3)
        
        btn_del = tk.Button(row, text="×", bg=BG_CHIP, fg=PINK, relief="flat",
                            font=("Segoe UI", 8, "bold"), cursor="hand2", bd=0,
                            command=lambda aid=app["id"]: eliminar_app_pool(aid))
        btn_del.pack(side="right", padx=4)

        for w in (row, handle, lbl):
            w.bind("<ButtonPress-1>", lambda e, a=app: start_drag(e, a, ("pool",)))

        pool_row_refs.append(row)


# =====================================================================
# CONFIGURACIÓN INDIVIDUAL DE HORARIOS
# =====================================================================
def abrir_config_horario(h_idx):
    if _asegurar_ventana_unica():
        return
    h = horarios[h_idx]
    top = tk.Toplevel(root)
    _subventana_activa[0] = top
    top.title(f"Configurar Horario #{h_idx + 1}")
    top.config(bg=BG_CURRENT, padx=12, pady=12)
    top.resizable(False, False)
    top.attributes("-topmost", True)

    def cerrar_y_destruir():
        if _subventana_activa[0] == top:
            _subventana_activa[0] = None
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", cerrar_y_destruir)

    tk.Label(top, text="Modo de Ejecución:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
    
    f_time = tk.Frame(top, bg=BG_CURRENT)
    f_time.pack(anchor="w", pady=(0, 10))
    
    c_hora = ttk.Combobox(f_time, values=[f"{i:02d}" for i in range(24)],
                          width=3, state="readonly", font=("Segoe UI", 9))
    c_hora.set(h["hora"])
    c_hora.pack(side="left", padx=(0, 2))
    tk.Label(f_time, text=":", bg=BG_CURRENT, fg=FG_LIGHT).pack(side="left")
    c_min = ttk.Combobox(f_time, values=[f"{i:02d}" for i in range(60)],
                         width=3, state="readonly", font=("Segoe UI", 9))
    c_min.set(h["min"])
    c_min.pack(side="left", padx=(2, 6))

    sh_var = tk.BooleanVar(value=h.get("sin_hora", False))
    
    def toggle_sh_config():
        if sh_var.get():
            c_hora.config(state="disabled")
            c_min.config(state="disabled")
        else:
            c_hora.config(state="readonly")
            c_min.config(state="readonly")

    chk_sh_sub = tk.Checkbutton(
        f_time, text="Sin Hora (S/H)", variable=sh_var,
        bg=BG_CURRENT, fg=CYAN, selectcolor=BG_DARK,
        activebackground=BG_CURRENT, activeforeground=CYAN,
        font=("Segoe UI", 8, "bold"), command=toggle_sh_config
    )
    chk_sh_sub.pack(side="left", padx=(4, 0))
    toggle_sh_config()

    tk.Label(top, text="▼ Días de la semana:", bg=BG_CURRENT, fg=PURPLE,
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 2))
    f_dias = tk.Frame(top, bg=BG_CURRENT)
    f_dias.pack(anchor="w", pady=(0, 6))
    
    sub_dias_btns = {}
    for val, nom in NOMBRES_DIA.items():
        btn = tk.Button(
            f_dias, text=nom, width=3,
            bg=PURPLE if h["dias_vals"][val] else BG_DARK,
            fg=BG_DARK if h["dias_vals"][val] else FG_LIGHT,
            font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(h["dias_vals"], sub_dias_btns, val, PURPLE),
        )
        btn.pack(side="left", padx=1, ipady=1)
        sub_dias_btns[val] = btn

    tk.Label(top, text="▼ Meses del año:", bg=BG_CURRENT, fg=CYAN,
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 2))
    f_meses = tk.Frame(top, bg=BG_CURRENT)
    f_meses.pack(anchor="w", pady=(0, 6))
    
    sub_meses_btns = {}
    for idx, (val, nom) in enumerate(NOMBRES_MES.items()):
        btn = tk.Button(
            f_meses, text=nom, width=3,
            bg=CYAN if h["meses_vals"][val] else BG_DARK,
            fg=BG_DARK if h["meses_vals"][val] else FG_LIGHT,
            font=("Segoe UI", 6, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(h["meses_vals"], sub_meses_btns, val, CYAN),
        )
        r_idx = idx // 6
        c_idx = idx % 6
        btn.grid(row=r_idx, column=c_idx, padx=1, pady=1, ipady=1)
        sub_meses_btns[val] = btn

    tk.Label(top, text="▼ Días del mes (1 al 31):", bg=BG_CURRENT, fg=PINK,
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 2))
    f_dmes = tk.Frame(top, bg=BG_CURRENT)
    f_dmes.pack(anchor="w", pady=(0, 10))
    
    sub_dmes_btns = {}
    for val in range(1, 32):
        btn = tk.Button(
            f_dmes, text=str(val), width=2,
            bg=PINK if h["dias_mes_vals"][val] else BG_DARK,
            fg=BG_DARK if h["dias_mes_vals"][val] else FG_LIGHT,
            font=("Segoe UI", 6, "bold"), relief="flat", cursor="hand2",
            command=make_toggle(h["dias_mes_vals"], sub_dmes_btns, val, PINK),
        )
        r_idx = (val - 1) // 10
        c_idx = (val - 1) % 10
        btn.grid(row=r_idx, column=c_idx, padx=1, pady=1, ipady=1)
        sub_dmes_btns[val] = btn

    def guardar_cambios():
        h["sin_hora"] = sh_var.get()
        if not h["sin_hora"]:
            h["hora"] = c_hora.get()
            h["min"] = c_min.get()
        refresh_horarios_ui()
        cerrar_y_destruir()

    tk.Button(top, text="Aceptar", bg=GREEN, fg=BG_DARK,
              font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
              command=guardar_cambios).pack(fill="x", ipady=4)


# =====================================================================
# HORARIOS + APPS
# =====================================================================
def _resumen_calendario(h):
    prefix = "S/H (Sin hora)" if h.get("sin_hora") else f"{h['hora']}:{h['min']}"
    
    activos_d = [k for k, v in h["dias_vals"].items() if v]
    d_txt = "Todos" if len(activos_d) == 7 else (",".join(NOMBRES_DIA[k] for k in activos_d) if activos_d else "Ninguno")
    
    activos_m = [k for k, v in h["meses_vals"].items() if v]
    m_txt = "Todos" if len(activos_m) == 12 else f"{len(activos_m)} meses"
    
    return f"⏰ {prefix} | Días: {d_txt} | {m_txt}"


def toggle_sin_hora():
    global s_h_active
    s_h_active = not s_h_active
    tk_estado = "disabled" if s_h_active else "readonly"
    refs["combo_hora"].config(state=tk_estado)
    refs["combo_min"].config(state=tk_estado)
    refs["chk_sin_hora"].config(
        bg=CYAN if s_h_active else BG_CURRENT,
        fg=BG_DARK if s_h_active else CYAN,
    )


def agregar_horario():
    global s_h_active
    h = refs["combo_hora"].get()
    m = refs["combo_min"].get()
    is_sh = s_h_active

    if s_h_active:
        s_h_active = False
        refs["chk_sin_hora"].config(bg=BG_CURRENT, fg=CYAN)
        refs["combo_hora"].config(state="readonly")
        refs["combo_min"].config(state="readonly")

    horarios.append({
        "hora": h, "min": m, "sin_hora": is_sh, "apps": [],
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
        tk.Label(container, text="Sin horarios definidos.", bg=BG_DARK,
                 fg=FG_LIGHT, font=("Segoe UI", 8, "italic")).pack(anchor="w", padx=6, pady=8)
        refresh_previews()
        return

    for h_idx, h in enumerate(horarios):
        row = tk.Frame(container, bg=BG_DARK)
        row.pack(fill="x", pady=(0, 6))

        top_row = tk.Frame(row, bg=BG_DARK)
        top_row.pack(fill="x")
        
        titulo_reloj = "⏰ S/H" if h.get("sin_hora") else f"⏰ {h['hora']}:{h['min']}"
        tk.Label(top_row, text=titulo_reloj, bg=BG_DARK, fg=CYAN,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 2))
        
        tk.Button(top_row, text="⚙", bg=BG_DARK, fg=PURPLE, relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2", bd=0,
                  command=lambda hi=h_idx: abrir_config_horario(hi)).pack(side="left", padx=2)

        tk.Button(top_row, text="×", bg=BG_CURRENT, fg=FG_LIGHT,
                  font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  command=lambda hi=h_idx: quitar_horario(hi)).pack(side="right", padx=4)

        tk.Label(row, text=_resumen_calendario(h), bg=BG_DARK, fg=FG_LIGHT,
                 font=("Segoe UI", 7, "italic"), justify="left"
                 ).pack(anchor="w", padx=(6, 0))

        drop_zone = tk.Frame(row, bg=BG_CURRENT, padx=4, pady=4)
        drop_zone.pack(fill="x", pady=(2, 0))
        drop_zone._drop_target = h_idx

        if not h["apps"]:
            ph = tk.Label(drop_zone, text="Arrastrá apps acá",
                          bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 7, "italic"))
            ph.pack(anchor="w")
            ph._drop_target = h_idx
        else:
            for a_idx, app in enumerate(h["apps"]):
                chip = tk.Frame(drop_zone, bg=BG_CHIP)
                chip.pack(fill="x", pady=2)
                chip._drop_target = h_idx

                simbolo = "🔗 " if app.get("es_link") else "📦 "
                texto_chip = simbolo + app["nombre"] + (" ↵" if app.get("enter_auto") else "")
                lbl = tk.Label(chip, text=texto_chip, bg=BG_CHIP,
                               fg=FG_LIGHT, font=("Segoe UI", 8), cursor="fleur")
                lbl.pack(side="left", padx=4, pady=3)
                lbl._drop_target = h_idx
                lbl.bind("<ButtonPress-1>",
                         lambda e, a=app, hi=h_idx, ai=a_idx:
                         start_drag(e, a, ("horario", hi, ai)))

                tk.Button(chip, text="×", bg=BG_CHIP, fg=PINK, relief="flat", bd=0,
                          font=("Segoe UI", 8, "bold"), cursor="hand2",
                          command=lambda hi=h_idx, ai=a_idx: quitar_app_chip(hi, ai)
                          ).pack(side="right", padx=4)

    refresh_previews()


# =====================================================================
# VISTAS: RESUMEN Y FLUJO
# =====================================================================
def refresh_previews(*_):
    if refs["resumen_text"]:
        refs["resumen_text"].config(state="normal")
        refs["resumen_text"].delete("1.0", tk.END)
        total_apps = sum(len(h["apps"]) for h in horarios)
        refs["resumen_text"].insert(tk.END, f"📊 RESUMEN GENERAL\n")
        refs["resumen_text"].insert(tk.END, f"• Horarios/Bloques: {len(horarios)}\n")
        refs["resumen_text"].insert(tk.END, f"• Apps enlazadas: {total_apps}\n")
        refs["resumen_text"].config(state="disabled")

    if refs["flujo_text"]:
        refs["flujo_text"].config(state="normal")
        refs["flujo_text"].delete("1.0", tk.END)
        
        step = 1
        for h in horarios:
            modo = "S/H (Al iniciar PC)" if h.get("sin_hora") else f"Hora {h['hora']}:{h['min']}"
            refs["flujo_text"].insert(tk.END, f"Paso {step}: [{modo}]\n")
            step += 1
            for app in h["apps"]:
                tipo = "Enlace" if app.get("es_link") else "App"
                extra = f" [Enter '{app.get('ventana_nombre')}']" if app.get("enter_auto") else ""
                refs["flujo_text"].insert(tk.END, f"   -> {tipo}: '{app['nombre']}'{extra}\n")
            refs["flujo_text"].insert(tk.END, "\n")
                
        refs["flujo_text"].config(state="disabled")


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
        win_name = app.get("ventana_nombre", "").strip()
        if win_name:
            lineas.append(f'WshShell.AppActivate "{win_name}"')
            lineas.append('WScript.Sleep 400')
        lineas.append('WshShell.SendKeys "{ENTER}"')
    return "\n".join(lineas)


def _calcular_espera_por_horario(horarios_con_apps):
    grupos = {}
    for h in horarios_con_apps:
        clave = "sh" if h.get("sin_hora") else (h["hora"], h["min"])
        grupos.setdefault(clave, []).append(h)
    espera = {}
    for clave, lista in grupos.items():
        for i, h in enumerate(lista):
            espera[id(h)] = i < len(lista) - 1
    return espera


def build_vbs():
    horarios_con_apps = [h for h in horarios if h["apps"]]
    if not horarios_con_apps:
        raise ValidationError("Agregá al menos un horario/bloque y una app/enlace.")

    cabecera = [
        "On Error Resume Next",
        'Set WshShell = WScript.CreateObject("WScript.Shell")',
        "Dim t, runKey, intentos",
        'executedTimes = ","',
    ]

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

        espera = espera_por_horario.get(id(h), False)
        cuerpo = "\n".join(run_app_vbs(app, espera=espera) for app in h["apps"])
        cuerpo_indent = textwrap.indent(cuerpo, " " * 8)

        if h.get("sin_hora"):
            runkey = f"sh_{h_idx}"
            if_bloque = textwrap.dedent(f"""\
                If okDay{h_idx} And okMonth{h_idx} And okMonthDay{h_idx} Then
                    runKey = CStr(currDate) & "_{runkey}"
                    If InStr(executedTimes, "," & runKey & ",") = 0 Then
                {cuerpo_indent}
                        executedTimes = executedTimes & runKey & ","
                    End If
                End If""")
        else:
            hhmm = f"{h['hora']}:{h['min']}:00"
            runkey = f"h{h_idx}_{h['hora']}{h['min']}"
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
        with open(archivo_guardado, "w", encoding="cp1252") as f:
            f.write(vbs_content)
        messagebox.showinfo("Éxito", "¡Guardado correctamente en Inicio!")


# =====================================================================
# VENTANA PRINCIPAL (DISTRIBUCIÓN 3 COLUMNAS)
# =====================================================================
root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
root.title("Automatizador")
root.geometry("820x520")
root.resizable(False, False)
root.config(bg=BG_DARK)

cargar_estado()

root.bind_all("<B1-Motion>", on_drag_motion)
root.bind_all("<ButtonRelease-1>", on_drag_release)

main_layout = tk.Frame(root, bg=BG_DARK)
main_layout.pack(fill="both", expand=True, padx=6, pady=6)

main_layout.columnconfigure(0, weight=3)
main_layout.columnconfigure(1, weight=3)
main_layout.columnconfigure(2, weight=2)
main_layout.rowconfigure(0, weight=1)

# =====================================================================
# COLUMNA 0: FILTROS GLOBALES + HORARIOS
# =====================================================================
col0 = tk.Frame(main_layout, bg=BG_DARK)
col0.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
col0.rowconfigure(1, weight=1)
col0.columnconfigure(0, weight=1)

f_filtros_card = tk.Frame(col0, bg=BG_CURRENT, padx=4, pady=4)
f_filtros_card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

tk.Button(f_filtros_card, text="DÍA ▾", bg=PURPLE, fg=BG_DARK,
          font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
          command=abrir_selector_dias).pack(fill="x", pady=1, ipady=1)
lbl_resumen_dias = tk.Label(f_filtros_card, text="Días: Todos", bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 6))
lbl_resumen_dias.pack(anchor="w")

tk.Button(f_filtros_card, text="MES ▾", bg=CYAN, fg=BG_DARK,
          font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
          command=abrir_selector_meses).pack(fill="x", pady=(3, 1), ipady=1)
lbl_resumen_meses = tk.Label(f_filtros_card, text="Meses: Todos", bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 6))
lbl_resumen_meses.pack(anchor="w")

tk.Button(f_filtros_card, text="DÍA DEL MES ▾", bg=PINK, fg=BG_DARK,
          font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
          command=abrir_selector_dias_mes).pack(fill="x", pady=(3, 1), ipady=1)
lbl_resumen_diasmes = tk.Label(f_filtros_card, text="Día mes: Todos", bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 6))
lbl_resumen_diasmes.pack(anchor="w")

refs["lbl_resumen_dias"] = lbl_resumen_dias
refs["lbl_resumen_meses"] = lbl_resumen_meses
refs["lbl_resumen_diasmes"] = lbl_resumen_diasmes

f_horarios_card = tk.Frame(col0, bg=BG_CURRENT, padx=4, pady=4)
f_horarios_card.grid(row=1, column=0, sticky="nsew")
f_horarios_card.rowconfigure(2, weight=1)
f_horarios_card.columnconfigure(0, weight=1)

tk.Label(f_horarios_card, text="HORARIOS / BLOQUES", bg=BG_CURRENT, fg=CYAN,
         font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))

controls_h = tk.Frame(f_horarios_card, bg=BG_CURRENT)
controls_h.grid(row=1, column=0, sticky="ew", pady=(0, 2))

combo_hora = ttk.Combobox(controls_h, values=[f"{i:02d}" for i in range(24)],
                            width=2, state="readonly", font=("Segoe UI", 7))
combo_hora.set("08")
combo_hora.pack(side="left", padx=(0, 1))
tk.Label(controls_h, text=":", bg=BG_CURRENT, fg=FG_LIGHT, font=("Segoe UI", 7)).pack(side="left")
combo_min = ttk.Combobox(controls_h, values=[f"{i:02d}" for i in range(60)],
                          width=2, state="readonly", font=("Segoe UI", 7))
combo_min.set("00")
combo_min.pack(side="left", padx=(1, 2))
btn_add = tk.Button(controls_h, text="+", bg=PURPLE, fg=BG_DARK,
                    font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
                    command=agregar_horario)
btn_add.pack(side="left", padx=1)
chk_sin_hora = tk.Button(controls_h, text="S/H", bg=BG_CURRENT, fg=CYAN,
                         font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
                         command=toggle_sin_hora)
chk_sin_hora.pack(side="right", padx=(2, 0))

f_h_scroll = tk.Frame(f_horarios_card, bg=BG_DARK)
f_h_scroll.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
f_h_scroll.rowconfigure(0, weight=1)
f_h_scroll.columnconfigure(0, weight=1)

canvas_h = tk.Canvas(f_h_scroll, bg=BG_DARK, highlightthickness=0)
scrollbar_h = ttk.Scrollbar(f_h_scroll, orient="vertical", command=canvas_h.yview)
horarios_container = tk.Frame(canvas_h, bg=BG_DARK, padx=2, pady=2)

horarios_container.bind("<Configure>", lambda e: canvas_h.configure(scrollregion=canvas_h.bbox("all")))
canvas_window_h = canvas_h.create_window((0, 0), window=horarios_container, anchor="nw")
canvas_h.bind("<Configure>", lambda e: canvas_h.itemconfig(canvas_window_h, width=e.width))
canvas_h.configure(yscrollcommand=scrollbar_h.set)

canvas_h.grid(row=0, column=0, sticky="nsew")
scrollbar_h.grid(row=0, column=1, sticky="ns")

refs["combo_hora"] = combo_hora
refs["combo_min"] = combo_min
refs["chk_sin_hora"] = chk_sin_hora
refs["horarios_container"] = horarios_container


# =====================================================================
# COLUMNA 1: FLUJO + APPS GUARDADAS
# =====================================================================
col1 = tk.Frame(main_layout, bg=BG_DARK)
col1.grid(row=0, column=1, sticky="nsew", padx=(2, 2))
col1.rowconfigure(0, weight=1)
col1.rowconfigure(1, weight=1)
col1.columnconfigure(0, weight=1)

f_flujo_card = tk.Frame(col1, bg=BG_CURRENT, padx=4, pady=4)
f_flujo_card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
f_flujo_card.rowconfigure(1, weight=1)
f_flujo_card.columnconfigure(0, weight=1)

tk.Label(f_flujo_card, text="FLUJO PASO A PASO", bg=BG_CURRENT, fg=PURPLE,
         font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))

f_flujo_scroll = tk.Frame(f_flujo_card, bg=BG_DARK)
f_flujo_scroll.grid(row=1, column=0, sticky="nsew")
f_flujo_scroll.rowconfigure(0, weight=1)
f_flujo_scroll.columnconfigure(0, weight=1)

flujo_text = tk.Text(f_flujo_scroll, bg=BG_DARK, fg=FG_LIGHT, wrap="word",
                     font=("Consolas", 7), relief="flat", state="disabled", bd=0)
scrollbar_flujo = ttk.Scrollbar(f_flujo_scroll, orient="vertical", command=flujo_text.yview)
flujo_text.configure(yscrollcommand=scrollbar_flujo.set)

flujo_text.grid(row=0, column=0, sticky="nsew")
scrollbar_flujo.grid(row=0, column=1, sticky="ns")
refs["flujo_text"] = flujo_text

f_pool_card = tk.Frame(col1, bg=BG_CURRENT, padx=4, pady=4)
f_pool_card.grid(row=1, column=0, sticky="nsew")
f_pool_card.rowconfigure(1, weight=1)
f_pool_card.columnconfigure(0, weight=1)

f_pool_header = tk.Frame(f_pool_card, bg=BG_CURRENT)
f_pool_header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
tk.Label(f_pool_header, text="APPS GUARDADAS", bg=BG_CURRENT, fg=CYAN,
         font=("Segoe UI", 8, "bold")).pack(side="left")
tk.Button(f_pool_header, text="+ Agregar App", bg=PURPLE, fg=BG_DARK,
          font=("Segoe UI", 7, "bold"), relief="flat", cursor="hand2",
          command=abrir_dialogo_nueva_app).pack(side="right")

f_pool_scroll_outer = tk.Frame(f_pool_card, bg=BG_DARK)
f_pool_scroll_outer.grid(row=1, column=0, sticky="nsew")
f_pool_scroll_outer.rowconfigure(0, weight=1)
f_pool_scroll_outer.columnconfigure(0, weight=1)

canvas_p = tk.Canvas(f_pool_scroll_outer, bg=BG_DARK, highlightthickness=0)
scrollbar_p = ttk.Scrollbar(f_pool_scroll_outer, orient="vertical", command=canvas_p.yview)
pool_list_frame = tk.Frame(canvas_p, bg=BG_DARK)

pool_list_frame.bind("<Configure>", lambda e: canvas_p.configure(scrollregion=canvas_p.bbox("all")))
canvas_window_p = canvas_p.create_window((0, 0), window=pool_list_frame, anchor="nw")
canvas_p.bind("<Configure>", lambda e: canvas_p.itemconfig(canvas_window_p, width=e.width))
canvas_p.configure(yscrollcommand=scrollbar_p.set)

canvas_p.grid(row=0, column=0, sticky="nsew")
scrollbar_p.grid(row=0, column=1, sticky="ns")
pool_list_frame._pool_target = True

if HAS_DND:
    pool_list_frame.drop_target_register(DND_FILES)
    pool_list_frame.dnd_bind("<<Drop>>", on_desktop_drop)


# =====================================================================
# COLUMNA 2: RESUMEN + BOTÓN GUARDAR
# =====================================================================
col2 = tk.Frame(main_layout, bg=BG_DARK)
col2.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
col2.rowconfigure(0, weight=1)
col2.columnconfigure(0, weight=1)

f_resumen_card = tk.Frame(col2, bg=BG_CURRENT, padx=4, pady=4)
f_resumen_card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
f_resumen_card.rowconfigure(1, weight=1)
f_resumen_card.columnconfigure(0, weight=1)

tk.Label(f_resumen_card, text="RESUMEN", bg=BG_CURRENT, fg=CYAN,
         font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))

resumen_text = tk.Text(f_resumen_card, bg=BG_DARK, fg=CYAN, wrap="word",
                       font=("Consolas", 7), relief="flat", state="disabled")
resumen_text.grid(row=1, column=0, sticky="nsew")
refs["resumen_text"] = resumen_text

tk.Button(
    col2, text="Guardar en Inicio", bg=GREEN, fg=BG_DARK,
    font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
    command=generar_script,
).grid(row=1, column=0, sticky="ew", ipady=8)


# Inicializar interfaces con datos cargados
refresh_horarios_ui()
refresh_pool_ui()
actualizar_etiquetas_filtros()


# Manejar evento de cierre para guardar estado
def on_closing():
    guardar_estado()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()