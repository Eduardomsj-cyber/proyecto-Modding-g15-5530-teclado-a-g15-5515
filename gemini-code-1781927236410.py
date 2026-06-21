import asyncio
import os
import json
import tkinter as tk
from tkinter import filedialog
from nicegui import app, ui, run
from bleak import BleakClient, BleakScanner

# --- LIBRERIAS DE EXTRACCION DE ICONOS ---
try:
    from icoextract import IconExtractor
    from PIL import Image
except ImportError:
    print("ADVERTENCIA: Te falta instalar las librerias. Ejecuta: pip install icoextract Pillow")

# --- CONFIGURACION ---
ESP32_MAC = "A0:F2:62:EC:AF:49" 
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
ARCHIVO_JUEGOS = "juegos_alienfx.json"
CARPETA_ICONOS = os.path.abspath("iconos_cache")
ble_client = None

os.makedirs(CARPETA_ICONOS, exist_ok=True)

# Permite a NiceGUI leer archivos locales como el video y las imagenes
app.add_static_files('/assets', '.')

# --- SISTEMA DE GUARDADO DE JUEGOS ---
def cargar_juegos():
    if os.path.exists(ARCHIVO_JUEGOS):
        try:
            with open(ARCHIVO_JUEGOS, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_juegos():
    with open(ARCHIVO_JUEGOS, 'w') as f:
        json.dump(juegos_guardados, f)

juegos_guardados = cargar_juegos()

# --- LOGICA DE CONEXION BLE ---
async def conectar_placa():
    global ble_client
    ui.notify('[SISTEMA] INICIANDO ESCANEO DE FRECUENCIAS...', type='info', color='#00e5ff')
    estado_label.set_text('SYS: BUSCANDO...')
    estado_label.classes(replace='text-sm font-bold tracking-widest text-yellow-500')
    
    device = await BleakScanner.find_device_by_address(ESP32_MAC, timeout=5.0)
    if not device:
        ui.notify('[ERROR] ENLACE NO ENCONTRADO', type='negative')
        estado_label.set_text('SYS: OFFLINE')
        estado_label.classes(replace='text-sm font-bold tracking-widest text-red-500')
        return

    try:
        ble_client = BleakClient(device)
        await ble_client.connect()
        ui.notify('[OK] SISTEMA ALIENFX ENLAZADO', type='positive')
        estado_label.set_text('SYS: ONLINE')
        estado_label.classes(replace='text-sm font-bold tracking-widest text-[#00e5ff]')
    except Exception as e:
        ui.notify(f'[ERROR] FALLO DE PROTOCOLO', type='negative')

async def enviar_comando(comando):
    if ble_client and ble_client.is_connected:
        try:
            await ble_client.write_gatt_char(CHARACTERISTIC_UUID, comando.encode('utf-8'))
            ui.notify(f'>>> TRANSMITIDO: {comando}', type='info', color='#00e5ff')
        except Exception as e:
            ui.notify(f'[ERROR] FALLO DE TRANSMISION', type='negative')
    else:
        ui.notify('[ADVERTENCIA] HARDWARE NO DETECTADO', type='warning')

# --- LOGICA DE LANZAMIENTO DE JUEGOS ---
async def lanzar_juego(ruta_exe, comando_rgb):
    ui.notify(f'[ALIENFX] APLICANDO PERFIL: {comando_rgb}', type='info', color='#00e5ff')
    await enviar_comando(comando_rgb)
    await asyncio.sleep(0.5)
    
    try:
        ruta_limpia = os.path.normpath(ruta_exe.strip().strip('"').strip("'"))
        if os.path.exists(ruta_limpia):
            os.startfile(ruta_limpia)
            ui.notify(f'[SISTEMA] EJECUTANDO BINARIO...', type='positive')
        else:
            ui.notify(f'[ERROR] RUTA NO ENCONTRADA: {ruta_limpia}', type='negative')
    except Exception as e:
        ui.notify(f'[ERROR] FALLO AL EJECUTAR: {e}', type='negative')

# --- CONVERSION Y APLICACION DE COLOR ---
def hex_a_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6: return 0, 0, 0
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

async def aplicar_color_hex(hex_str):
    r, g, b = hex_a_rgb(hex_str)
    hex_label.set_text(f'HEX: {hex_str.upper()}')
    rgb_label.set_text(f'RGB: [{r}, {g}, {b}]')
    await enviar_comando(f"FIJO,{r},{g},{b}")

# --- EXPLORADOR DE ARCHIVOS Y EXTRACCION AUTOMATICA ---
def _dialogo_exe():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    ruta = filedialog.askopenfilename(title="Selecciona el .exe del juego", filetypes=[("Ejecutables", "*.exe")])
    root.destroy()
    return ruta

cache_temporal_icono = {"ruta_png": ""}

async def buscar_exe_y_extraer():
    ruta = await run.io_bound(_dialogo_exe)
    if ruta:
        ruta_input.set_value(ruta)
        nombre_base = os.path.basename(ruta).replace('.exe', '')
        nombre_limpio = ''.join([' ' + c if c.isupper() else c for c in nombre_base]).strip()
        titulo_input.set_value(nombre_limpio.upper())
        
        try:
            ruta_ico = os.path.join(CARPETA_ICONOS, f"{nombre_base}.ico")
            ruta_png = os.path.join(CARPETA_ICONOS, f"{nombre_base}.png")
            
            def extraer():
                extractor = IconExtractor(ruta)
                extractor.export_icon(ruta_ico)
                img = Image.open(ruta_ico)
                img.save(ruta_png, format='PNG')
                
            await run.io_bound(extraer)
            cache_temporal_icono["ruta_png"] = ruta_png
            ui.notify('[SISTEMA] ÍCONO EXTRAÍDO CORRECTAMENTE', type='positive')
        except Exception as e:
            cache_temporal_icono["ruta_png"] = ""
            ui.notify('[AVISO] Ejecutable sin ícono, se usarán iniciales', type='warning')

ui.timer(0.5, conectar_placa, once=True)

# --- MAXIMIZAR VENTANA AL INICIAR ---
async def maximizar_ventana():
    # Pequeño retraso para asegurar que la ventana nativa ya existe
    await asyncio.sleep(0.5)
    try:
        if app.native.main_window:
            app.native.main_window.maximize()
    except Exception as e:
        print(f"No se pudo maximizar la ventana: {e}")

app.on_startup(maximizar_ventana)

# --- ESTILOS GLOBALES ---
ui.query('body').classes('bg-black text-gray-300 font-sans select-none m-0 p-0 overflow-hidden')

# --- VIDEO DE FONDO Y HUD DE BORDES FINALES (Sin bug de cuadros negros) ---
ui.html('''
    <video autoplay loop muted playsinline class="fixed top-0 left-0 w-screen h-screen object-cover z-[-10] opacity-40 pointer-events-none">
        <source src="/assets/fondo.mp4" type="video/mp4">
    </video>
    

''')

# --- HEADER (BARRA SUPERIOR TRANSLUCIDA) ---
with ui.row().classes('w-full bg-[#0a0a0a]/70 backdrop-blur-md border-b border-[#00e5ff]/50 p-4 items-center justify-between shadow-[0_4px_30px_rgba(0,229,255,0.15)] z-20 absolute top-0 left-0 right-0 h-[80px]'):
    with ui.row().classes('items-center gap-4 pl-4'):
        ui.image('alien.png').classes('w-12 h-12 opacity-100 mix-blend-screen')
        with ui.column().classes('gap-0'):
            ui.label('ALIENFX').classes('text-2xl font-black tracking-[0.3em] text-white leading-none drop-shadow-[0_0_8px_rgba(0,229,255,0.8)]')
            ui.label('COMMAND CENTER CORE').classes('text-[10px] tracking-[0.4em] text-[#00e5ff] leading-none mt-1')
    
    with ui.row().classes('items-center gap-6 pr-4'):
        estado_label = ui.label('SYS: INICIANDO...').classes('text-sm font-bold tracking-widest text-gray-500')
        ui.button('REINICIAR ENLACE', on_click=conectar_placa).classes(
            'bg-transparent border border-[#00e5ff] text-[#00e5ff] hover:bg-[#00e5ff] hover:text-black '
            'font-bold tracking-[0.2em] px-4 py-2 rounded-none transition-all duration-300 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
        )

# --- AREA DE SCROLL CON TABS ---
with ui.scroll_area().classes('w-full h-[calc(100vh-80px)] mt-[80px] z-10'):

    with ui.tabs().classes('w-full bg-[#050505]/60 backdrop-blur-sm text-gray-400 font-bold tracking-[0.2em] border-b border-[#00e5ff]/20') as tabs:
        tab_teclado = ui.tab('ILUMINACION (TECLADO)')
        tab_biblio = ui.tab('BIBLIOTECA (JUEGOS)')

    with ui.tab_panels(tabs, value=tab_teclado).classes('w-full bg-transparent p-0'):
        
        # ==========================================
        # PESTAÑA 1: TECLADO RGB (Translúcida)
        # ==========================================
        with ui.tab_panel(tab_teclado).classes('w-full p-8 bg-transparent'):
            with ui.row().classes('w-full max-w-[1400px] mx-auto gap-8 items-stretch justify-center'):
                
                # Panel Izquierdo
                with ui.column().classes('flex-1 bg-[#0a0a0a]/75 backdrop-blur-md border border-[#00e5ff]/30 p-6 relative min-w-[400px] items-center shadow-[0_0_20px_rgba(0,0,0,0.8)] justify-start min-h-[550px]'):
                    
                    with ui.column().classes('w-full bg-[#000000]/50 border border-[#222] p-3 mb-6'):
                        ui.label('TELEMETRIA DE SEÑAL').classes('text-[10px] tracking-[0.3em] text-[#00e5ff] mb-2')
                        with ui.row().classes('w-full justify-between items-center border-b border-[#111] pb-1 mb-1'):
                            ui.label('MAC:').classes('text-xs text-gray-400 tracking-wider')
                            ui.label(ESP32_MAC).classes('text-xs text-[#00e5ff] tracking-widest font-mono')
                        with ui.row().classes('w-full justify-between items-center border-b border-[#111] pb-1 mb-1'):
                            ui.label('LAST:').classes('text-xs text-gray-400 tracking-wider')
                            hex_label = ui.label('HEX: #00E5FF').classes('text-xs text-white tracking-widest font-mono')
                        with ui.row().classes('w-full justify-between items-center'):
                            ui.label('PWM:').classes('text-xs text-gray-400 tracking-wider')
                            rgb_label = ui.label('RGB: [0, 229, 255]').classes('text-xs text-white tracking-widest font-mono')

                    with ui.column().classes('w-full items-center gap-2'):
                        ui.label('ESPECTRO DE ZONAS').classes('text-sm font-bold tracking-[0.3em] text-white mb-2 border-b border-[#00e5ff]/30 pb-2 w-full text-center drop-shadow-[0_0_5px_#00e5ff]')
                        ui.label('PALETA DE ACCESO DIRECTO').classes('text-[9px] tracking-[0.2em] text-[#00e5ff] font-bold uppercase mt-2')
                        
                        with ui.grid(columns=4).classes('gap-2 w-full mt-2'):
                            colores = [
                                ('#00e5ff', 'CYAN'), ('#ff003c', 'RED'), ('#00ff66', 'GREEN'), ('#7000ff', 'PURPLE'),
                                ('#ffaa00', 'ORANGE'), ('#ffffff', 'WHITE'), ('#ff00c8', 'PINK'), ('#003cff', 'BLUE')
                            ]
                            for h_val, name in colores:
                                ui.button(name, on_click=lambda h=h_val: aplicar_color_hex(h)).classes(
                                    'bg-[#000000]/60 border border-[#333] text-gray-300 hover:text-white hover:border-[#00e5ff] text-[10px] font-bold tracking-wider py-4 rounded-none transition-all'
                                )

                # Panel Derecho
                with ui.column().classes('flex-1 bg-[#0a0a0a]/75 backdrop-blur-md border border-[#00e5ff]/30 p-8 relative min-w-[400px] shadow-[0_0_20px_rgba(0,0,0,0.8)] min-h-[550px]'):
                    ui.label('MACROS DE ILUMINACION').classes('text-sm font-bold tracking-[0.3em] text-white mb-8 border-b border-[#00e5ff]/30 pb-2 w-full text-center drop-shadow-[0_0_5px_#00e5ff]')
                    
                    btn_class = 'w-full bg-[#000000]/60 border border-[#333] text-gray-300 hover:border-[#00e5ff] hover:text-[#00e5ff] hover:shadow-[0_0_15px_rgba(0,229,255,0.3)] font-bold tracking-[0.2em] py-4 px-6 rounded-none transition-all duration-300 text-left mb-5'
                    
                    with ui.column().classes('w-full'):
                        ui.button('MODO RESPIRACION', on_click=lambda: enviar_comando('RESPIRA,255,255,255')).classes(btn_class)
                        ui.button('MODO ESTROBOSCOPICO (FLASH)', on_click=lambda: enviar_comando('FLASH,255,255,255')).classes(btn_class)
                        ui.button('CICLO ESPECTRAL (ARCOIRIS)', on_click=lambda: enviar_comando('ARCOIRIS')).classes(btn_class)
                        ui.button('ILUMINACION TACTICA (LOW)', on_click=lambda: enviar_comando('LOW,20,50,60')).classes(btn_class)
                        
                        ui.html('<div class="w-full h-[1px] bg-[#00e5ff]/20 my-4"></div>')
                        
                        ui.button('DESACTIVAR ILUMINACION', on_click=lambda: enviar_comando('OFF')).classes(
                            'w-full bg-[#1a0505]/80 border border-red-900 text-red-500 hover:bg-red-900 hover:text-white '
                            'font-bold tracking-[0.2em] py-4 rounded-none transition-all shadow-[0_0_15px_rgba(255,0,0,0.1)] mt-auto'
                        )

        # ==========================================
        # PESTAÑA 2: BIBLIOTECA (Translúcida)
        # ==========================================
        with ui.tab_panel(tab_biblio).classes('w-full p-8 bg-transparent'):
            
            with ui.row().classes('w-full justify-between items-center mb-8 pb-4 border-b border-[#00e5ff]/30'):
                ui.label('CENTRO DE COMANDO TÁCTICO').classes('text-sm font-bold tracking-[0.4em] text-white leading-none pl-2 drop-shadow-[0_0_5px_#00e5ff]')
                ui.label(f'{len(juegos_guardados)} UNIDADES REGISTRADAS').classes('text-[9px] tracking-[0.3em] text-[#00e5ff] font-bold pr-2')

            @ui.refreshable
            def renderizar_grid_juegos():
                with ui.row().classes('w-full flex-wrap gap-8 items-start justify-start max-w-[1400px] mx-auto'):
                    for i, juego in enumerate(juegos_guardados):
                        
                        with ui.column().classes('group relative bg-[#0a0a0a]/80 backdrop-blur-md border border-[#00e5ff]/20 p-0 shadow-[0_0_15px_rgba(0,0,0,0.9)] transition-all duration-300 w-48 h-72 hover:border-[#00e5ff] hover:shadow-[0_0_25px_rgba(0,229,255,0.4)] overflow-hidden'):
                            
                            if juego.get('img_ruta') and os.path.exists(juego['img_ruta']):
                                ui.image(juego['img_ruta']).classes('w-full h-full object-contain p-6 bg-transparent transition-transform duration-300 group-hover:scale-110 drop-shadow-[0_0_10px_rgba(0,229,255,0.2)]')
                            else:
                                letras = juego['titulo'][:2].upper() if len(juego['titulo']) >= 2 else juego['titulo'].upper()
                                with ui.column().classes('w-full h-full bg-transparent items-center justify-center'):
                                    ui.label(letras).classes('text-[40px] tracking-[0.2em] text-[#00e5ff] font-black opacity-40 drop-shadow-[0_0_10px_#00e5ff]')
                            
                            with ui.row().classes('absolute bottom-0 left-0 right-0 bg-[#000000]/90 border-t border-[#00e5ff]/30 p-3 justify-center backdrop-blur-xl'):
                                ui.label(juego['titulo'].upper()).classes('text-[10px] font-bold tracking-[0.1em] text-white truncate w-full text-center')

                            with ui.column().classes('absolute inset-0 bg-[#000000]/90 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300 p-4 items-center justify-center z-20'):
                                ui.button('X', on_click=lambda idx=i: borrar_juego(idx)).classes('absolute top-1 right-1 text-red-500 bg-transparent text-[12px] p-2 min-w-0 min-h-0 font-black rounded-none hover:text-white drop-shadow-[0_0_5px_red]')
                                
                                ui.label('PERFIL ASIGNADO:').classes('text-[8px] text-gray-400 font-bold tracking-[0.2em] mb-1')
                                ui.label(juego['perfil_nombre']).classes('text-[9px] text-[#00e5ff] font-bold tracking-[0.1em] text-center w-full truncate mb-6 drop-shadow-[0_0_5px_#00e5ff]')
                                
                                ui.button('LANZAR', on_click=lambda j=juego: lanzar_juego(j['ruta'], j['comando_rgb'])).classes(
                                    'bg-transparent border border-[#00e5ff] text-[#00e5ff] hover:bg-[#00e5ff] hover:text-black '
                                    'font-bold tracking-[0.2em] px-6 py-2 rounded-none transition-all shadow-[0_0_15px_rgba(0,229,255,0.4)] hover:shadow-[0_0_25px_#00e5ff]'
                                )

                    with ui.column().classes('bg-[#000000]/50 backdrop-blur-sm border border-dashed border-[#00e5ff]/30 w-48 h-72 items-center justify-center hover:border-[#00e5ff] hover:bg-[#00e5ff]/10 transition-all cursor-pointer shadow-lg').on('click', lambda: dialog_agregar.open()):
                        ui.label('+').classes('text-4xl text-[#00e5ff] font-black mb-2 drop-shadow-[0_0_8px_#00e5ff]')
                        ui.label('REGISTRAR').classes('text-[10px] tracking-[0.3em] text-white font-bold')
                        ui.label('UNIDAD').classes('text-[10px] tracking-[0.3em] text-white font-bold')

            renderizar_grid_juegos()

            def borrar_juego(index):
                juegos_guardados.pop(index)
                guardar_juegos()
                ui.notify('[SISTEMA] UNIDAD BORRADA', type='warning')
                renderizar_grid_juegos.refresh()

            def agregar_juego():
                perfiles_disponibles = {
                    'FIJO,255,255,255': 'ROJO MAXIMO',
                    'FIJO,0,255,0': 'VERDE MAXIMO',
                    'FIJO,0,0,255': 'AZUL MAXIMO',
                    'RESPIRA,0,229,255': 'RESPIRACION CIAN',
                    'FLASH,255,0,0': 'ALERTA ROJA (FLASH)',
                    'ARCOIRIS': 'ARCOIRIS ESPECTRAL'
                }
                
                t = titulo_input.value
                r = ruta_input.value
                c = rgb_select.value
                
                if not t or not r or not c:
                    ui.notify('Selecciona el .exe y el perfil de color', type='warning')
                    return
                
                juegos_guardados.append({
                    'titulo': t,
                    'ruta': r.strip().strip('"').strip("'"),
                    'img_ruta': cache_temporal_icono["ruta_png"],
                    'comando_rgb': c,
                    'perfil_nombre': perfiles_disponibles[c]
                })
                guardar_juegos()
                ui.notify('[OK] UNIDAD REGISTRADA', type='positive')
                renderizar_grid_juegos.refresh()
                dialog_agregar.close()
                titulo_input.set_value('')
                ruta_input.set_value('')
                cache_temporal_icono["ruta_png"] = ""

            with ui.dialog() as dialog_agregar:
                with ui.card().classes('bg-[#0a0a0a]/90 backdrop-blur-xl border border-[#00e5ff] p-6 w-[600px] shadow-[0_0_30px_rgba(0,229,255,0.2)]'):
                    ui.label('REGISTRAR NUEVO JUEGO AUTOMATIZADO').classes('text-white font-bold tracking-widest mb-4 drop-shadow-[0_0_5px_#00e5ff]')
                    
                    ui.label('1. Selecciona el Juego').classes('text-[10px] tracking-widest text-[#00e5ff] mb-1')
                    with ui.row().classes('w-full items-center gap-2 mb-4 flex-nowrap'):
                        ruta_input = ui.input('Ruta del .exe').classes('flex-1').props('dark color="cyan"')
                        ui.button(icon='folder', on_click=buscar_exe_y_extraer).classes('bg-[#000000]/60 border border-[#00e5ff] text-[#00e5ff] h-[56px] w-[56px] rounded-none hover:bg-[#00e5ff] hover:text-black transition-all')
                    
                    ui.label('2. Confirma el Título (Auto-rellenado)').classes('text-[10px] tracking-widest text-[#00e5ff] mb-1')
                    titulo_input = ui.input('Nombre del Juego').classes('w-full mb-6').props('dark color="cyan"')
                    
                    ui.label('3. Asigna la Iluminación Táctica').classes('text-[10px] tracking-widest text-[#00e5ff] mb-1')
                    opciones_rgb = {
                        'FIJO,255,0,0': 'ROJO MAXIMO',
                        'FIJO,0,255,0': 'VERDE MAXIMO',
                        'FIJO,0,0,255': 'AZUL MAXIMO',
                        'RESPIRA,0,229,255': 'RESPIRACION CIAN',
                        'FLASH,255,0,0': 'ALERTA ROJA (FLASH)',
                        'ARCOIRIS': 'ARCOIRIS ESPECTRAL'
                    }
                    rgb_select = ui.select(opciones_rgb, label='Elige el Perfil AlienFX').classes('w-full mb-8').props('dark color="cyan"')
                    
                    with ui.row().classes('w-full gap-4'):
                        ui.button('CANCELAR', on_click=dialog_agregar.close).classes('flex-1 bg-transparent border border-red-500 text-red-500 font-bold tracking-widest rounded-none hover:bg-red-900')
                        ui.button('GUARDAR', on_click=agregar_juego).classes('flex-1 bg-[#00e5ff] text-black font-bold tracking-widest rounded-none hover:bg-white shadow-[0_0_15px_rgba(0,229,255,0.4)]')

ui.run(native=True, window_size=(1280, 720), title="AlienFX Custom Core", frameless=False, favicon='icon2.ico')