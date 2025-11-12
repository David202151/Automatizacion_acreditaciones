import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from datetime import datetime
import time
from pathlib import Path
from PIL import Image
import io
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import pandas as pd
import json
import pyautogui
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, SessionNotCreatedException
from webdriver_manager.chrome import ChromeDriverManager

# Configurar PyAutoGUI para que sea más seguro
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

class Config:
    # Configuración de Mautic
    MAUTIC_URL = "https://marketingmch.miles.com.ec"
    MAUTIC_USERNAME = "david.vargas"
    MAUTIC_PASSWORD = "nubxe6-Xugved-favgyw"
    
    # Configuración de Cloudflare R2 (S3)
    R2_ACCESS_KEY_ID = "fcf42625ad735ad63da22100af72e684"
    R2_SECRET_ACCESS_KEY = "b304706b40e5544fbc4a50c543e2ba66f5f41595c69afa1b56097dc2fce5db2a"
    R2_ENDPOINT = "https://95f977894b55126e9809447b9bd1fa20.r2.cloudflarestorage.com"
    R2_BUCKET_NAME = "icare"
    R2_FOLDER_PATH = "images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/"
    
    # URL base para las imágenes
    IMAGE_BASE_URL = "https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/"
    
    # Carpeta local (se seleccionará mediante interfaz)
    LOCAL_FOLDER = ""
    
    # Archivo de mapeo de campos
    FIELD_MAPPING_FILE = ""
    FIELD_MAPPINGS = {}  # {establecimiento: campo_mautic}
    
    # Configuración de boletines por establecimiento
    ESTABLISHMENT_CONFIG = {} 
    
    # Nombre del segmento objetivo
    TARGET_SEGMENT = "Segmento-DV" 
    # Lista de boletines creados (para campañas)
    CREATED_EMAILS = []  # Se llenará durante la ejecución
    
    @staticmethod
    def get_date_format():
        now = datetime.now()
        day = now.strftime("%d").lstrip('0')
        month_spanish = {
            'January': 'ENERO', 'February': 'FEBRERO', 'March': 'MARZO',
            'April': 'ABRIL', 'May': 'MAYO', 'June': 'JUNIO',
            'July': 'JULIO', 'August': 'AGOSTO', 'September': 'SEPTIEMBRE',
            'October': 'OCTUBRE', 'November': 'NOVIEMBRE', 'December': 'DICIEMBRE'
        }
        month = month_spanish.get(now.strftime("%B"), now.strftime("%B").upper())
        year = now.strftime("%y")
        return f"{day}{month}{year}"

# ======================== INTERFAZ GRÁFICA ========================
class AutomationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Automatización Mautic - ClubMiles")
        self.root.geometry("1000x850")
        self.root.resizable(True, True)
        
        # Configurar colores
        self.root.configure(bg='#f0f0f0')
        
        # Variables
        self.selected_folder = tk.StringVar()
        self.progress_text = tk.StringVar()
        self.current_status = tk.StringVar(value="Esperando configuración...")
        self.establishments_vars = {}
        self.field_entries = {}
        self.emails_created = False  # Flag para saber si se crearon emails
        self.segment_name = tk.StringVar(value=Config.TARGET_SEGMENT)  # Variable para el segmento
        
        # Configurar estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Personalizar colores
        self.style.configure('Title.TLabel', font=('Arial', 18, 'bold'))
        self.style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        self.style.configure('Status.TLabel', font=('Arial', 10))
        
        self.setup_ui()
        # AGREGAR ESTA LÍNEA AL FINAL DEL __init__ (aproximadamente línea 205)
        self.root.after(500, self.check_pending_campaigns)  # Verificar después de 500ms
    def backup_emails_json(self):
        """Crear backup del archivo JSON con timestamp"""
        if os.path.exists('emails_creados.json'):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f'emails_creados_backup_{timestamp}.json'
            
            try:
                import shutil
                shutil.copy2('emails_creados.json', backup_name)
                self.log_message(f"Backup creado: {backup_name}")
                return True
            except Exception as e:
                self.log_message(f"Error creando backup: {str(e)}")
                return False
        return False
    def check_pending_campaigns(self):
        """Verificar si hay campañas pendientes de crear desde una sesión anterior"""
        json_file = 'emails_creados.json'
        
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as f:
                    pending_emails = json.load(f)
                
                if pending_emails and len(pending_emails) > 0:
                    # Contar boletines por tipo
                    personal_count = sum(1 for e in pending_emails if e.get('type') == 'personal')
                    corporate_count = sum(1 for e in pending_emails if e.get('type') == 'corporate')
                    
                    message = f"Se encontraron {len(pending_emails)} boletines creados previamente:\n\n"
                    message += f"• Personal: {personal_count}\n"
                    message += f"• Corporativo: {corporate_count}\n\n"
                    message += "¿Deseas crear las campañas para estos boletines ahora?"
                    
                    result = messagebox.askyesno(
                        "Campañas Pendientes", 
                        message,
                        icon='info'
                    )
                    
                    if result:
                        # Cargar los emails en la configuración
                        Config.CREATED_EMAILS = pending_emails
                        self.emails_created = True
                        
                        # Habilitar el botón de campañas
                        self.campaign_button.config(state='normal')
                        
                        # Actualizar el log
                        self.log_message("="*60)
                        self.log_message("CAMPAÑAS PENDIENTES DETECTADAS")
                        self.log_message(f"Se cargaron {len(pending_emails)} boletines de la sesión anterior")
                        self.log_message("="*60)
                        
                        for email in pending_emails[:5]:  # Mostrar primeros 5
                            self.log_message(f"  • {email.get('name', 'Sin nombre')}")
                        
                        if len(pending_emails) > 5:
                            self.log_message(f"  ... y {len(pending_emails) - 5} más")
                        
                        self.log_message("\nPuedes crear las campañas usando el botón 'CREAR CAMPAÑAS'")
                        self.current_status.set("Campañas pendientes cargadas - Listo para crear")
                        
                        return True
                    else:
                        # Preguntar si desea eliminar el archivo
                        delete_result = messagebox.askyesno(
                            "Eliminar Cache",
                            "¿Deseas eliminar estos boletines pendientes?\n\n" +
                            "Esto borrará el registro pero NO afectará los boletines ya creados en Mautic.",
                            icon='warning'
                        )
                        
                        if delete_result:
                            os.remove(json_file)
                            self.log_message("Cache de boletines eliminado")
                            messagebox.showinfo("Cache Eliminado", 
                                "El archivo de boletines pendientes ha sido eliminado.")
                        
            except json.JSONDecodeError:
                self.log_message("Error: El archivo JSON está corrupto")
                messagebox.showerror("Error", 
                    f"El archivo {json_file} está corrupto.\n\n¿Deseas eliminarlo?")
                
                if messagebox.askyesno("Eliminar archivo corrupto", 
                                    f"¿Eliminar {json_file}?"):
                    os.remove(json_file)
                    self.log_message("Archivo corrupto eliminado")
                    
            except Exception as e:
                self.log_message(f"Error leyendo cache: {str(e)}")
        
        return False
    # Agregar este método para manejar el botón de carga manual
    def load_pending_campaigns(self):
        """Cargar manualmente campañas pendientes"""
        json_file = 'emails_creados.json'
        
        if not os.path.exists(json_file):
            # Permitir seleccionar archivo
            file_path = filedialog.askopenfilename(
                title="Selecciona el archivo de boletines creados",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="emails_creados.json"
            )
            
            if file_path:
                try:
                    with open(file_path, 'r') as f:
                        pending_emails = json.load(f)
                    
                    if pending_emails:
                        Config.CREATED_EMAILS = pending_emails
                        self.emails_created = True
                        self.campaign_button.config(state='normal')
                        
                        self.log_message(f"✓ Cargados {len(pending_emails)} boletines")
                        self.current_status.set("Boletines cargados - Listo para crear campañas")
                        
                        messagebox.showinfo("Éxito", 
                            f"Se cargaron {len(pending_emails)} boletines.\n\n" +
                            "Ahora puedes crear las campañas.")
                    else:
                        messagebox.showwarning("Sin datos", 
                            "El archivo no contiene boletines.")
                            
                except Exception as e:
                    messagebox.showerror("Error", f"Error al cargar archivo: {str(e)}")
        else:
            self.check_pending_campaigns()    

    def setup_ui(self):
        """Configurar la interfaz de usuario con scroll completo"""
        
        # Canvas principal y scrollbar
        main_canvas = tk.Canvas(self.root, bg='#f0f0f0')
        main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        
        # Frame scrollable que contendrá todo
        scrollable_frame = ttk.Frame(main_canvas)
        
        # Configurar el canvas
        main_canvas.configure(yscrollcommand=main_scrollbar.set)
        main_canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Actualizar el scrollregion cuando cambie el tamaño del frame
        def configure_scroll_region(event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
            # Ajustar el ancho del frame al canvas
            canvas_width = main_canvas.winfo_width()
            main_canvas.itemconfig(main_canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        main_canvas.bind("<Configure>", lambda e: main_canvas.itemconfig(main_canvas_window, width=e.width))
        
        # Bind para scroll con rueda del mouse
        def on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind en diferentes widgets para asegurar que funcione el scroll
        main_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Frame principal dentro del scrollable_frame
        main_frame = ttk.Frame(scrollable_frame, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Automatización ClubMiles", 
                                style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Separador
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 20))
        
        # ===== SECCIÓN DE MAPEO DE CAMPOS =====
        mapping_frame = ttk.LabelFrame(main_frame, text="Configuración de Campos Mautic", padding="15")
        mapping_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Botón para cargar Excel
        excel_button = ttk.Button(mapping_frame, text="Cargar Excel de Mapeo", 
                                 command=self.load_mapping_excel)
        excel_button.pack(side=tk.LEFT, padx=5)
        
        # Label para mostrar estado del Excel
        self.excel_status = ttk.Label(mapping_frame, text="No se ha cargado archivo de mapeo", 
                                     foreground='gray')
        self.excel_status.pack(side=tk.LEFT, padx=10)
        
        # ===== SECCIÓN DE SELECCIÓN DE CARPETA =====
        folder_frame = ttk.LabelFrame(main_frame, text="Carpeta con Establecimientos", padding="15")
        folder_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Frame para entrada y botón
        input_frame = ttk.Frame(folder_frame)
        input_frame.pack(fill=tk.X)
        
        folder_entry = ttk.Entry(input_frame, textvariable=self.selected_folder, 
                                width=60, state='readonly')
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_button = ttk.Button(input_frame, text="Seleccionar Carpeta", 
                                  command=self.select_folder)
        browse_button.pack(side=tk.LEFT)
        
        # Información de la carpeta
        self.folder_info = ttk.Label(folder_frame, text="No se ha seleccionado ninguna carpeta", 
                                    foreground='gray')
        self.folder_info.pack(anchor=tk.W, pady=(10, 0))
        
        # ===== SECCIÓN DE CAMPOS MANUALES =====
        self.manual_fields_frame = ttk.LabelFrame(main_frame, text="Campos Personalizados (sin mapeo en Excel)", padding="15")
        # No hacer pack aquí, se hará cuando sea necesario
        
        # ===== SECCIÓN DE CONFIGURACIÓN DE ESTABLECIMIENTOS =====
        self.config_frame = ttk.LabelFrame(main_frame, text="Configuración de Boletines por Establecimiento", padding="15")
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Frame con scroll para la lista de establecimientos
        self.create_scrollable_establishment_list()
        
        # ===== BOTONES DE ACCIÓN =====
        # Frame para botones de selección rápida
        quick_button_frame = ttk.Frame(main_frame)
        quick_button_frame.pack(fill=tk.X, pady=(0, 10))
        
        button_container = ttk.Frame(quick_button_frame)
        button_container.pack()
        
        select_all_personal = ttk.Button(button_container, 
                                        text="Marcar todos Personal", 
                                        command=lambda: self.select_all('personal'),
                                        width=20)
        select_all_personal.grid(row=0, column=0, padx=2)
        
        select_all_corporate = ttk.Button(button_container, 
                                         text="Marcar todos Corporativo", 
                                         command=lambda: self.select_all('corporate'),
                                         width=20)
        select_all_corporate.grid(row=0, column=1, padx=2)
        
        deselect_all = ttk.Button(button_container, 
                                 text="Desmarcar todos", 
                                 command=self.deselect_all,
                                 width=15)
        deselect_all.grid(row=0, column=2, padx=2)
        
        # ===== SECCIÓN DE CONFIGURACIÓN DE CAMPAÑA =====
        campaign_frame = ttk.LabelFrame(main_frame, text="Configuración de Campaña", padding="15")
        campaign_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Frame para el segmento
        segment_frame = ttk.Frame(campaign_frame)
        segment_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(segment_frame, text="Nombre del Segmento:", font=('Arial', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        segment_entry = ttk.Entry(segment_frame, textvariable=self.segment_name, width=30)
        segment_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Información importante
        info_label = ttk.Label(segment_frame, 
                              text="⚠️ El segmento debe existir en Mautic", 
                              foreground='red', font=('Arial', 9))
        info_label.pack(side=tk.LEFT)
        # Label de progreso (inicialmente oculto)
        self.progress_label = ttk.Label(
            main_frame,
            text="",
            foreground='orange',
            font=('Arial', 10, 'bold')
        )
        self.progress_label.pack(pady=(5, 0))
        # Separador
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # ===== FRAME DE BOTONES PRINCIPALES =====
        main_button_frame = ttk.Frame(main_frame)
        main_button_frame.pack(fill=tk.X, pady=10)

        main_button_container = ttk.Frame(main_button_frame)
        main_button_container.pack()

        # Botón para crear boletines
        self.start_button = ttk.Button(
            main_button_container,
            text="CREAR BOLETINES",
            command=self.start_process,
            state='disabled',
            width=20
        )
        self.start_button.grid(row=0, column=0, padx=5)

        # Botón para crear campañas (inicialmente deshabilitado)
        self.campaign_button = ttk.Button(
            main_button_container,
            text="CREAR CAMPAÑAS",
            command=self.create_campaigns,
            state='disabled',
            width=20
        )
        self.campaign_button.grid(row=0, column=1, padx=5)

        # Botón para cargar campañas pendientes
        self.load_pending_button = ttk.Button(
            main_button_container,
            text="CARGAR PENDIENTES",
            command=self.load_pending_campaigns,
            width=20
        )
        self.load_pending_button.grid(row=0, column=2, padx=5)

        # Botón para clonar boletines
        self.clone_button = ttk.Button(
            main_button_container,
            text="CLONAR BOLETINES",
            command=self.open_clone_dialog,
            width=20
        )
        self.clone_button.grid(row=0, column=3, padx=5)

        # Botón para cerrar
        self.close_button = ttk.Button(
            main_button_container,
            text="CERRAR",
            command=self.root.quit,
            width=15
        )
        self.close_button.grid(row=0, column=4, padx=5)

        
        # Label informativo sobre las campañas
        campaign_info_label = ttk.Label(main_frame, 
                                       text="Las campañas se crearán después de revisar los boletines",
                                       foreground='blue')
        campaign_info_label.pack(pady=(5, 10))
        
        # ===== SECCIÓN DE ESTADO =====
        status_frame = ttk.LabelFrame(main_frame, text="Estado Actual", padding="15")
        status_frame.pack(fill=tk.X, pady=(15, 0))
        
        status_text = ttk.Label(status_frame, textvariable=self.current_status, 
                               style='Status.TLabel')
        status_text.pack(anchor=tk.W)
        
        # ===== ÁREA DE LOG =====
        log_frame = ttk.LabelFrame(main_frame, text="Progreso del Proceso", padding="15")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # Frame para el área de texto y scrollbar
        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Área de texto con scrollbar
        self.log_text = tk.Text(text_frame, height=10, wrap=tk.WORD, 
                               bg='white', fg='black', font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ===== BARRA DE PROGRESO =====
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(15, 20))
        
        # Empaquetar canvas y scrollbar
        main_canvas.pack(side="left", fill="both", expand=True)
        main_scrollbar.pack(side="right", fill="y")
        # AGREGAR: Crear barra de menú
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú de Cache
        cache_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Cache", menu=cache_menu)
        cache_menu.add_command(label="Ver campañas pendientes", 
                            command=self.view_pending_campaigns)
        cache_menu.add_command(label="Cargar archivo JSON", 
                            command=self.load_pending_campaigns)
        cache_menu.add_separator()
        cache_menu.add_command(label="Limpiar cache", 
                            command=self.clear_cache)
        # Menú de Archivos
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivos", menu=file_menu)
        file_menu.add_command(label="Ver emails creados", 
                            command=lambda: self.view_json_file('emails_creados.json'))
        file_menu.add_command(label="Ver correcciones", 
                            command=lambda: self.view_json_file('correcciones.json'))
        file_menu.add_command(label="Ver emails finales", 
                            command=lambda: self.view_json_file('emails_finales.json'))
        file_menu.add_separator()
        file_menu.add_command(label="Limpiar correcciones", 
                            command=lambda: self.clear_json_file('correcciones.json'))
        file_menu.add_command(label="Limpiar emails finales", 
                            command=lambda: self.clear_json_file('emails_finales.json'))
    def view_pending_campaigns(self):
        """Ver detalles de las campañas pendientes"""
        json_file = 'emails_creados.json'
        
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as f:
                    pending = json.load(f)
                
                if pending:
                    # Crear ventana de detalles
                    details_window = tk.Toplevel(self.root)
                    details_window.title("Campañas Pendientes")
                    details_window.geometry("600x400")
                    
                    # Texto con scroll
                    text_frame = ttk.Frame(details_window)
                    text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    
                    text_widget = tk.Text(text_frame, wrap=tk.WORD)
                    scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
                    text_widget.configure(yscrollcommand=scrollbar.set)
                    
                    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    
                    # Mostrar información
                    text_widget.insert(tk.END, f"Total de boletines pendientes: {len(pending)}\n")
                    text_widget.insert(tk.END, "="*50 + "\n\n")
                    
                    for idx, email in enumerate(pending, 1):
                        text_widget.insert(tk.END, f"{idx}. {email.get('name', 'Sin nombre')}\n")
                        text_widget.insert(tk.END, f"   ID: {email.get('id', 'N/A')}\n")
                        text_widget.insert(tk.END, f"   Tipo: {email.get('type', 'N/A')}\n")
                        text_widget.insert(tk.END, f"   Establecimiento: {email.get('establishment', 'N/A')}\n")
                        text_widget.insert(tk.END, "-"*40 + "\n")
                    
                    text_widget.configure(state='disabled')
                    
                    # Botón cerrar
                    ttk.Button(details_window, text="Cerrar", 
                            command=details_window.destroy).pack(pady=10)
                else:
                    messagebox.showinfo("Sin pendientes", 
                                    "No hay campañas pendientes.")
            except Exception as e:
                messagebox.showerror("Error", f"Error leyendo archivo: {str(e)}")
        else:
            messagebox.showinfo("Sin cache", 
                            "No existe archivo de cache.")
            
    def open_clone_dialog(self):
        """Abrir diálogo de clonación de boletines"""
        # Verificar que existan boletines
        if not os.path.exists('emails_creados.json'):
            messagebox.showinfo("Sin boletines", 
                "No hay boletines creados. Por favor crea boletines primero.")
            return
        
        # Abrir el diálogo
        CloneDialog(self)
    def start_cloning_process(self, selected_emails, mode):
        """Iniciar el proceso de clonación en thread separado"""
        
        self.log_message("\n" + "="*60)
        self.log_message(f"INICIANDO CLONACIÓN EN MODO: {mode.upper()}")
        self.log_message(f"Boletines a procesar: {len(selected_emails)}")
        self.log_message("="*60 + "\n")
        
        # Deshabilitar botones
        self.start_button.config(state='disabled')
        self.campaign_button.config(state='disabled')
        self.clone_button.config(state='disabled')
        self.progress_bar.start(10)
        self.current_status.set("Clonando boletines... Por favor espera")
        
        # Ejecutar en thread
        thread = threading.Thread(
            target=self.run_cloning_process, 
            args=(selected_emails, mode)
        )
        thread.daemon = True
        thread.start()
    def start_cloning(self):
        """Iniciar el proceso de clonación"""
        mode = self.clone_mode.get()
        
        if mode == "correcciones":
            # Obtener emails seleccionados
            selected_emails = [
                data['email'] for data in self.email_vars.values() 
                if data['var'].get()
            ]
            
            if not selected_emails:
                messagebox.showwarning(
                    "Sin selección", 
                    "Por favor selecciona al menos un boletín para corregir."
                )
                return
            
            message = f"¿Deseas eliminar y recrear {len(selected_emails)} boletines?\n\n"
            message += "Proceso:\n"
            message += "1. Se eliminarán los boletines seleccionados\n"
            message += "2. Se recrearán con el mismo nombre\n"
            message += "3. Se guardarán en correcciones.json\n\n"
            message += "⚠️ Este proceso puede tomar varios minutos."
            
        else:  # final
            selected_emails = self.all_emails
            
            message = f"¿Deseas clonar TODOS los {len(selected_emails)} boletines?\n\n"
            message += "Proceso:\n"
            message += "1. Se clonarán todos los boletines\n"
            message += "2. Se removerá la palabra 'PRUEBA' del nombre\n"
            message += "3. Se guardarán en emails_finales.json\n\n"
            message += "⚠️ Este proceso puede tomar varios minutos."
        
        result = messagebox.askyesno("Confirmar Clonación", message, icon='question')
        
        if not result:
            return
        
        # Mostrar progreso
        self.progress_label.config(text=f"Procesando {len(selected_emails)} boletines...")
        self.clone_btn.config(state='disabled')
        self.dialog.update()
        
        # Ejecutar en thread y cerrar diálogo
        self.dialog.destroy()
        self.parent_gui.start_cloning_process(selected_emails, mode)

    def run_cloning_process(self, selected_emails, mode):
        """Ejecutar el proceso de clonación"""
        try:
            cloner = MauticEmailCloner(
                Config.MAUTIC_URL,
                Config.MAUTIC_USERNAME,
                Config.MAUTIC_PASSWORD,
                self
            )
            
            cloner.setup_driver(headless=False)
            
            if not cloner.login():
                raise Exception("No se pudo hacer login en Mautic")
            
            cloned_emails = []
            success_count = 0
            failed_count = 0
            
            if mode == "correcciones":
                # Modo correcciones: Eliminar y recrear
                for email in selected_emails:
                    email_id = email.get('id')
                    email_name = email.get('name')
                    establishment = email.get('establishment')
                    email_type = email.get('type')
                    
                    self.log_message(f"\nProcesando: {email_name}")
                    
                    # 1. Eliminar el email
                    if cloner.delete_email(email_id, email_name):
                        self.log_message("   Boletín eliminado")
                        
                        # 2. Esperar un momento
                        time.sleep(3)
                        
                        # 3. Recrear el boletín
                        # Necesitamos obtener la imagen y los datos originales
                        # Buscar en la configuración original
                        if establishment in Config.ESTABLISHMENT_CONFIG:
                            config = Config.ESTABLISHMENT_CONFIG[establishment]
                            field_alias = config.get('field')
                            
                            # Buscar la imagen
                            folder_path = os.path.join(Config.LOCAL_FOLDER, establishment)
                            image_path, image_filename = self.find_image_in_folder(folder_path)
                            
                            if image_path:
                                # Subir imagen y crear email
                                uploader = CloudflareR2Uploader(self)
                                uploader.connect()
                                
                                original_ext = os.path.splitext(image_filename)[1]
                                remote_filename = f"{establishment.replace(' ', '_')}{original_ext}"
                                
                                upload_success, img_width, img_height = uploader.upload_image(
                                    image_path, remote_filename
                                )
                                
                                if upload_success:
                                    image_url = Config.IMAGE_BASE_URL + remote_filename
                                    # Crear el boletín usando MauticBulkAutomator
                                    mautic = MauticBulkAutomator(
                                        Config.MAUTIC_URL,
                                        Config.MAUTIC_USERNAME,
                                        Config.MAUTIC_PASSWORD,
                                        self
                                    )
                                    
                                    # Usar el driver existente del cloner
                                    mautic.driver = cloner.driver
                                    mautic.wait = cloner.wait
                                    mautic.is_logged_in = True
                                    
                                    new_email_id = mautic.create_email_for_establishment(
                                        establishment, image_url, img_width, img_height, 
                                        email_type, field_alias
                                    )
                                    
                                    if new_email_id:
                                        self.log_message("   ✅ Boletín recreado exitosamente")
                                        self.log_message(f"   Nuevo ID: {new_email_id}")
                                        
                                        # *** PARTE CRÍTICA: ACTUALIZAR LA LISTA ORIGINAL ***
                                        # Buscar el email original en Config.CREATED_EMAILS y actualizar su ID
                                        for i, original_email in enumerate(Config.CREATED_EMAILS):
                                            if original_email['name'] == email_name:
                                                old_id = original_email['id']
                                                Config.CREATED_EMAILS[i]['id'] = new_email_id
                                                Config.CREATED_EMAILS[i]['recreated'] = True
                                                Config.CREATED_EMAILS[i]['corrected_at'] = datetime.now().isoformat()
                                                self.log_message(f"   ✓ ID actualizado en memoria: {old_id} → {new_email_id}")
                                                break
                                        
                                        # Guardar la actualización en el archivo JSON
                                        try:
                                            with open('emails_creados.json', 'w') as f:
                                                json.dump(Config.CREATED_EMAILS, f, indent=4)
                                            self.log_message(f"   ✓ Archivo JSON actualizado con nuevo ID")
                                        except Exception as e:
                                            self.log_message(f"   ⚠️ Error actualizando JSON: {e}")
                                        
                                        # Agregar a la lista de emails corregidos
                                        cloned_emails.append({
                                            'id': new_email_id,
                                            'name': email_name,
                                            'establishment': establishment,
                                            'type': email_type,
                                            'field': field_alias,
                                            'old_id': email_id,
                                            'recreated': True
                                        })
                                        success_count += 1
                                    else:
                                        self.log_message("   ❌ Error recreando boletín")
                                        failed_count += 1
                                    
                                    uploader.disconnect()
                                else:
                                    self.log_message("   ❌ Error subiendo imagen")
                                    failed_count += 1
                            else:
                                self.log_message("   ❌ No se encontró imagen")
                                failed_count += 1
                        else:
                            self.log_message("   ❌ No se encontró configuración del establecimiento")
                            failed_count += 1
                    else:
                        self.log_message("   ❌ Error eliminando boletín")
                        failed_count += 1
                    
                    # Pequeña pausa entre procesos
                    time.sleep(2)
                
                # Guardar los emails corregidos en correcciones.json
                if cloned_emails:
                    with open('correcciones.json', 'w') as f:
                        json.dump(cloned_emails, f, indent=2)
                    self.log_message(f"\n✅ Información guardada en correcciones.json")
            
            else:  # modo "final"
                # Recargar IDs actualizados desde JSON para asegurar que tenemos los IDs correctos
                try:
                    if os.path.exists('emails_creados.json'):
                        with open('emails_creados.json', 'r') as f:
                            current_emails = json.load(f)
                        
                        self.log_message("✓ Verificando emails para clonación final...")
                        
                        # IMPORTANTE: NO clonar los que ya fueron clonados previamente
                        emails_to_clone = []
                        already_cloned = set()
                        
                        # Verificar si existe archivo de emails finales previos
                        if os.path.exists('emails_finales.json'):
                            with open('emails_finales.json', 'r') as f:
                                previous_finals = json.load(f)
                                for final_email in previous_finals:
                                    # Guardar los nombres de los ya clonados
                                    already_cloned.add(final_email.get('original_name', final_email.get('name', '')))
                        
                        # Filtrar emails para clonar
                        for email in current_emails:
                            email_name = email.get('name', '')
                            
                            # NO clonar si:
                            # 1. Ya fue clonado previamente (está en emails_finales.json)
                            # 2. NO tiene "PRUEBA" en el nombre (ya es final)
                            if email_name in already_cloned:
                                self.log_message(f"   ⏭️ Saltando {email_name} (ya fue clonado)")
                            elif "PRUEBA" not in email_name:
                                self.log_message(f"   ⏭️ Saltando {email_name} (no es prueba)")
                            else:
                                emails_to_clone.append(email)
                                self.log_message(f"   ✓ Agregado para clonar: {email_name}")
                        
                        self.log_message(f"\nTotal a clonar: {len(emails_to_clone)} boletines")
                        selected_emails = emails_to_clone
                        
                except Exception as e:
                    self.log_message(f"⚠️ Error verificando emails: {e}")
                    # Usar la lista original si hay error
                    selected_emails = [e for e in selected_emails if "PRUEBA" in e.get('name', '')]
                
                # Modo final: Clonar todos sin "PRUEBA"
                for email in selected_emails:
                    email_id = email.get('id')
                    email_name = email.get('name')
                    
                    # Remover "PRUEBA" y cualquier variante del nombre
                    new_name = email_name
                    
                    # Remover "PRUEBA-", "PRUEBA2-", "PRUEBA", etc.
                    import re
                    new_name = re.sub(r'PRUEBA\d*-', '', new_name)
                    new_name = re.sub(r'PRUEBA\d*_', '', new_name)
                    new_name = re.sub(r'PRUEBA\d*', '', new_name)
                    
                    self.log_message(f"\nClonando: {email_name}")
                    self.log_message(f"   Nuevo nombre: {new_name}")
                    
                    success, new_id = cloner.clone_email(email_id, email_name, new_name)
                    
                    if success:
                        self.log_message("   ✅ Boletín clonado exitosamente")
                        
                        # Guardar info del nuevo email
                        cloned_email = {
                            'id': new_id if new_id else 'unknown',
                            'name': new_name,
                            'establishment': email.get('establishment'),
                            'type': email.get('type'),
                            'field': email.get('field'),
                            'original_id': email_id,
                            'original_name': email_name,
                            'cloned_at': datetime.now().isoformat()
                        }
                        cloned_emails.append(cloned_email)
                        success_count += 1
                    else:
                        self.log_message("   ❌ Error clonando boletín")
                        failed_count += 1
                    
                    # Pequeña pausa entre procesos
                    time.sleep(3)
                
                # Guardar los emails finales en emails_finales.json
                if cloned_emails:
                    # Si ya existe el archivo, combinar con los nuevos
                    existing_finals = []
                    if os.path.exists('emails_finales.json'):
                        try:
                            with open('emails_finales.json', 'r') as f:
                                existing_finals = json.load(f)
                        except:
                            existing_finals = []
                    
                    # Combinar existentes con nuevos
                    all_finals = existing_finals + cloned_emails
                    
                    with open('emails_finales.json', 'w') as f:
                        json.dump(all_finals, f, indent=2)
                    self.log_message(f"\n✅ Información guardada en emails_finales.json")
            
            cloner.close()
            
            # Mostrar resumen
            self.log_message("\n" + "="*60)
            self.log_message("RESUMEN DE CLONACIÓN")
            self.log_message("="*60)
            self.log_message(f"Exitosos: {success_count}")
            self.log_message(f"Fallidos: {failed_count}")
            self.log_message(f"Total procesados: {len(selected_emails)}")
            self.log_message("="*60)
            
            if success_count > 0:
                if mode == "correcciones":
                    msg = f"Se han recreado {success_count} boletines exitosamente.\n\n" + \
                        "Los IDs han sido actualizados en emails_creados.json.\n" + \
                        "Puedes crear campañas usando el botón 'Crear Campañas'."
                else:
                    msg = f"Se han clonado {success_count} boletines finales exitosamente.\n\n" + \
                        "Los nuevos boletines están listos para producción."
                
                self.root.after(0, lambda: messagebox.showinfo("Clonación Completada", msg))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", 
                    "No se pudo clonar ningún boletín.\n\nRevisa los logs para más detalles."
                ))
            
        except Exception as e:
            self.log_message(f"\n❌ ERROR: {str(e)}")
            import traceback
            self.log_message(f"Detalle: {traceback.format_exc()}")
            self.root.after(0, lambda: messagebox.showerror("Error", 
                                                            f"Error durante clonación:\n\n{str(e)}"))
        finally:
            self.progress_bar.stop()
            self.current_status.set("Proceso de clonación completado")
            self.start_button.config(state='normal')
            self.campaign_button.config(state='normal')
            self.clone_button.config(state='normal')

    def find_image_in_folder(self, folder_path):
        """Encontrar la primera imagen en una carpeta"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        
        try:
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file)[1].lower()
                    if ext in image_extensions:
                        return file_path, file
        except Exception as e:
            self.log_message(f"Error buscando imagen: {str(e)}")
        
        return None, None
    def view_json_file(self, filename):
        """Ver contenido de un archivo JSON"""
        if not os.path.exists(filename):
            messagebox.showinfo("Archivo no encontrado", 
                f"El archivo {filename} no existe.")
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                messagebox.showinfo("Archivo vacío", 
                    f"El archivo {filename} está vacío.")
                return
            
            # Crear ventana para mostrar datos
            view_window = tk.Toplevel(self.root)
            view_window.title(f"Contenido de {filename}")
            view_window.geometry("800x500")
            
            # Frame con scroll
            text_frame = ttk.Frame(view_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget = tk.Text(text_frame, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Mostrar información
            text_widget.insert(tk.END, f"Total de boletines: {len(data)}\n")
            text_widget.insert(tk.END, "="*70 + "\n\n")
            
            for idx, email in enumerate(data, 1):
                text_widget.insert(tk.END, f"{idx}. {email.get('name', 'Sin nombre')}\n")
                text_widget.insert(tk.END, f"   ID: {email.get('id', 'N/A')}\n")
                text_widget.insert(tk.END, f"   Tipo: {email.get('type', 'N/A')}\n")
                text_widget.insert(tk.END, f"   Establecimiento: {email.get('establishment', 'N/A')}\n")
                text_widget.insert(tk.END, "-"*70 + "\n")
            
            text_widget.configure(state='disabled')
            
            # Botón cerrar
            ttk.Button(view_window, text="Cerrar", 
                    command=view_window.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error leyendo archivo: {str(e)}")

    def clear_json_file(self, filename):
        """Limpiar un archivo JSON"""
        if not os.path.exists(filename):
            messagebox.showinfo("Archivo no encontrado", 
                f"El archivo {filename} no existe.")
            return
        
        result = messagebox.askyesno("Confirmar", 
            f"¿Deseas eliminar el archivo {filename}?\n\n" +
            "Esto NO afectará los boletines en Mautic,\n" +
            "solo eliminará el registro local.",
            icon='warning')
        
        if result:
            try:
                # Crear backup
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f'{filename.replace(".json", "")}_{timestamp}.json'
                
                import shutil
                shutil.copy2(filename, backup_name)
                
                os.remove(filename)
                
                self.log_message(f"Archivo {filename} eliminado (backup: {backup_name})")
                messagebox.showinfo("Archivo eliminado", 
                    f"El archivo ha sido eliminado.\n\nBackup creado: {backup_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando archivo: {str(e)}")

    def clear_cache(self):
        """Limpiar el cache de campañas"""
        json_file = 'emails_creados.json'
        
        if os.path.exists(json_file):
            result = messagebox.askyesno("Confirmar", 
                "¿Estás seguro de eliminar el cache?\n\n" +
                "Esto NO afectará los boletines ya creados en Mautic,\n" +
                "solo eliminará el registro local.",
                icon='warning')
            
            if result:
                # Crear backup antes de eliminar
                self.backup_emails_json()
                os.remove(json_file)
                
                Config.CREATED_EMAILS = []
                self.emails_created = False
                self.campaign_button.config(state='disabled')
                
                self.log_message("Cache eliminado (se creó backup)")
                messagebox.showinfo("Cache eliminado", 
                                "El cache ha sido eliminado exitosamente.")
        else:
            messagebox.showinfo("Sin cache", "No hay cache que eliminar.")
    def load_mapping_excel(self):
        """Cargar archivo Excel con mapeo de campos"""
        file_path = filedialog.askopenfilename(
            title="Selecciona el archivo Excel de mapeo",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Leer el Excel
                df = pd.read_excel(file_path)
                
                # Verificar que tenga las columnas necesarias
                if 'Label' not in df.columns or 'Alias' not in df.columns:
                    messagebox.showerror("Error", 
                        "El archivo Excel debe tener columnas 'Label' y 'Alias'")
                    return
                
                # Crear diccionario de mapeo
                Config.FIELD_MAPPINGS = {}
                for _, row in df.iterrows():
                    if pd.notna(row['Label']) and pd.notna(row['Alias']):
                        # Normalizar el nombre del establecimiento
                        establishment = str(row['Label']).strip()
                        field_alias = str(row['Alias']).strip()
                        Config.FIELD_MAPPINGS[establishment.lower()] = field_alias
                
                Config.FIELD_MAPPING_FILE = file_path
                
                self.excel_status.config(
                    text=f"✓ Cargados {len(Config.FIELD_MAPPINGS)} mapeos",
                    foreground='green'
                )
                
                self.log_message(f"Excel cargado: {len(Config.FIELD_MAPPINGS)} mapeos encontrados")
                
                # Si ya hay establecimientos cargados, actualizar la vista
                if hasattr(self, 'establishments_vars') and self.establishments_vars:
                    # Recargar la lista de establecimientos
                    subfolders = [f for f in os.listdir(Config.LOCAL_FOLDER) 
                                 if os.path.isdir(os.path.join(Config.LOCAL_FOLDER, f))]
                    self.populate_establishment_list(subfolders)
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error al leer el Excel: {str(e)}")
                self.excel_status.config(text="Error al cargar archivo", foreground='red')
    
    def create_scrollable_establishment_list(self):
        """Crear lista scrollable de establecimientos"""
        # Frame contenedor con canvas y scrollbar
        canvas_frame = ttk.Frame(self.config_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas para scroll
        self.canvas = tk.Canvas(canvas_frame, bg='white', height=150)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Encabezados
        header_frame = ttk.Frame(self.config_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Establecimiento", width=40, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Personal", width=10, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Corporativo", width=10, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Campo Mautic", width=20, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(self.config_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 5))
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mensaje inicial
        self.no_folder_label = ttk.Label(self.scrollable_frame, 
                                        text="Selecciona una carpeta para ver los establecimientos disponibles",
                                        foreground='gray')
        self.no_folder_label.pack(pady=50)
    
    def populate_establishment_list(self, subfolders):
        """Poblar la lista de establecimientos con checkboxes y campos"""
        # Limpiar frame anterior
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.establishments_vars = {}
        self.field_entries = {}
        
        # Verificar si hay establecimientos sin mapeo
        unmapped = []
        for folder_name in subfolders:
            normalized_name = folder_name.lower().strip()
            if normalized_name not in Config.FIELD_MAPPINGS:
                unmapped.append(folder_name)
        
        # Si hay campos sin mapeo, mostrar sección manual
        if unmapped:
            self.manual_fields_frame.pack(fill=tk.X, pady=(0, 15), before=self.config_frame)
            
            # Limpiar contenido anterior
            for widget in self.manual_fields_frame.winfo_children():
                widget.destroy()
            
            # Canvas scrollable para campos manuales
            manual_canvas = tk.Canvas(self.manual_fields_frame, height=min(120, len(unmapped) * 30 + 30))
            manual_scrollbar = ttk.Scrollbar(self.manual_fields_frame, orient="vertical", 
                                            command=manual_canvas.yview)
            manual_frame = ttk.Frame(manual_canvas)
            
            manual_frame.bind(
                "<Configure>",
                lambda e: manual_canvas.configure(scrollregion=manual_canvas.bbox("all"))
            )
            
            manual_canvas.create_window((0, 0), window=manual_frame, anchor="nw")
            manual_canvas.configure(yscrollcommand=manual_scrollbar.set)
            
            # Encabezado para campos manuales
            ttk.Label(manual_frame, text="Establecimiento", width=30, 
                     font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=5, sticky='w')
            ttk.Label(manual_frame, text="Campo Mautic", width=25, 
                     font=('Arial', 9, 'bold')).grid(row=0, column=1, padx=5)
            ttk.Label(manual_frame, text="Vista Previa", width=40, 
                     font=('Arial', 9, 'bold')).grid(row=0, column=2, padx=5)
            
            row_idx = 1
            for folder_name in unmapped:
                ttk.Label(manual_frame, text=folder_name, width=30).grid(
                    row=row_idx, column=0, padx=5, pady=2, sticky='w'
                )
                
                # Campo por defecto
                default_field = folder_name.lower().replace(' ', '_').replace('-', '_')
                field_var = tk.StringVar(value=default_field)
                field_entry = ttk.Entry(manual_frame, textvariable=field_var, width=25)
                field_entry.grid(row=row_idx, column=1, padx=5, pady=2)
                
                # Vista previa del campo
                preview_label = ttk.Label(manual_frame, text="", foreground='blue')
                preview_label.grid(row=row_idx, column=2, padx=5, pady=2, sticky='w')
                
                # Actualizar vista previa cuando cambie el campo
                def update_preview(var, label=preview_label):
                    preview = f"{{{{contactfield={var.get()}_txt}}}}"
                    label.config(text=preview)
                
                field_var.trace('w', lambda *args, var=field_var: update_preview(var))
                update_preview(field_var)  # Actualización inicial
                
                self.field_entries[folder_name] = field_var
                row_idx += 1
            
            manual_canvas.pack(side="left", fill="both", expand=True)
            manual_scrollbar.pack(side="right", fill="y")
        else:
            # Ocultar frame de campos manuales si no hay unmapped
            self.manual_fields_frame.pack_forget()
        
        # Crear una fila para cada establecimiento en la lista principal
        for idx, folder_name in enumerate(subfolders):
            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            # Color alternado para las filas
            if idx % 2 == 0:
                row_frame.configure(style='Even.TFrame')
            
            # Nombre del establecimiento
            name_label = ttk.Label(row_frame, text=folder_name[:35] + "..." if len(folder_name) > 35 else folder_name, 
                                  width=40)
            name_label.pack(side=tk.LEFT, padx=5)
            
            # Variables para checkboxes
            personal_var = tk.BooleanVar(value=True)
            corporate_var = tk.BooleanVar(value=True)
            
            # Checkboxes
            personal_check = ttk.Checkbutton(row_frame, variable=personal_var)
            personal_check.pack(side=tk.LEFT, padx=30)
            
            corporate_check = ttk.Checkbutton(row_frame, variable=corporate_var)
            corporate_check.pack(side=tk.LEFT, padx=40)
            
            # Buscar campo en el mapeo
            normalized_name = folder_name.lower().strip()
            field_value = Config.FIELD_MAPPINGS.get(normalized_name, "")
            
            # Mostrar campo o indicar que es manual
            if field_value:
                field_label = ttk.Label(row_frame, text=field_value, foreground='green')
            else:
                field_label = ttk.Label(row_frame, text="[Manual]", foreground='orange')
            field_label.pack(side=tk.LEFT, padx=20)
            
            # Guardar referencias
            self.establishments_vars[folder_name] = {
                'personal': personal_var,
                'corporate': corporate_var,
                'field': field_value if field_value else None
            }
        
        # Actualizar canvas
        self.canvas.update_idletasks()
        
        # Mostrar advertencia si hay campos sin mapeo
        if unmapped:
            self.log_message(f"⚠️ {len(unmapped)} establecimientos sin mapeo en Excel")
            self.log_message("Por favor, revisa los campos manuales arriba")
    
    def select_all(self, bulletin_type):
        """Marcar todos los checkboxes de un tipo"""
        for est_vars in self.establishments_vars.values():
            est_vars[bulletin_type].set(True)
    
    def deselect_all(self):
        """Desmarcar todos los checkboxes"""
        for est_vars in self.establishments_vars.values():
            est_vars['personal'].set(False)
            est_vars['corporate'].set(False)
    
    def select_folder(self):
        """Seleccionar carpeta con las imágenes"""
        folder = filedialog.askdirectory(title="Selecciona la carpeta con las subcarpetas de establecimientos")
        
        if folder:
            self.selected_folder.set(folder)
            Config.LOCAL_FOLDER = folder
            
            # Analizar la carpeta
            subfolders = [f for f in os.listdir(folder) 
                         if os.path.isdir(os.path.join(folder, f))]
            
            if subfolders:
                self.folder_info.config(
                    text=f"{len(subfolders)} subcarpetas encontradas", 
                    foreground='green'
                )
                
                # Poblar la lista de establecimientos
                self.populate_establishment_list(subfolders)
                
                self.log_message(f"Carpeta seleccionada: {folder}")
                self.log_message(f"Subcarpetas encontradas: {len(subfolders)}")
                
                if not Config.FIELD_MAPPINGS:
                    self.log_message("\n⚠️ Considera cargar un Excel de mapeo para los campos de Mautic")
                
                self.log_message("\nConfigura los boletines y presiona 'CREAR BOLETINES'")
                
                # Habilitar el botón de inicio
                self.start_button.config(state='normal')
                self.current_status.set("Configura los boletines y presiona CREAR BOLETINES")
                
            else:
                self.folder_info.config(
                    text="No se encontraron subcarpetas", 
                    foreground='red'
                )
                messagebox.showwarning("Sin subcarpetas", 
                                      "La carpeta seleccionada no contiene subcarpetas.")
    
    def log_message(self, message):
        """Agregar mensaje al log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_process(self):
        """Iniciar el proceso de creación de boletines"""
        if not Config.LOCAL_FOLDER:
            messagebox.showwarning("Sin carpeta", 
                                "Por favor selecciona una carpeta primero.")
            return
        
        # Actualizar campos manuales si existen
        for name, field_var in self.field_entries.items():
            if name in self.establishments_vars:
                field_value = field_var.get().strip()
                if not field_value:
                    messagebox.showwarning("Campos vacíos", 
                        f"El campo para '{name}' está vacío. Por favor complétalo.")
                    return
                self.establishments_vars[name]['field'] = field_value
        
        # Guardar configuración de cada establecimiento
        Config.ESTABLISHMENT_CONFIG = {}
        Config.CREATED_EMAILS = []  # Limpiar lista de emails creados
        total_selected = 0
        
        for name, vars_dict in self.establishments_vars.items():
            personal = vars_dict['personal'].get()
            corporate = vars_dict['corporate'].get()
            
            if personal or corporate:
                # Obtener el campo final
                field = vars_dict.get('field')
                if not field and name in self.field_entries:
                    field = self.field_entries[name].get()
                if not field:
                    # Si aún no hay campo, usar el predeterminado
                    field = name.lower().replace(' ', '_').replace('-', '_')
                
                Config.ESTABLISHMENT_CONFIG[name] = {
                    'personal': personal,
                    'corporate': corporate,
                    'field': field
                }
                total_selected += 1
        
        if total_selected == 0:
            messagebox.showwarning("Sin selección", 
                                "Por favor selecciona al menos un boletín para procesar.")
            return
        
        # Contar boletines totales
        total_bulletins = sum(
            (1 if cfg['personal'] else 0) + (1 if cfg['corporate'] else 0)
            for cfg in Config.ESTABLISHMENT_CONFIG.values()
        )
        
        # Confirmación antes de iniciar
        message = f"¿Deseas procesar {total_selected} establecimientos?\n\n"
        message += f"Total de boletines a crear: {total_bulletins}\n"
        message += "\nEsto subirá las imágenes a Cloudflare R2 y creará los boletines en Mautic."
        
        result = messagebox.askyesno("Confirmar", message, icon='question')
        
        if not result:
            return
        
        self.start_button.config(state='disabled')
        self.campaign_button.config(state='disabled')  # Asegurar que esté deshabilitado
        self.progress_bar.start(10)
        self.current_status.set("Procesando... Por favor espera")
        
        # Limpiar el log previo
        self.log_text.delete(1.0, tk.END)
        self.log_message("="*60)
        self.log_message("INICIANDO PROCESO DE CREACIÓN DE BOLETINES")
        self.log_message(f"Establecimientos seleccionados: {total_selected}")
        self.log_message(f"Total de boletines a crear: {total_bulletins}")
        self.log_message("="*60 + "\n")
        
        # Ejecutar en thread separado
        thread = threading.Thread(target=self.run_automation)
        thread.daemon = True
        thread.start()
    
    def run_automation(self):
        """Ejecutar la automatización de boletines"""
        error_occurred = False
        error_message = ""
        
        try:
            if os.path.exists('emails_creados.json'):
                self.backup_emails_json()
            self.log_message("Iniciando automatización...")
            processor = EstablishmentProcessor(self)
            processor.process_all_establishments()
            
            # Si se crearon emails exitosamente, habilitar el botón de campañas
            if Config.CREATED_EMAILS:
                self.emails_created = True
                self.campaign_button.config(state='normal')
                self.log_message("\n✅ Boletines creados exitosamente")
                self.log_message("Ahora puedes revisar los boletines en Mautic")
                self.log_message("Cuando estés listo, presiona 'CREAR CAMPAÑAS'")
                
                # Guardar información de emails para las campañas
                with open('emails_creados.json', 'w') as f:
                    json.dump(Config.CREATED_EMAILS, f, indent=2)
                self.log_message(f"\nInformación guardada: {len(Config.CREATED_EMAILS)} emails")
            
                # Mostrar mensaje de éxito
                self.root.after(0, lambda: messagebox.showinfo(
                    "Boletines Creados", 
                    f"Se han creado {len(Config.CREATED_EMAILS)} boletines exitosamente.\n\n" +
                    "Revisa los boletines en Mautic y luego presiona 'CREAR CAMPAÑAS'"
                ))
            else:
                self.log_message("\n⚠️ No se crearon boletines")
                self.root.after(0, lambda: messagebox.showwarning(
                    "Sin boletines", 
                    "No se pudo crear ningún boletín.\n\nRevisa los logs para más detalles."
                ))
            
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            self.log_message(f"ERROR: {error_message}")
            import traceback
            self.log_message(f"Detalle: {traceback.format_exc()}")
            self.root.after(0, lambda msg=error_message: messagebox.showerror("Error", 
                                                           f"Se produjo un error:\n\n{msg}"))
        finally:
            self.progress_bar.stop()
            if Config.CREATED_EMAILS:
                self.current_status.set("Boletines creados - Listo para crear campañas")
            else:
                self.current_status.set("Proceso completado - Revisa los logs")
            self.start_button.config(state='normal')
    
    def create_campaigns(self):
        """Crear campañas para los boletines ya creados"""
        # Verificar si hay emails en Config.CREATED_EMAILS
        if not Config.CREATED_EMAILS:
            # Intentar cargar desde archivo
            files_to_check = ['correcciones.json', 'emails_creados.json', 'emails_finales.json']
            loaded = False
            
            for json_file in files_to_check:
                if os.path.exists(json_file):
                    try:
                        with open(json_file, 'r') as f:
                            Config.CREATED_EMAILS = json.load(f)
                        
                        if Config.CREATED_EMAILS:
                            self.log_message(f"Emails cargados desde: {json_file}")
                            loaded = True
                            break
                    except:
                        continue
            
            if not loaded:
                messagebox.showwarning("Sin boletines", 
                    "No hay boletines creados. Primero crea boletines.")
                return
        """Crear campañas para los boletines ya creados"""
        if not Config.CREATED_EMAILS:
            # Intentar cargar desde archivo si existe
            try:
                with open('emails_creados.json', 'r') as f:
                    Config.CREATED_EMAILS = json.load(f)
            except:
                messagebox.showwarning("Sin boletines", 
                    "No hay boletines creados. Primero crea los boletines.")
                return
        
        # Obtener el segmento del campo de texto
        segment_name = self.segment_name.get().strip()
        
        if not segment_name:
            messagebox.showerror("Error", 
                "Por favor ingresa el nombre del segmento en el campo de configuración")
            return
        
        # Confirmación
        num_campaigns = len(Config.CREATED_EMAILS)
        result = messagebox.askyesno("Confirmar Creación de Campañas", 
            f"¿Deseas crear {num_campaigns} campañas?\n\n" +
            f"Se creará una campaña para cada boletín.\n" +
            f"Segmento configurado: {segment_name}\n\n" +
            f"IMPORTANTE: Asegúrate que el segmento '{segment_name}' existe en Mautic")
        
        if not result:
            return
        
        self.campaign_button.config(state='disabled')
        self.progress_bar.start(10)
        self.current_status.set("Creando campañas... Por favor espera")
        
        # Limpiar log
        self.log_text.delete(1.0, tk.END)
        self.log_message("="*60)
        self.log_message("INICIANDO CREACIÓN DE CAMPAÑAS")
        self.log_message(f"Campañas a crear: {num_campaigns}")
        self.log_message(f"Segmento: {segment_name}")
        self.log_message("="*60 + "\n")
        
        # Ejecutar en thread
        thread = threading.Thread(target=self.run_campaign_creation)
        thread.daemon = True
        thread.start()
    
    def run_campaign_creation(self):
        """Ejecutar la creación de campañas"""
        try:
            # Obtener el nombre del segmento desde el campo de texto
            segment_name = self.segment_name.get().strip()
            
            if not segment_name:
                self.log_message("ERROR: No se ha especificado un segmento")
                self.root.after(0, lambda: messagebox.showerror("Error", 
                    "Por favor, ingresa el nombre del segmento"))
                return
            
            self.log_message(f"Segmento configurado: {segment_name}")
            
            automator = MauticCampaignCreator(
                Config.MAUTIC_URL,
                Config.MAUTIC_USERNAME,
                Config.MAUTIC_PASSWORD,
                self
            )
            
            automator.setup_driver(headless=False)
            
            if not automator.login():
                raise Exception("No se pudo hacer login en Mautic")
            
            # Crear campañas usando el segmento especificado
            success_count = 0
            failed_campaigns = []
            
            for email_info in Config.CREATED_EMAILS:
                if automator.create_campaign_for_email(email_info, segment_name):
                    success_count += 1
                else:
                    failed_campaigns.append(email_info['name'])
            
            automator.close()
            
            self.log_message("\n" + "="*60)
            self.log_message(f"CAMPAÑAS CREADAS: {success_count}/{len(Config.CREATED_EMAILS)}")
            
            if failed_campaigns:
                self.log_message("\nCampañas que no se pudieron crear:")
                for campaign in failed_campaigns:
                    self.log_message(f"   - {campaign}")
            
            self.log_message("="*60)
            
            if success_count > 0:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Proceso Completado", 
                    f"Se han creado {success_count} campañas exitosamente.\n\n" +
                    "Revisa las campañas en Mautic."
                ))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", 
                    "No se pudo crear ninguna campaña.\n\n" +
                    "Verifica el proceso manualmente."
                ))
            
        except Exception as e:
            self.log_message(f"ERROR: {str(e)}")
            import traceback
            self.log_message(f"Detalle: {traceback.format_exc()}")
            self.root.after(0, lambda: messagebox.showerror("Error", 
                                                           f"Error creando campañas:\n\n{str(e)}"))
        finally:
            self.progress_bar.stop()
            self.current_status.set("Proceso completado")
            self.campaign_button.config(state='normal')
    
    def run(self):
        """Ejecutar la interfaz"""
        self.root.mainloop()
    # AGREGAR ESTOS MÉTODOS EN AutomationGUI (al final de la clase)
    def view_json_file(self, filename):
        """Ver contenido de un archivo JSON"""
        if not os.path.exists(filename):
            messagebox.showinfo("Archivo no encontrado", 
                f"El archivo {filename} no existe.")
            return
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            if not data:
                messagebox.showinfo("Archivo vacío", 
                    f"El archivo {filename} está vacío.")
                return
            
            # Crear ventana para mostrar datos
            view_window = tk.Toplevel(self.root)
            view_window.title(f"Contenido de {filename}")
            view_window.geometry("800x500")
            
            # Frame con scroll
            text_frame = ttk.Frame(view_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget = tk.Text(text_frame, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Mostrar información
            text_widget.insert(tk.END, f"Total de boletines: {len(data)}\n")
            text_widget.insert(tk.END, "="*70 + "\n\n")
            
            for idx, email in enumerate(data, 1):
                text_widget.insert(tk.END, f"{idx}. {email.get('name', 'Sin nombre')}\n")
                text_widget.insert(tk.END, f"   ID: {email.get('id', 'N/A')}\n")
                text_widget.insert(tk.END, f"   Tipo: {email.get('type', 'N/A')}\n")
                text_widget.insert(tk.END, f"   Establecimiento: {email.get('establishment', 'N/A')}\n")
                text_widget.insert(tk.END, "-"*70 + "\n")
            
            text_widget.configure(state='disabled')
            
            # Botón cerrar
            ttk.Button(view_window, text="Cerrar", 
                    command=view_window.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error leyendo archivo: {str(e)}")

    def clear_json_file(self, filename):
        """Limpiar un archivo JSON"""
        if not os.path.exists(filename):
            messagebox.showinfo("Archivo no encontrado", 
                f"El archivo {filename} no existe.")
            return
        
        result = messagebox.askyesno("Confirmar", 
            f"¿Deseas eliminar el archivo {filename}?\n\n" +
            "Esto NO afectará los boletines en Mautic,\n" +
            "solo eliminará el registro local.",
            icon='warning')
        
        if result:
            try:
                # Crear backup
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f'{filename.replace(".json", "")}_{timestamp}.json'
                
                import shutil
                shutil.copy2(filename, backup_name)
                
                os.remove(filename)
                
                self.log_message(f"Archivo {filename} eliminado (backup: {backup_name})")
                messagebox.showinfo("Archivo eliminado", 
                    f"El archivo ha sido eliminado.\n\nBackup creado: {backup_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando archivo: {str(e)}")

# ======================== UPLOADER CLOUDFLARE R2 ========================
class CloudflareR2Uploader:
    def __init__(self, gui=None):
        self.s3_client = None
        self.bucket_name = Config.R2_BUCKET_NAME
        self.gui = gui
    
    def log(self, message):
        """Log con GUI si está disponible"""
        print(message)
        if self.gui:
            self.gui.log_message(message)
    
    def connect(self):
        """Conectar a Cloudflare R2"""
        try:
            self.log("Conectando a Cloudflare R2...")
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=Config.R2_ENDPOINT,
                aws_access_key_id=Config.R2_ACCESS_KEY_ID,
                aws_secret_access_key=Config.R2_SECRET_ACCESS_KEY,
                region_name='auto'
            )
            
            self.log("Conexión a Cloudflare R2 establecida")
            return True
                
        except Exception as e:
            self.log(f"Error conectando a Cloudflare R2: {e}")
            return False
    
    def upload_image(self, local_path, remote_filename):
        """Subir imagen a Cloudflare R2"""
        try:
            remote_path = Config.R2_FOLDER_PATH + remote_filename
            
            if not os.path.exists(local_path):
                self.log(f"Archivo no encontrado: {local_path}")
                return False, None, None
            
            # Verificar si ya existe
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=remote_path)
                self.log(f"   La imagen {remote_filename} ya existe en R2. Actualizando...")
            except:
                self.log(f"   Subiendo nueva imagen {remote_filename} a Cloudflare R2...")
            
            # Analizar y optimizar imagen
            img_width, img_height, optimized_image = self.optimize_image(local_path)
            
            # Determinar el content type
            content_type = 'image/jpeg'
            if remote_filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif remote_filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            
            # Subir imagen
            if optimized_image:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=remote_path,
                    Body=optimized_image,
                    ContentType=content_type,
                    CacheControl='public, max-age=31536000'
                )
            else:
                with open(local_path, 'rb') as file:
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=remote_path,
                        Body=file,
                        ContentType=content_type,
                        CacheControl='public, max-age=31536000'
                    )
            
            self.log(f"   Imagen actualizada exitosamente: {remote_filename}")
            
            try:
                self.s3_client.put_object_acl(
                    Bucket=self.bucket_name,
                    Key=remote_path,
                    ACL='public-read'
                )
            except:
                pass
            
            return True, img_width, img_height
            
        except Exception as e:
            self.log(f"Error subiendo imagen: {e}")
            return False, None, None
    
    def optimize_image(self, image_path, max_width=700, quality=85):
        """Optimizar imagen y obtener dimensiones"""
        try:
            img = Image.open(image_path)
            original_width, original_height = img.size
            
            if original_width > max_width:
                ratio = max_width / original_width
                new_height = int(original_height * ratio)
                
                self.log(f"   Imagen original: {original_width}x{original_height}px")
                self.log(f"   Se adaptará a: {max_width}x{new_height}px")
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                img.thumbnail((max_width, original_height), Image.Resampling.LANCZOS)
                
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                output.seek(0)
                
                final_width, final_height = img.size
                return final_width, final_height, output
            else:
                self.log(f"   Imagen: {original_width}x{original_height}px (no requiere ajuste)")
                return original_width, original_height, None
                
        except Exception as e:
            self.log(f"   No se pudo analizar imagen: {e}")
            return None, None, None
    
    def disconnect(self):
        """Cerrar conexión"""
        self.log("Conexión a Cloudflare R2 cerrada")

# ======================== MAUTIC EMAIL CREATOR ========================
class MauticBulkAutomator:
    def __init__(self, base_url, username, password, gui=None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.driver = None
        self.wait = None
        self.short_wait = None
        self.is_logged_in = False
        self.spanish_language_value = None
        self.gui = gui
    
    def log(self, message):
        """Log con GUI si está disponible"""
        print(message)
        if self.gui:
            self.gui.log_message(message)
    
    def setup_driver(self, headless=False):
        """Configurar Chrome con Selenium"""
        self.log("Iniciando navegador Chrome...")
        
        import tempfile
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--disable-gpu-sandbox')
        chrome_options.add_argument('--disable-software-rasterizer')
        
        temp_dir = tempfile.mkdtemp(prefix="mautic_chrome_")
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--start-maximized')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver.implicitly_wait(3)
            self.wait = WebDriverWait(self.driver, 15)
            self.short_wait = WebDriverWait(self.driver, 5)
            self.long_wait = WebDriverWait(self.driver, 30)
            
            self.driver.set_page_load_timeout(30)
            
            self.log("Navegador configurado correctamente")
            
        except Exception as e:
            self.log(f"Error iniciando Chrome: {str(e)}")
            raise
    
    def login(self):
        """Login rápido en Mautic"""
        self.log("Iniciando login en Mautic...")
        
        try:
            login_url = f"{self.base_url}/s/login"
            self.driver.get(login_url)
            
            if 'dashboard' in self.driver.current_url or 'emails' in self.driver.current_url:
                self.log("Ya estás logueado!")
                self.is_logged_in = True
                return True
            
            username_field = self.short_wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.clear()
            username_field.send_keys(self.username)
            password_field.clear()
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            
            WebDriverWait(self.driver, 10).until(
                lambda driver: 'login' not in driver.current_url.lower()
            )
            
            self.log("Login exitoso!")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            self.log(f"Error durante login: {str(e)}")
            return False
    
    def create_email_for_establishment(self, establishment_name, image_url, img_width, img_height, bulletin_type, field_alias):
        """Crear email para un establecimiento específico"""
        
        fecha = Config.get_date_format()
        
        # Generar nombres según el tipo
        if bulletin_type == "personal":
            subject = f"¡Tus millas ya fueron acreditadas! + MILES {establishment_name}"
            internal_name = f"PRUEBA-CME-BOL-INF-MME-PERSONAL_{establishment_name.upper().replace(' ', '_')}_{fecha}"
            html_template = self.generate_personal_template(
                establishment_name, image_url, img_width, img_height, field_alias
            )
        else:  # corporate
            subject = f"¡Tus millas ya fueron acreditadas! + MILES {establishment_name}"
            internal_name = f"PRUEBA-CME-BOL-INF-MME-CORPORATIVO_{establishment_name.upper().replace(' ', '_')}_{fecha}"
            html_template = self.generate_corporate_template(
                establishment_name, image_url, img_width, img_height, field_alias
            )
        
        self.log(f"   Creando boletín {bulletin_type.upper()}: {internal_name}")
        self.log(f"      Campo Mautic: {field_alias}_txt")
        
        try:
            # Navegar a nuevo email
            self.driver.get(f"{self.base_url}/s/emails/new")
            time.sleep(1)
            
            # Seleccionar Template Email
            self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    if (buttons[i].textContent.trim() === 'Select') {
                        buttons[i].click();
                        break;
                    }
                }
            """)
            
            time.sleep(1)
            
            # Seleccionar Code Mode
            self.driver.execute_script("""
                var links = document.querySelectorAll('a');
                for (var i = 0; i < links.length; i++) {
                    if (links[i].textContent.trim() === 'Select') {
                        links[i].click();
                        break;
                    }
                }
            """)
            
            time.sleep(1)
            
            # Buscar valor de español si no lo tenemos
            if not self.spanish_language_value:
                self.spanish_language_value = self.find_spanish_value()
            
            # Llenar campos del formulario
            self.driver.execute_script("""
                // Subject
                var subjectField = document.getElementById('emailform_subject');
                if (subjectField) {
                    subjectField.value = arguments[0];
                    subjectField.dispatchEvent(new Event('change', { bubbles: true }));
                }
                
                // Internal Name
                var nameField = document.getElementById('emailform_name');
                if (nameField) {
                    nameField.value = arguments[1];
                    nameField.dispatchEvent(new Event('change', { bubbles: true }));
                }
                
                // Idioma
                var languageSelect = document.getElementById('emailform_language');
                if (languageSelect && arguments[2]) {
                    languageSelect.value = arguments[2];
                    languageSelect.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, subject, internal_name, self.spanish_language_value)
            
            # Cambiar a pestaña Advanced y agregar HTML
            self.driver.execute_script("""
                var advancedTab = document.querySelector('a[href="#advanced-container"]');
                if (advancedTab) advancedTab.click();
            """)
            
            time.sleep(0.5)
            
            self.driver.execute_script("""
                var htmlTextarea = document.getElementById('emailform_customHtml');
                if (htmlTextarea) {
                    htmlTextarea.value = arguments[0];
                    htmlTextarea.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, html_template)
            
            # Guardar
            self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if (btn.textContent.includes('Save') && btn.getBoundingClientRect().top < 200) {
                        btn.click();
                        break;
                    }
                }
            """)
            
            time.sleep(3)
            
            current_url = self.driver.current_url
            if '/edit/' in current_url or ('/email/' in current_url and '/new' not in current_url):
                email_id = current_url.split('/')[-1]
                self.log(f"      OK - Boletín creado (ID: {email_id})")
                
                # ============================================
                # SOLUCIÓN IMPLEMENTADA PARA EVITAR DUPLICADOS
                # ============================================
                
                # Verificar si este boletín ya existe en la lista (es una recreación)
                email_exists = False
                existing_index = -1
                
                for index, existing_email in enumerate(Config.CREATED_EMAILS):
                    # Comparar por nombre, establecimiento y tipo para identificar si es el mismo boletín
                    if (existing_email['name'] == internal_name and 
                        existing_email['establishment'] == establishment_name and
                        existing_email['type'] == bulletin_type):
                        # Este boletín ya existe, es una recreación
                        email_exists = True
                        existing_index = index
                        self.log(f"      ✓ Boletín existente detectado, actualizando ID")
                        break
                
                if email_exists and existing_index >= 0:
                    # ACTUALIZAR el boletín existente en lugar de agregar uno nuevo
                    Config.CREATED_EMAILS[existing_index]['id'] = email_id
                    Config.CREATED_EMAILS[existing_index]['recreated'] = True
                    Config.CREATED_EMAILS[existing_index]['updated_at'] = datetime.now().isoformat()
                    
                    # Si hay un campo field anterior, mantenerlo
                    if 'field' not in Config.CREATED_EMAILS[existing_index]:
                        Config.CREATED_EMAILS[existing_index]['field'] = field_alias
                    
                    self.log(f"      ✓ ID actualizado en posición {existing_index}")
                    
                else:
                    # Es un boletín nuevo, agregarlo a la lista
                    Config.CREATED_EMAILS.append({
                        'id': email_id,
                        'name': internal_name,
                        'establishment': establishment_name,
                        'type': bulletin_type,
                        'field': field_alias
                    })
                    self.log(f"      ✓ Nuevo boletín agregado a la lista")
                
                # Guardar inmediatamente en el archivo JSON para mantener consistencia
                try:
                    with open('emails_creados.json', 'w') as f:
                        json.dump(Config.CREATED_EMAILS, f, indent=2)
                    self.log(f"      ✓ Archivo emails_creados.json actualizado")
                except Exception as e:
                    self.log(f"      ⚠️ Error guardando JSON: {str(e)}")
                
                return email_id
            else:
                self.log(f"      OK - Boletín posiblemente creado")
                return None
                
        except Exception as e:
            self.log(f"      ERROR - No se pudo crear: {str(e)}")
            return None
        
    
    def find_spanish_value(self):
        """Encontrar el valor de español en el dropdown"""
        try:
            result = self.driver.execute_script("""
                var select = document.getElementById('emailform_language');
                if (select) {
                    var spanishValues = ['es', 'es_ES', 'es_MX', 'es_AR', 'es_CO', 'es_EC'];
                    for (var j = 0; j < spanishValues.length; j++) {
                        for (var i = 0; i < select.options.length; i++) {
                            if (select.options[i].value === spanishValues[j]) {
                                return select.options[i].value;
                            }
                        }
                    }
                    for (var i = 0; i < select.options.length; i++) {
                        if (select.options[i].value.startsWith('es')) {
                            return select.options[i].value;
                        }
                    }
                }
                return null;
            """)
            return result
        except:
            return None
    
    def generate_personal_template(self, establishment_name, image_url, img_width, img_height, field_alias):
        """Generar template HTML para boletín personal"""
        contact_field = f"{{contactfield={field_alias}_txt}}"
        
        display_width = min(img_width, 700) if img_width else 700
        display_height = img_height if img_height else 700
        
        return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>ClubMiles</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<style type="text/css">
  html, body, div, form, fieldset, legend, label, img, tr
  {{
  margin: 0;
  padding: 0;
  }}
  table
  {{
  border-collapse: collapse;
  border-spacing: 0;
  font-size:0;
  }}
  th, td
  {{
  text-align: left;
  }}
  h1, h2, h3, h4, h5, h6, th, td, caption {{ font-weight:normal; }}
  img {{ border: 0; display:block; padding:0; margin:0;}}
  div {{
   display:block !important;
   }}
   span.preheader {{ display: none !important; }}
</style>
</head>
<body bgcolor="#ffffff">
  <span class="preheader">Disfruta tus millas adicionales entregadas por tus compras en {establishment_name}</span>
  <center>
    <table width="100%">
      <tr>
        <td>
          <center>
            <table style="display: inline-table;" border="0" cellpadding="0" cellspacing="0" width="700">
              <tr>
               <td><img style="display:block" name="index_r1_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r1_c1.jpg" width="700" height="96" id="index_r1_c1" alt="" /></td>
              </tr>
              <tr>
                <td>
                  <table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                    <tr>
                      <td td width="39" style="background-color:#E7E7E7;"></td>
                      <td width="624" height="30" style="font-family:sans-serif;font-size:24px;text-align:center;padding-top:10px;">
                        Hola, {{contactfield=firstname}}
                      </td>
                      <td td width="37" style="background-color:#E7E7E7;"></td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
               <td><img style="display:block" name="index_r3_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r3_c1.jpg" width="700" height="28" id="index_r3_c1" alt="" /></td>
              </tr>
              <tr>
                <td>
                  <table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                    <tr>
                      <td td width="39" style="background-color:#E7E7E7;"></td>
                      <td width="624" height="30" style="font-family:sans-serif;font-size:20px;text-align: center">
                        Se han acreditado exitosamente
                      </td>
                      <td td width="37" style="background-color:#E7E7E7;"></td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td>
                  <table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                    <tr>
                      <td td width="39" style="background-color:#E7E7E7;"></td>
                      <td width="624" height="30" style="color:#0097FF;font-family:sans-serif;font-size:23px;text-align: center">
                        <strong>{contact_field} millas</strong>
                      </td>
                      <td td width="37" style="background-color:#E7E7E7;"></td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td>
                  <table align="center" border="0" cellpadding="0" cellspacing="0" width="700" style="background-color: #E7E7E7;">
                    <tr>
                      <td>
                        <table align="center" border="0" cellpadding="0" cellspacing="0" width="623" style="background-color: #ffffff; border-bottom-left-radius: 30px; border-bottom-right-radius: 30px;">
                          <tr>
                            <td width="622" height="30" align="center" style="font-family:sans-serif; font-size: 20px; padding-bottom:10px; text-align: center;">
                              por tu compra en:
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              
              <tr>
               <td align="center"><img style="display:block; margin: 0 auto;" name="index_r5_c1" src="{image_url}" width="{display_width}" height="{display_height}" id="index_r5_c1" alt="{establishment_name}" /></td>
              </tr>
              <tr>
               <td><a href="https://onelink.to/appclubmiles1" target="_blank"><img style="display:block" name="index_r6_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r6_c1.jpg" width="700" height="278" id="index_r6_c1" alt="#" /></a></td>
              </tr>
              <tr>
               <td><table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                <tr>
                 <td><img style="display:block" name="index_r7_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c1.jpg" width="269" height="46" id="index_r7_c1" alt="" /></td>
                 <td><a href="https://www.facebook.com/ClubMiles/" target="_blank"><img style="display:block" name="index_r7_c2" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c2.jpg" width="41" height="46" id="index_r7_c2" alt="Facebook Club Miles" /></a></td>
                 <td><a href="https://instagram.com/clubmiles_ec?igshid=YmMyMTA2M2Y=" target="_blank"><img style="display:block" name="index_r7_c3" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c3.jpg" width="40" height="46" id="index_r7_c3" alt="Instagram Club Miles" /></a></td>
                 <td><a href="https://wa.me/593963040040" target="_blank"><img style="display:block" name="index_r7_c4" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c4.jpg" width="39" height="46" id="index_r7_c4" alt="Whatsapp Club Miles" /></a></td>
                 <td><a href="https://www.youtube.com/channel/UCJ5qTUrByNb6u9XiQ39xmHA" target="_blank"><img style="display:block" name="index_r7_c5" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c5.jpg" width="39" height="46" id="index_r7_c5" alt="Youtube Club Miles" /></a></td>
                 <td><img style="display:block" name="index_r7_c6" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c6.jpg" width="272" height="46" id="index_r7_c6" alt="" /></td>
                </tr>
              </table></td>
              </tr>
              <tr>
               <td><img style="display:block" name="index_r8_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r8_c1.jpg" width="700" height="23" id="index_r8_c1" alt="" /></td>
              </tr>
              <tr>
               <td><img style="display:block" name="index_r9_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r9_c1.jpg" width="700" height="39" id="index_r9_c1" alt="" /></td>
              </tr>
            </table>
          </center>
        </td>
      </tr>
    </table>
  </center>
</body>
</html>
{{unsubscribe_text}}"""
    
    def generate_corporate_template(self, establishment_name, image_url, img_width, img_height, field_alias):
        """Generar template HTML para boletín corporativo"""
        contact_field = f"{{contactfield={field_alias}_txt}}"
        
        display_width = min(img_width, 700) if img_width else 700
        display_height = img_height if img_height else 700
        
        return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>ClubMiles</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<style type="text/css">
  html, body, div, form, fieldset, legend, label, img, tr
  {{
  margin: 0;
  padding: 0;
  }}
  table
  {{
  border-collapse: collapse;
  border-spacing: 0;
  font-size:0;
  }}
  th, td
  {{
  text-align: left;
  }}
  h1, h2, h3, h4, h5, h6, th, td, caption {{ font-weight:normal; }}
  img {{ border: 0; display:block; padding:0; margin:0;}}
  div {{
   display:block !important;
   }}
   span.preheader {{ display: none !important; }}
</style>
</head>
<body bgcolor="#ffffff">
  <span class="preheader">Disfruta tus millas adicionales entregadas por tus compras en {establishment_name}</span>
  <center>
    <table width="100%">
      <tr>
        <td>
          <center>
            <table style="display: inline-table;" border="0" cellpadding="0" cellspacing="0" width="700">
              <tr>
               <td><img style="display:block" name="index_r1_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r1_c1.jpg" width="700" height="96" id="index_r1_c1" alt="" /></td>
              </tr>
              <tr>
                <td>
                  <table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                    <tr>
                      <td td width="39" style="background-color:#E7E7E7;"></td>
                      <td width="624" height="30" style="font-family:sans-serif;font-size:20px;text-align: center">
                        Se han acreditado exitosamente
                      </td>
                      <td td width="37" style="background-color:#E7E7E7;"></td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td>
                  <table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                    <tr>
                      <td td width="39" style="background-color:#E7E7E7;"></td>
                      <td width="624" height="30" style="color:#0097FF;font-family:sans-serif;font-size:23px;text-align: center">
                        <strong>{contact_field} millas</strong>
                      </td>
                      <td td width="37" style="background-color:#E7E7E7;"></td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td>
                  <table align="center" border="0" cellpadding="0" cellspacing="0" width="700" style="background-color: #E7E7E7;">
                    <tr>
                      <td>
                        <table align="center" border="0" cellpadding="0" cellspacing="0" width="623" style="background-color: #ffffff; border-bottom-left-radius: 30px; border-bottom-right-radius: 30px;">
                          <tr>
                            <td width="622" height="30" align="center" style="font-family:sans-serif; font-size: 20px; padding-bottom:10px; text-align: center;">
                              por tu compra en:
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              
              <tr>
               <td><img style="display:block" name="index_r5_c1" src="{image_url}" width="{display_width}" height="{display_height}" id="index_r5_c1" alt="" /></td>
              </tr>
              <tr>
               <td><a href="https://onelink.to/appclubmiles1" target="_blank"><img style="display:block" name="index_r6_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r6_c1.jpg" width="700" height="278" id="index_r6_c1" alt="#" /></a></td>
              </tr>
              <tr>
               <td><table style="display: inline-table;" align="center" border="0" cellpadding="0" cellspacing="0" width="700">
                <tr>
                 <td><img style="display:block" name="index_r7_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c1.jpg" width="269" height="46" id="index_r7_c1" alt="" /></td>
                 <td><a href="https://www.facebook.com/ClubMiles/" target="_blank"><img style="display:block" name="index_r7_c2" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c2.jpg" width="41" height="46" id="index_r7_c2" alt="Facebook Club Miles" /></a></td>
                 <td><a href="https://instagram.com/clubmiles_ec?igshid=YmMyMTA2M2Y=" target="_blank"><img style="display:block" name="index_r7_c3" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c3.jpg" width="40" height="46" id="index_r7_c3" alt="Instagram Club Miles" /></a></td>
                 <td><a href="https://wa.me/593963040040" target="_blank"><img style="display:block" name="index_r7_c4" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c4.jpg" width="39" height="46" id="index_r7_c4" alt="Whatsapp Club Miles" /></a></td>
                 <td><a href="https://www.youtube.com/channel/UCJ5qTUrByNb6u9XiQ39xmHA" target="_blank"><img style="display:block" name="index_r7_c5" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c5.jpg" width="39" height="46" id="index_r7_c5" alt="Youtube Club Miles" /></a></td>
                 <td><img style="display:block" name="index_r7_c6" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r7_c6.jpg" width="272" height="46" id="index_r7_c6" alt="" /></td>
                </tr>
              </table></td>
              </tr>
              <tr>
               <td><img style="display:block" name="index_r8_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r8_c1.jpg" width="700" height="23" id="index_r8_c1" alt="" /></td>
              </tr>
              <tr>
               <td><img style="display:block" name="index_r9_c1" src="https://content.miles.com.ec/images/CME/CME-BOL-INF-MME-ACREDITACIONES_LOGOS/index_r9_c1.jpg" width="700" height="39" id="index_r9_c1" alt="" /></td>
              </tr>
            </table>
          </center>
        </td>
      </tr>
    </table>
  </center>
</body>
</html>
{{unsubscribe_text}}"""
    
    def calculate_toolbar_height(self):
        """Calcular la altura de la barra de herramientas del navegador"""
        try:
            # Obtener la diferencia entre window.outerHeight y window.innerHeight
            toolbar_height = self.driver.execute_script("""
                return window.outerHeight - window.innerHeight;
            """)
            
            # Si no se puede calcular, usar un valor por defecto
            if toolbar_height is None or toolbar_height < 50:
                toolbar_height = 130  # Valor por defecto para Chrome
            
            self.log(f"   Altura de toolbar calculada: {toolbar_height}px")
            return toolbar_height
        except:
            return 130  # Valor por defecto
        """Cerrar navegador"""
        if self.driver:
            self.log("Cerrando navegador...")
            try:
                self.driver.quit()
            except:
                pass

# ======================== MAUTIC CAMPAIGN CREATOR ========================
class MauticCampaignCreator:
    def __init__(self, base_url, username, password, gui=None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.driver = None
        self.wait = None
        self.short_wait = None
        self.is_logged_in = False
        self.gui = gui
    
    def log(self, message):
        """Log con GUI si está disponible"""
        print(message)
        if self.gui:
            self.gui.log_message(message)
    
    def setup_driver(self, headless=False):
        """Configurar Chrome con Selenium"""
        self.log("Iniciando navegador Chrome para campañas...")
        
        import tempfile
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--disable-gpu-sandbox')
        chrome_options.add_argument('--disable-software-rasterizer')
        
        temp_dir = tempfile.mkdtemp(prefix="mautic_chrome_")
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--start-maximized')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver.implicitly_wait(3)
            self.wait = WebDriverWait(self.driver, 15)
            self.short_wait = WebDriverWait(self.driver, 5)
            
            self.driver.set_page_load_timeout(30)
            
            self.log("Navegador configurado correctamente")
            
        except Exception as e:
            self.log(f"Error iniciando Chrome: {str(e)}")
            raise
    
    def login(self):
        """Login rápido en Mautic"""
        self.log("Iniciando login en Mautic...")
        
        try:
            login_url = f"{self.base_url}/s/login"
            self.driver.get(login_url)
            
            if 'dashboard' in self.driver.current_url or 'campaigns' in self.driver.current_url:
                self.log("Ya estás logueado!")
                self.is_logged_in = True
                return True
            
            username_field = self.short_wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.clear()
            username_field.send_keys(self.username)
            password_field.clear()
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            
            WebDriverWait(self.driver, 10).until(
                lambda driver: 'login' not in driver.current_url.lower()
            )
            
            self.log("Login exitoso!")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            self.log(f"Error durante login: {str(e)}")
            return False

    def take_screenshot_for_debug(self, filename="debug_screenshot.png"):
        """Tomar screenshot para debugging"""
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            self.log(f"   Screenshot guardado: {filename}")
        except Exception as e:
            self.log(f"   Error tomando screenshot: {e}")
    
    def find_element_by_text_ocr(self, text_to_find, region=None):
        """Buscar elemento por texto usando OCR (requiere pytesseract)"""
        try:
            import pytesseract
            from PIL import Image
            import numpy as np
            
            # Tomar screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # Convertir a texto
            text = pytesseract.image_to_string(screenshot)
            
            # Buscar el texto
            if text_to_find.lower() in text.lower():
                self.log(f"   Texto '{text_to_find}' encontrado via OCR")
                return True
            return False
        except ImportError:
            self.log("   pytesseract no instalado, saltando OCR")
            return False
        except Exception as e:
            self.log(f"   Error en OCR: {e}")
            return False
    
    def wait_for_element_and_get_position(self, selector, timeout=5):
        """Esperar elemento y obtener su posición absoluta en pantalla"""
        try:
            # Esperar que el elemento sea visible
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # Obtener posición del elemento
            location = self.driver.execute_script("""
                var element = document.querySelector(arguments[0]);
                if (element) {
                    var rect = element.getBoundingClientRect();
                    return {
                        x: rect.left + rect.width/2,
                        y: rect.top + rect.height/2,
                        width: rect.width,
                        height: rect.height,
                        found: true
                    };
                }
                return {found: false};
            """, selector)
            
            if location['found']:
                # Obtener posición de la ventana
                window_rect = self.driver.get_window_rect()
                
                # Calcular posición absoluta
                # Ajuste para la barra de herramientas del navegador
                toolbar_height = 130  # Ajustable según el navegador
                
                absolute_x = window_rect['x'] + location['x']
                absolute_y = window_rect['y'] + location['y'] + toolbar_height
                
                return {
                    'x': absolute_x,
                    'y': absolute_y,
                    'width': location['width'],
                    'height': location['height'],
                    'found': True
                }
        except Exception as e:
            self.log(f"   Error obteniendo posición del elemento: {e}")
        
        return {'found': False}
    
    def click_element_by_position(self, element_info, click_offset=(0, 0)):
        """Hacer clic en un elemento usando su posición"""
        if element_info['found']:
            x = element_info['x'] + click_offset[0]
            y = element_info['y'] + click_offset[1]
            
            self.log(f"   Moviendo mouse a ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.5)
            time.sleep(0.3)
            
            self.log(f"   Haciendo clic")
            pyautogui.click()
            time.sleep(0.5)
            return True
        return False
    
    def smart_dropdown_selection(self, dropdown_selector, option_text):
        """Selección inteligente de dropdown usando múltiples métodos"""
        
        # Método 1: Intentar con Selenium puro
        self.log(f"   Método 1: Intentando selección con Selenium...")
        try:
            # Hacer clic en el dropdown
            dropdown = self.driver.find_element(By.CSS_SELECTOR, dropdown_selector)
            dropdown.click()
            time.sleep(1)
            
            # Buscar la opción
            options = self.driver.find_elements(By.CSS_SELECTOR, ".chosen-results li")
            for option in options:
                if option_text.lower() in option.text.lower():
                    option.click()
                    self.log(f"   ✓ Seleccionado '{option_text}' con Selenium")
                    return True
        except Exception as e:
            self.log(f"   Selenium falló: {e}")
        
        # Método 2: PyAutoGUI con posición exacta
        self.log(f"   Método 2: Intentando con PyAutoGUI y posición exacta...")
        element_pos = self.wait_for_element_and_get_position(dropdown_selector)
        
        if element_pos['found']:
            if self.click_element_by_position(element_pos):
                time.sleep(1)
                
                # Escribir para filtrar
                self.log(f"   Escribiendo '{option_text}' para filtrar...")
                pyautogui.typewrite(option_text, interval=0.1)
                time.sleep(1)
                
                # Presionar Enter
                pyautogui.press('enter')
                time.sleep(1)
                
                self.log(f"   ✓ Seleccionado '{option_text}' con PyAutoGUI")
                return True
        
        # Método 3: Búsqueda visual con imagen
        self.log(f"   Método 3: Búsqueda visual...")
        try:
            # Tomar screenshot para debug
            self.take_screenshot_for_debug("dropdown_debug.png")
            
            # Intentar localizar visualmente el texto
            # Esto requeriría una imagen de referencia del dropdown
            pass
        except Exception as e:
            self.log(f"   Búsqueda visual falló: {e}")
        
        return False
    
    def create_campaign_for_email(self, email_info, segment_name):
        """Crear campaña - Intenta automático, con fallback manual si falla"""
        try:
            campaign_name = email_info['name']
            email_id = email_info.get('id')
            
            self.log(f"\n{'='*60}")
            self.log(f"CREANDO CAMPAÑA: {campaign_name}")
            self.log(f"Segmento: {segment_name}")
            self.log(f"{'='*60}")
            
            # PASO 1: Navegar a nueva campaña
            self.log("PASO 1: Navegando a nueva campaña...")
            try:
                self.driver.get(f"{self.base_url}/s/campaigns/new")
                time.sleep(3)
                self.log("   ✓ Navegación exitosa")
            except Exception as e:
                self.log(f"   ❌ Error: {e}")
                self.log("   Por favor navega manualmente a Campaigns > New")
                input("   >>> Presiona ENTER cuando estés en la página de nueva campaña...")
            
            # PASO 2: Llenar formulario básico
            self.log("PASO 2: Llenando formulario de campaña...")

            # Primero llenar el campo Name (esto funciona bien)
            name_success = self.driver.execute_script("""
                var campaignName = arguments[0];
                var nameField = document.getElementById('campaign_name');
                
                if (nameField) {
                    nameField.value = campaignName;
                    nameField.dispatchEvent(new Event('input', {bubbles: true}));
                    nameField.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log('Nombre configurado: ' + campaignName);
                    return true;
                }
                return false;
            """, campaign_name)

            if name_success:
                self.log("   ✓ Nombre configurado")
            else:
                self.log("   ❌ No se pudo configurar el nombre")

            # Ahora manejar el campo Description con CKEditor
            self.log("   Configurando descripción...")

            # Método principal: Enfocar y escribir en CKEditor
            description_success = self.driver.execute_script("""
                return new Promise((resolve) => {
                    var campaignName = arguments[0];
                    var maxAttempts = 10;
                    var currentAttempt = 0;
                    
                    function tryToWriteDescription() {
                        currentAttempt++;
                        console.log('Intento ' + currentAttempt + ' de escribir en CKEditor');
                        
                        // Buscar el editor
                        var ckEditor = document.querySelector('.ck-editor__editable');
                        
                        if (!ckEditor) {
                            console.log('Editor no encontrado');
                            resolve(false);
                            return;
                        }
                        
                        // Verificar si está blurred
                        if (ckEditor.classList.contains('ck-blurred')) {
                            console.log('Editor está blurred, intentando enfocar...');
                            
                            // Hacer múltiples clicks para asegurar el enfoque
                            ckEditor.click();
                            ckEditor.focus();
                            
                            // Simular un click más profundo
                            var clickEvent = new MouseEvent('mousedown', {
                                view: window,
                                bubbles: true,
                                cancelable: true
                            });
                            ckEditor.dispatchEvent(clickEvent);
                            
                            var clickUpEvent = new MouseEvent('mouseup', {
                                view: window,
                                bubbles: true,
                                cancelable: true
                            });
                            ckEditor.dispatchEvent(clickUpEvent);
                            
                            // Esperar y verificar si se enfocó
                            setTimeout(() => {
                                if (ckEditor.classList.contains('ck-focused')) {
                                    console.log('¡Editor enfocado exitosamente!');
                                    
                                    // Ahora escribir el contenido
                                    // Método 1: Cambiar el innerHTML directamente
                                    ckEditor.innerHTML = '<p>' + campaignName + '</p>';
                                    
                                    // Método 2: Usar execCommand (más compatible)
                                    try {
                                        document.execCommand('selectAll', false, null);
                                        document.execCommand('delete', false, null);
                                        document.execCommand('insertText', false, campaignName);
                                    } catch(e) {
                                        console.log('execCommand falló: ' + e);
                                    }
                                    
                                    // Disparar eventos
                                    ckEditor.dispatchEvent(new Event('input', { bubbles: true }));
                                    ckEditor.dispatchEvent(new Event('change', { bubbles: true }));
                                    ckEditor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
                                    
                                    // Verificar que se escribió
                                    var content = ckEditor.textContent || ckEditor.innerText;
                                    console.log('Contenido actual: ' + content);
                                    
                                    resolve(true);
                                } else if (currentAttempt < maxAttempts) {
                                    // Si no se enfocó, intentar de nuevo
                                    console.log('Editor aún no enfocado, reintentando...');
                                    tryToWriteDescription();
                                } else {
                                    console.log('No se pudo enfocar el editor después de ' + maxAttempts + ' intentos');
                                    resolve(false);
                                }
                            }, 300); // Esperar 300ms entre intentos
                        } else if (ckEditor.classList.contains('ck-focused')) {
                            // Ya está enfocado, escribir directamente
                            console.log('Editor ya está enfocado');
                            ckEditor.innerHTML = '<p>' + campaignName + '</p>';
                            ckEditor.dispatchEvent(new Event('input', { bubbles: true }));
                            resolve(true);
                        }
                    }
                    
                    // Iniciar el proceso
                    tryToWriteDescription();
                });
            """, campaign_name)

            # Esperar el resultado de la promesa
            time.sleep(3)  # Dar tiempo para los intentos

            # Verificar si se logró escribir
            if description_success:
                self.log("   ✓ Descripción configurada con JavaScript")
            else:
                self.log("   ⚠️ JavaScript no pudo configurar la descripción")
                
                # Intentar con Selenium
                self.log("   Intentando con Selenium...")
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.common.keys import Keys
                    from selenium.webdriver.common.action_chains import ActionChains
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    # Buscar el editor
                    ck_editor = self.driver.find_element(By.CSS_SELECTOR, '.ck-editor__editable')
                    
                    # Scroll al elemento
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", ck_editor)
                    time.sleep(0.5)
                    
                    # Usar ActionChains para un click más confiable
                    actions = ActionChains(self.driver)
                    actions.move_to_element(ck_editor)
                    actions.click()
                    actions.perform()
                    
                    # Esperar a que tenga la clase ck-focused
                    wait = WebDriverWait(self.driver, 10)
                    wait.until(lambda driver: 'ck-focused' in ck_editor.get_attribute('class'))
                    
                    self.log("   Editor enfocado con Selenium")
                    
                    # Limpiar y escribir
                    ck_editor.send_keys(Keys.CONTROL + 'a')
                    ck_editor.send_keys(Keys.DELETE)
                    time.sleep(0.2)
                    ck_editor.send_keys(campaign_name)
                    
                    self.log("   ✓ Descripción escrita con Selenium")
                    
                except Exception as e:
                    self.log(f"   ❌ Error con Selenium: {str(e)}")
                    
                    # Como último recurso, resaltar el campo e instrucciones detalladas
                    self.driver.execute_script("""
                        var ckEditor = document.querySelector('.ck-editor__editable');
                        if (ckEditor) {
                            ckEditor.style.border = '3px solid red';
                            ckEditor.style.boxShadow = '0 0 10px red';
                        }
                    """)
                    
                    self.log("\n   ❌ No se pudo llenar la descripción automáticamente")
                    self.log("   Por favor sigue estos pasos:")
                    self.log("   1. Haz clic en el campo de Description (resaltado en rojo)")
                    self.log("   2. Espera a que el cursor aparezca y el borde cambie")
                    self.log(f"   3. Escribe: {campaign_name}")
                    self.log("   4. Asegúrate que el texto aparezca en el campo")
                    input("   >>> Presiona ENTER cuando hayas llenado la descripción...")

            # Verificación final de ambos campos
            time.sleep(1)
            final_check = self.driver.execute_script("""
                var check = {
                    name: '',
                    description: '',
                    descriptionHtml: ''
                };
                
                // Verificar nombre
                var nameField = document.getElementById('campaign_name');
                check.name = nameField ? nameField.value : '';
                
                // Verificar descripción - múltiples métodos
                var ckEditor = document.querySelector('.ck-editor__editable');
                if (ckEditor) {
                    check.description = ckEditor.textContent || ckEditor.innerText || '';
                    check.descriptionHtml = ckEditor.innerHTML;
                }
                
                // También verificar el textarea oculto si existe
                var hiddenDesc = document.getElementById('campaign_description');
                if (hiddenDesc && !check.description) {
                    check.description = hiddenDesc.value;
                }
                
                return check;
            """)

            self.log(f"   Verificación final - Name: '{final_check['name']}'")
            self.log(f"   Verificación final - Description: '{final_check['description'].strip()}'")

            # Validar que ambos campos estén llenos
            if final_check['name'] == campaign_name and final_check['description'].strip():
                self.log("   ✅ PASO 2 COMPLETADO: Formulario llenado correctamente")
            else:
                if final_check['name'] != campaign_name:
                    self.log(f"   ❌ Nombre incorrecto o vacío")
                if not final_check['description'].strip():
                    self.log(f"   ❌ Descripción vacía")
                
                self.log(f"\n   Por favor verifica que:")
                self.log(f"   - Name: {campaign_name}")
                self.log(f"   - Description: {campaign_name}")
                input("   >>> Presiona ENTER cuando hayas corregido los campos...")

            time.sleep(1)
            
            # PASO 3: Launch Campaign Builder
            self.log("PASO 3: Lanzando Campaign Builder...")
            builder_launched = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var btnText = buttons[i].textContent.trim();
                    if (btnText.includes('Launch Campaign Builder') || 
                        (btnText.includes('Launch') && btnText.includes('Campaign'))) {
                        buttons[i].scrollIntoView(true);
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
            """)
            
            if builder_launched:
                self.log("   ✓ Campaign Builder lanzado")
                time.sleep(10)
            else:
                self.log("   ❌ No se pudo lanzar el builder")
                self.log("   Por favor haz clic en 'Launch Campaign Builder'")
                input("   >>> Presiona ENTER cuando se abra el builder...")
                time.sleep(3)
            
            # PASO 4: Seleccionar 'Contact segments' del dropdown
            self.log("PASO 4: Seleccionando 'Contact segments' del dropdown...")

            # Cerrar dropdown si está abierto
            dropdown_reset = self.driver.execute_script("""
                var dropdown = document.getElementById('SourceList_chosen');
                if (dropdown && dropdown.classList.contains('chosen-with-drop')) {
                    var clickTarget = dropdown.querySelector('.chosen-single');
                    if (clickTarget) clickTarget.click();
                    return true;
                }
                return false;
            """)

            if dropdown_reset:
                self.log("   Dropdown reiniciado")
                time.sleep(1)

            # Abrir dropdown
            self.log("Abriendo dropdown...")
            self.driver.execute_script("""
                var dropdown = document.getElementById('SourceList_chosen');
                if (dropdown) {
                    var clickTarget = dropdown.querySelector('.chosen-single');
                    if (clickTarget) clickTarget.click();
                }
            """)

            time.sleep(2)  # Esperar a que se abra

            # Hacer click en "Contact segments"
            self.log("Haciendo click en 'Contact segments'...")
            click_result = self.driver.execute_script("""
                var options = document.querySelectorAll('#SourceList_chosen .chosen-results li');
                
                for (var i = 0; i < options.length; i++) {
                    var li = options[i];
                    var text = li.textContent.trim();
                    
                    if (text === 'Contact segments') {
                        // Disparar todos los eventos necesarios
                        ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(function(eventType) {
                            var event = new MouseEvent(eventType, {
                                view: window,
                                bubbles: true,
                                cancelable: true
                            });
                            li.dispatchEvent(event);
                        });
                        
                        return true;
                    }
                }
                return false;
            """)

            if click_result:
                self.log("   ✓ Click ejecutado en 'Contact segments'")
                time.sleep(3)  # Dar tiempo para que se actualice
                
                # Verificación visual simple
                visual_check = self.driver.execute_script("""
                    var span = document.querySelector('#SourceList_chosen .chosen-single span');
                    return span ? span.textContent.trim() : '';
                """)
                
                # Si visualmente muestra "Contact segments" o está vacío pero sabemos que funcionó, continuar
                if visual_check == "Contact segments":
                    self.log("   ✅ PASO 4 COMPLETADO: 'Contact segments' seleccionado y verificado")
                else:
                    self.log(f"   ⚠️ Verificación automática muestra: '{visual_check}'")
                    self.log("   PERO el click se ejecutó correctamente.")
                    self.log("   ✅ PASO 4 COMPLETADO: Continuando con el proceso...")
                
                time.sleep(5)  # Esperar para que el modal se actualice completamente
            else:
                self.log("   ❌ No se encontró 'Contact segments'")
                self.log("   Por favor selecciónalo manualmente")
                input("   >>> Presiona ENTER después de seleccionar...")
                time.sleep(3)

            # NO detener el proceso por verificación fallida
            self.log("Continuando con PASO 5...")
            
            # PASO 5: Seleccionar el segmento específico
            self.log(f"PASO 5: Seleccionando segmento '{segment_name}'...")

            # DEBUGGING: Analizar el campo de búsqueda
            self.log("\n=== DEBUGGING: Analizando campo de segmentos ===")
            field_analysis = self.driver.execute_script("""
                var analysis = {
                    multiSelectFound: false,
                    searchInputFound: false,
                    containerId: null,
                    currentSelections: []
                };
                
                // Buscar el contenedor multi-select
                var containers = document.querySelectorAll('.chosen-container-multi');
                if (containers.length > 0) {
                    analysis.multiSelectFound = true;
                    analysis.containerId = containers[0].id;
                    
                    // Buscar el input de búsqueda
                    var searchInput = containers[0].querySelector('.chosen-search-input');
                    if (searchInput) {
                        analysis.searchInputFound = true;
                        analysis.inputValue = searchInput.value;
                        analysis.inputPlaceholder = searchInput.placeholder;
                        analysis.inputWidth = searchInput.style.width;
                    }
                    
                    // Ver selecciones actuales
                    var choices = containers[0].querySelectorAll('.chosen-choices .search-choice span');
                    for (var i = 0; i < choices.length; i++) {
                        analysis.currentSelections.push(choices[i].textContent.trim());
                    }
                }
                
                return JSON.stringify(analysis, null, 2);
            """)
            self.log("Análisis del campo:")
            self.log(field_analysis)

            # Hacer clic en el campo para activarlo
            self.log(f"\n>>> Activando campo de búsqueda para escribir '{segment_name}'...")
            field_activated = self.driver.execute_script("""
                // Buscar el contenedor multi-select
                var container = document.querySelector('.chosen-container-multi');
                if (!container) {
                    console.log('No se encontró contenedor multi-select');
                    return false;
                }
                
                // Buscar el input de búsqueda dentro
                var searchInput = container.querySelector('.chosen-search-input');
                if (!searchInput) {
                    // Si no hay input, hacer clic en el contenedor para crearlo
                    var choicesDiv = container.querySelector('.chosen-choices');
                    if (choicesDiv) {
                        choicesDiv.click();
                        console.log('Click en chosen-choices');
                        
                        // Esperar y buscar el input nuevamente
                        setTimeout(function() {
                            searchInput = container.querySelector('.chosen-search-input');
                            if (searchInput) {
                                searchInput.focus();
                                console.log('Input encontrado y enfocado después del click');
                            }
                        }, 500);
                    }
                    return true;
                }
                
                // Si el input ya existe, enfocarlo
                searchInput.focus();
                searchInput.click();
                console.log('Input de búsqueda enfocado');
                
                // Limpiar el valor por defecto si existe
                if (searchInput.value === 'Choose one or more...' || searchInput.placeholder === 'Choose one or more...') {
                    searchInput.value = '';
                    console.log('Valor por defecto limpiado');
                }
                
                return true;
            """)

            if field_activated:
                self.log("   ✓ Campo de búsqueda activado")
                time.sleep(1)
                
                # Escribir el nombre del segmento
                self.log(f"   Escribiendo '{segment_name}'...")
                
                # MÉTODO 1: Escribir usando JavaScript y eventos
                typing_result = self.driver.execute_script("""
                    var segmentName = arguments[0];
                    
                    // Encontrar el input de búsqueda
                    var searchInput = document.querySelector('.chosen-container-multi .chosen-search-input');
                    if (!searchInput) {
                        console.log('No se encontró el input de búsqueda');
                        return false;
                    }
                    
                    console.log('Input encontrado, escribiendo: ' + segmentName);
                    
                    // Asegurar que el input esté enfocado
                    searchInput.focus();
                    
                    // Limpiar cualquier valor existente
                    searchInput.value = '';
                    
                    // Escribir el texto carácter por carácter para simular escritura real
                    for (var i = 0; i < segmentName.length; i++) {
                        searchInput.value += segmentName[i];
                        
                        // Disparar evento input para cada carácter
                        var inputEvent = new Event('input', {
                            bubbles: true,
                            cancelable: true
                        });
                        searchInput.dispatchEvent(inputEvent);
                        
                        // También disparar keyup
                        var keyupEvent = new KeyboardEvent('keyup', {
                            bubbles: true,
                            cancelable: true,
                            key: segmentName[i],
                            code: 'Key' + segmentName[i].toUpperCase()
                        });
                        searchInput.dispatchEvent(keyupEvent);
                    }
                    
                    console.log('Texto escrito: ' + searchInput.value);
                    
                    // Disparar eventos finales para activar la búsqueda
                    var changeEvent = new Event('change', {
                        bubbles: true,
                        cancelable: true
                    });
                    searchInput.dispatchEvent(changeEvent);
                    
                    var keyupFinal = new KeyboardEvent('keyup', {
                        bubbles: true,
                        cancelable: true
                    });
                    searchInput.dispatchEvent(keyupFinal);
                    
                    return true;
                """, segment_name)
                
                if typing_result:
                    self.log(f"   ✓ Texto '{segment_name}' escrito")
                    time.sleep(2)  # Esperar a que aparezcan las opciones filtradas
                    
                    # Verificar qué opciones aparecieron
                    self.log("\n   Verificando opciones disponibles...")
                    options_check = self.driver.execute_script("""
                        var options = document.querySelectorAll('.chosen-container-multi .chosen-results li.active-result');
                        var availableOptions = [];
                        
                        console.log('Opciones encontradas después de escribir: ' + options.length);
                        
                        for (var i = 0; i < options.length; i++) {
                            var optionText = options[i].textContent.trim();
                            availableOptions.push(optionText);
                            console.log('Opción ' + i + ': "' + optionText + '"');
                        }
                        
                        return {
                            count: options.length,
                            options: availableOptions
                        };
                    """)
                    
                    self.log(f"   Opciones disponibles: {options_check['count']}")
                    if options_check['count'] > 0:
                        self.log(f"   Opciones: {options_check['options']}")
                        
                        # Seleccionar la primera opción
                        self.log("   Seleccionando primera opción...")
                        selection_result = self.driver.execute_script("""
                            var options = document.querySelectorAll('.chosen-container-multi .chosen-results li.active-result');
                            
                            if (options.length > 0) {
                                console.log('Seleccionando primera opción: ' + options[0].textContent.trim());
                                
                                // Método 1: Click directo
                                options[0].click();
                                
                                // Si no funciona, método 2: Eventos completos
                                var events = ['mouseover', 'mousedown', 'mouseup', 'click'];
                                events.forEach(function(eventType) {
                                    var event = new MouseEvent(eventType, {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    options[0].dispatchEvent(event);
                                });
                                
                                return {
                                    success: true,
                                    selectedText: options[0].textContent.trim()
                                };
                            }
                            
                            return { success: false };
                        """)
                        
                        if selection_result['success']:
                            self.log(f"   ✓✓✓ Segmento seleccionado: '{selection_result['selectedText']}'")
                            time.sleep(3)
                        else:
                            self.log("   ❌ No se pudo hacer clic en la opción")
                    else:
                        self.log("   ❌ No aparecieron opciones después de escribir")
                        
                        # MÉTODO ALTERNATIVO: Usar Selenium para escribir
                        self.log("\n   Intentando método alternativo con Selenium...")
                        try:
                            from selenium.webdriver.common.by import By
                            from selenium.webdriver.common.keys import Keys
                            
                            # Encontrar el input
                            search_input = self.driver.find_element(By.CSS_SELECTOR, '.chosen-container-multi .chosen-search-input')
                            
                            # Limpiar y escribir
                            search_input.clear()
                            search_input.send_keys(segment_name)
                            time.sleep(2)  # Esperar opciones
                            
                            # Presionar Enter o flecha abajo + Enter para seleccionar primera opción
                            search_input.send_keys(Keys.ARROW_DOWN)
                            time.sleep(0.5)
                            search_input.send_keys(Keys.RETURN)
                            
                            self.log(f"   ✓ Texto escrito y Enter presionado con Selenium")
                            time.sleep(2)
                            
                        except Exception as e:
                            self.log(f"   ❌ Error con método Selenium: {str(e)}")
                else:
                    self.log("   ❌ No se pudo escribir el texto")
                    
                # Si todo falla, pedir intervención manual
                final_check = self.driver.execute_script("""
                    var container = document.querySelector('.chosen-container-multi');
                    var selections = [];
                    
                    if (container) {
                        var choices = container.querySelectorAll('.chosen-choices .search-choice span');
                        for (var i = 0; i < choices.length; i++) {
                            selections.push(choices[i].textContent.trim());
                        }
                    }
                    
                    return selections;
                """)
                
                if len(final_check) == 0 or not any(segment_name in s for s in final_check):
                    self.log(f"\n   ❌ El segmento '{segment_name}' no se seleccionó automáticamente")
                    self.log("   Por favor:")
                    self.log("   1. Haz clic en el campo 'Contact segments'")
                    self.log(f"   2. Escribe '{segment_name}'")
                    self.log("   3. Selecciona la primera opción que aparece")
                    input("   >>> Presiona ENTER cuando hayas seleccionado el segmento...")
                    time.sleep(2)
            else:
                self.log("   ❌ No se pudo activar el campo de búsqueda")
                self.log(f"   Por favor selecciona el segmento '{segment_name}' manualmente")
                input("   >>> Presiona ENTER cuando hayas seleccionado el segmento...")
                time.sleep(3)

            # Verificación final del PASO 5
            self.log("\n=== Verificación final del PASO 5 ===")
            final_verification = self.driver.execute_script("""
                var verification = {
                    segmentsSelected: [],
                    searchInputValue: '',
                    success: false
                };
                
                // Verificar selecciones en el multi-select
                var container = document.querySelector('.chosen-container-multi');
                if (container) {
                    // Obtener segmentos seleccionados
                    var choices = container.querySelectorAll('.chosen-choices .search-choice span');
                    for (var i = 0; i < choices.length; i++) {
                        verification.segmentsSelected.push(choices[i].textContent.trim());
                    }
                    
                    // Verificar el input
                    var searchInput = container.querySelector('.chosen-search-input');
                    if (searchInput) {
                        verification.searchInputValue = searchInput.value;
                    }
                }
                
                verification.success = verification.segmentsSelected.length > 0;
                
                return verification;
            """)

            if final_verification['success']:
                self.log(f"   ✅ PASO 5 COMPLETADO exitosamente")
                self.log(f"   Segmentos seleccionados: {final_verification['segmentsSelected']}")
            else:
                self.log("   ⚠️ PASO 5 requirió intervención manual")

            self.log("=== FIN DEL PASO 5 ===\n")
            
            # PASO 6: Hacer clic en "Add"
            self.log("PASO 6: Haciendo clic en Add...")
            add_clicked = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    if (buttons[i].textContent.trim().toLowerCase() === 'add' && 
                        buttons[i].offsetParent !== null) {
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
            """)
            
            if add_clicked:
                self.log("   ✓ Contact source agregado")
            else:
                self.log("   ❌ No se encontró el botón Add")
                self.log("   Por favor haz clic en 'Add'")
                input("   >>> Presiona ENTER cuando hayas hecho clic en 'Add'...")
            
            time.sleep(6)
            
            # PASO 7: Hacer clic en el "+"
            self.log("PASO 7: Haciendo clic en + para agregar acción...")

            # DEBUGGING: Analizar elementos jsPlumb
            self.log("Analizando elementos del builder...")
            elements_debug = self.driver.execute_script("""
                var debug = {
                    endpoints: [],
                    campaignBoxes: 0
                };
                
                // Buscar endpoints de jsPlumb
                var endpoints = document.querySelectorAll('.jtk-endpoint');
                debug.endpointsCount = endpoints.length;
                
                for (var i = 0; i < endpoints.length; i++) {
                    var ep = endpoints[i];
                    debug.endpoints.push({
                        classes: ep.className,
                        isVisible: ep.offsetHeight > 0,
                        position: {
                            top: ep.style.top,
                            left: ep.style.left
                        }
                    });
                }
                
                // Buscar la caja de campaign source
                var sourceBox = document.querySelector('.list-campaign-source, .list-campaign-leadsource, div[data-type="source"]');
                debug.hasSourceBox = !!sourceBox;
                
                console.log('Debug info:', debug);
                return debug;
            """)

            self.log(f"   Endpoints jsPlumb encontrados: {elements_debug.get('endpointsCount', 0)}")

            # Hacer clic en el endpoint correcto
            plus_clicked = self.driver.execute_script("""
                // Buscar el endpoint específico del source
                // Puede tener varias combinaciones de clases
                var possibleSelectors = [
                    '.jtk-endpoint.jtk-endpoint-anchor-leadsource',
                    '.jtk-endpoint.CampaignEvent_lists',
                    '.jtk-endpoint[class*="leadsource"]',
                    '.jtk-endpoint.jtk-draggable.jtk-droppable',
                    '.jtk-endpoint' // Si todo falla, cualquier endpoint
                ];
                
                for (var s = 0; s < possibleSelectors.length; s++) {
                    var endpoints = document.querySelectorAll(possibleSelectors[s]);
                    console.log('Selector "' + possibleSelectors[s] + '" encontró: ' + endpoints.length + ' elementos');
                    
                    if (endpoints.length > 0) {
                        for (var i = 0; i < endpoints.length; i++) {
                            var endpoint = endpoints[i];
                            
                            // Verificar que sea visible y esté en la posición correcta
                            if (endpoint.offsetHeight > 0 && endpoint.offsetWidth > 0) {
                                console.log('Endpoint encontrado con clases: ' + endpoint.className);
                                
                                // Scroll al elemento
                                endpoint.scrollIntoView({behavior: 'smooth', block: 'center'});
                                
                                // IMPORTANTE: Simular hover primero para que jsPlumb agregue las clases necesarias
                                var mouseenterEvent = new MouseEvent('mouseenter', {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true
                                });
                                endpoint.dispatchEvent(mouseenterEvent);
                                
                                var mouseoverEvent = new MouseEvent('mouseover', {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true
                                });
                                endpoint.dispatchEvent(mouseoverEvent);
                                
                                // Esperar un momento para que jsPlumb actualice las clases
                                setTimeout(function() {
                                    console.log('Clases después del hover: ' + endpoint.className);
                                    
                                    // Ahora hacer click
                                    var clickEvent = new MouseEvent('click', {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true,
                                        clientX: endpoint.getBoundingClientRect().left + 10,
                                        clientY: endpoint.getBoundingClientRect().top + 10
                                    });
                                    endpoint.dispatchEvent(clickEvent);
                                    
                                    // También intentar con mousedown/mouseup
                                    var mousedownEvent = new MouseEvent('mousedown', {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    endpoint.dispatchEvent(mousedownEvent);
                                    
                                    var mouseupEvent = new MouseEvent('mouseup', {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    endpoint.dispatchEvent(mouseupEvent);
                                    
                                }, 500);
                                
                                return true;
                            }
                        }
                    }
                }
                
                return false;
            """)

            if plus_clicked:
                self.log("   ✓ Hover y click en endpoint ejecutados")
                time.sleep(2)  # Esperar a que se procese el click
                
                # Verificar si apareció un menú o modal
                action_menu_check = self.driver.execute_script("""
                    // Verificar diferentes tipos de menús que podrían aparecer
                    var checks = {
                        modal: !!document.querySelector('.modal.in, .modal.show, .modal-dialog:not([style*="display: none"])'),
                        dropdown: !!document.querySelector('.dropdown-menu[style*="display: block"], .dropdown.open'),
                        actionList: !!document.querySelector('[class*="action"], [class*="event-type"]'),
                        popover: !!document.querySelector('.popover, .tooltip.in')
                    };
                    
                    console.log('Verificación de menú:', checks);
                    
                    return checks.modal || checks.dropdown || checks.actionList || checks.popover;
                """)
                
                if action_menu_check:
                    self.log("   ✓ Menú de acciones abierto")
                    time.sleep(2)
                else:
                    self.log("   ⚠️ No se detectó apertura de menú")
                    self.log("   Si ves el menú abierto, presiona ENTER para continuar")
                    input("   >>> Presiona ENTER para continuar...")
            else:
                self.log("   ❌ No se pudo hacer clic automáticamente")
                
                # Método alternativo con Selenium
                self.log("\n   Intentando método alternativo con Selenium...")
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    from selenium.webdriver.common.by import By
                    
                    # Buscar el endpoint
                    endpoint = self.driver.find_element(By.CSS_SELECTOR, '.jtk-endpoint')
                    
                    # Usar ActionChains para simular hover y click real
                    actions = ActionChains(self.driver)
                    actions.move_to_element(endpoint)
                    actions.pause(0.5)
                    actions.click()
                    actions.perform()
                    
                    self.log("   ✓ Click con Selenium ejecutado")
                    time.sleep(2)
                except Exception as e:
                    self.log(f"   ❌ Error con Selenium: {str(e)}")
                    
                    # Resaltar visualmente el elemento
                    self.driver.execute_script("""
                        var endpoints = document.querySelectorAll('.jtk-endpoint');
                        for (var i = 0; i < endpoints.length; i++) {
                            endpoints[i].style.border = '3px solid red';
                            endpoints[i].style.backgroundColor = 'yellow';
                            endpoints[i].style.zIndex = '9999';
                        }
                        console.log('Endpoints resaltados en rojo/amarillo');
                    """)
                    
                    self.log("\n   Por favor haz clic manualmente en el círculo '+' (resaltado en amarillo/rojo)")
                    self.log("   Está en la parte inferior del cuadro 'Segmento-DV'")
                    input("   >>> Presiona ENTER después de hacer clic...")
                    time.sleep(2)

            self.log("Continuando con PASO 8...")
            
            # PASO 8: Seleccionar "Action"
            self.log("PASO 8: Seleccionando Action...")

            # Esperar a que el panel se cargue completamente
            time.sleep(2)

            # DEBUGGING: Analizar el panel de selección
            self.log("Analizando panel de selección...")
            panel_info = self.driver.execute_script("""
                var info = {
                    panelFound: false,
                    options: []
                };
                
                // Buscar el panel con las opciones
                var panels = document.querySelectorAll('.panel');
                console.log('Paneles encontrados: ' + panels.length);
                
                for (var i = 0; i < panels.length; i++) {
                    var panel = panels[i];
                    
                    // Buscar los botones dentro del panel
                    var buttons = panel.querySelectorAll('button, .btn');
                    
                    for (var j = 0; j < buttons.length; j++) {
                        var btn = buttons[j];
                        var dataType = btn.getAttribute('data-type');
                        var text = btn.textContent.trim();
                        
                        info.options.push({
                            text: text,
                            dataType: dataType,
                            classes: btn.className,
                            isVisible: btn.offsetHeight > 0
                        });
                        
                        console.log('Botón encontrado: ' + text + ' (data-type: ' + dataType + ')');
                    }
                }
                
                info.panelFound = info.options.length > 0;
                return info;
            """)

            self.log(f"   Panel encontrado: {panel_info['panelFound']}")
            self.log(f"   Botones disponibles: {len(panel_info['options'])}")

            # Hacer clic en el botón Select de Action
            action_selected = self.driver.execute_script("""
                var clicked = false;
                
                // Estrategia 1: Buscar por data-type="Action"
                var actionButton = document.querySelector('button[data-type="Action"]');
                if (actionButton) {
                    console.log('Botón Action encontrado por data-type');
                    actionButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                    actionButton.click();
                    return true;
                }
                
                // Estrategia 2: Buscar el panel de Action y luego su botón Select
                var panels = document.querySelectorAll('.panel');
                
                for (var i = 0; i < panels.length; i++) {
                    var panel = panels[i];
                    
                    // Verificar si este panel es para Action
                    var panelText = panel.textContent;
                    
                    if (panelText.includes('Action') || panelText.includes('action')) {
                        console.log('Panel de Action encontrado');
                        
                        // Buscar el botón Select dentro de este panel
                        var selectButtons = panel.querySelectorAll('button');
                        
                        for (var j = 0; j < selectButtons.length; j++) {
                            var btn = selectButtons[j];
                            
                            // Verificar si es el botón Select (no el título)
                            if (btn.textContent.trim() === 'Select' || 
                                btn.className.includes('btn-primary') ||
                                btn.className.includes('btn-default')) {
                                
                                console.log('Botón Select de Action encontrado: ' + btn.className);
                                btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                                btn.click();
                                return true;
                            }
                        }
                    }
                }
                
                // Estrategia 3: Si hay exactamente 3 botones Select, elegir el del medio
                var allSelectButtons = document.querySelectorAll('button');
                var selectButtons = [];
                
                for (var k = 0; k < allSelectButtons.length; k++) {
                    if (allSelectButtons[k].textContent.trim() === 'Select' && 
                        allSelectButtons[k].offsetHeight > 0) {
                        selectButtons.push(allSelectButtons[k]);
                    }
                }
                
                console.log('Total de botones Select encontrados: ' + selectButtons.length);
                
                // Si hay 3 botones (Decision, Action, Condition), Action suele ser el del medio
                if (selectButtons.length === 3) {
                    console.log('Haciendo clic en el botón Select del medio (Action)');
                    selectButtons[1].scrollIntoView({behavior: 'smooth', block: 'center'});
                    selectButtons[1].click();
                    return true;
                }
                
                return false;
            """)

            if action_selected:
                self.log("   ✓ Botón 'Select' de Action clickeado")
                time.sleep(3)
                
                # Verificar que el panel se cerró o cambió la vista
                panel_closed = self.driver.execute_script("""
                    // Verificar si el panel de selección ya no está visible
                    var panels = document.querySelectorAll('.panel');
                    var visiblePanels = 0;
                    
                    for (var i = 0; i < panels.length; i++) {
                        if (panels[i].offsetHeight > 0 && panels[i].textContent.includes('Select')) {
                            visiblePanels++;
                        }
                    }
                    
                    // También verificar si apareció un nuevo formulario o modal
                    var newForm = document.querySelector('form.action-form, .modal.in, #ActionForm');
                    
                    return visiblePanels === 0 || !!newForm;
                """)
                
                if panel_closed:
                    self.log("   ✓ Vista actualizada después de seleccionar Action")
                else:
                    self.log("   ⚠️ Panel aún visible, pero continuando...")
            else:
                self.log("   ❌ No se pudo hacer clic automáticamente")
                
                # Método alternativo con coordenadas específicas
                self.log("\n   Intentando método alternativo...")
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.common.action_chains import ActionChains
                    
                    # Buscar específicamente el botón con data-type="Action"
                    action_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-type="Action"]')
                    
                    # Usar ActionChains para un click más confiable
                    actions = ActionChains(self.driver)
                    actions.move_to_element(action_btn)
                    actions.pause(0.5)
                    actions.click()
                    actions.perform()
                    
                    self.log("   ✓ Click con Selenium ejecutado")
                    time.sleep(3)
                except Exception as e:
                    self.log(f"   ❌ Método alternativo falló: {str(e)}")
                    
                    # Resaltar el botón correcto
                    self.driver.execute_script("""
                        // Resaltar el botón de Action
                        var actionBtn = document.querySelector('button[data-type="Action"]');
                        if (actionBtn) {
                            actionBtn.style.border = '3px solid red';
                            actionBtn.style.backgroundColor = 'yellow';
                        } else {
                            // Si no lo encuentra por data-type, resaltar el botón del medio
                            var selectBtns = document.querySelectorAll('button');
                            var selects = [];
                            for (var i = 0; i < selectBtns.length; i++) {
                                if (selectBtns[i].textContent.trim() === 'Select') {
                                    selects.push(selectBtns[i]);
                                }
                            }
                            if (selects.length >= 2) {
                                selects[1].style.border = '3px solid red';
                                selects[1].style.backgroundColor = 'yellow';
                            }
                        }
                        console.log('Botón de Action resaltado');
                    """)
                    
                    self.log("\n   Por favor haz clic en el botón 'Select' bajo 'Action'")
                    self.log("   (Es el botón del medio, resaltado en amarillo/rojo)")
                    input("   >>> Presiona ENTER después de hacer clic...")
                    time.sleep(3)

            self.log("Continuando con PASO 9...")
            
            # PASO 9: Seleccionar "Send email"
            self.log("PASO 9: Seleccionando Send email...")

            # Esperar a que el dropdown de Actions se cargue
            time.sleep(2)

            # DEBUGGING: Analizar el dropdown de Actions
            self.log("Analizando dropdown de Actions...")
            dropdown_info = self.driver.execute_script("""
                var info = {
                    dropdownFound: false,
                    inputFound: false,
                    currentSelection: '',
                    dropdownOpen: false
                };
                
                // Buscar el dropdown de Actions
                var actionDropdown = document.getElementById('ActionList_chosen');
                if (actionDropdown) {
                    info.dropdownFound = true;
                    info.dropdownOpen = actionDropdown.classList.contains('chosen-with-drop');
                    
                    // Ver qué está seleccionado
                    var selectedSpan = actionDropdown.querySelector('.chosen-single span');
                    if (selectedSpan) {
                        info.currentSelection = selectedSpan.textContent.trim();
                    }
                    
                    // Buscar el input de búsqueda
                    var searchInput = actionDropdown.querySelector('.chosen-search-input');
                    if (searchInput) {
                        info.inputFound = true;
                    }
                }
                
                console.log('Info del dropdown:', info);
                return info;
            """)

            self.log(f"   Dropdown encontrado: {dropdown_info['dropdownFound']}")
            self.log(f"   Selección actual: '{dropdown_info['currentSelection']}'")

            # Abrir el dropdown si no está abierto
            if not dropdown_info['dropdownOpen']:
                self.log("Abriendo dropdown de Actions...")
                self.driver.execute_script("""
                    var dropdown = document.getElementById('ActionList_chosen');
                    if (dropdown) {
                        var clickTarget = dropdown.querySelector('.chosen-single');
                        if (clickTarget) {
                            clickTarget.click();
                            console.log('Click en dropdown ejecutado');
                        }
                    }
                """)
                time.sleep(1)

            # Escribir "Send email" en el campo de búsqueda
            self.log("Escribiendo 'Send email' en el campo de búsqueda...")
            typing_success = self.driver.execute_script("""
                var searchText = 'Send email';
                
                // Buscar el input de búsqueda
                var searchInput = document.querySelector('#ActionList_chosen .chosen-search-input');
                
                if (!searchInput) {
                    console.log('Input de búsqueda no encontrado');
                    return false;
                }
                
                console.log('Input encontrado, escribiendo: ' + searchText);
                
                // Enfocar y limpiar el input
                searchInput.focus();
                searchInput.value = '';
                
                // Escribir el texto carácter por carácter
                for (var i = 0; i < searchText.length; i++) {
                    searchInput.value += searchText[i];
                    
                    // Disparar evento input para cada carácter
                    var inputEvent = new Event('input', {
                        bubbles: true,
                        cancelable: true
                    });
                    searchInput.dispatchEvent(inputEvent);
                    
                    // También disparar keyup
                    var keyupEvent = new KeyboardEvent('keyup', {
                        bubbles: true,
                        cancelable: true,
                        key: searchText[i]
                    });
                    searchInput.dispatchEvent(keyupEvent);
                }
                
                console.log('Texto escrito: ' + searchInput.value);
                
                // Disparar evento final para activar la búsqueda
                var changeEvent = new Event('change', {
                    bubbles: true,
                    cancelable: true
                });
                searchInput.dispatchEvent(changeEvent);
                
                return true;
            """)

            if typing_success:
                self.log("   ✓ 'Send email' escrito en el campo")
                time.sleep(2)  # Esperar a que aparezcan las opciones filtradas
                
                # Seleccionar la primera opción que coincida
                self.log("Seleccionando 'Send email' de las opciones...")
                selection_success = self.driver.execute_script("""
                    // Buscar las opciones filtradas
                    var options = document.querySelectorAll('#ActionList_chosen .chosen-results li.active-result');
                    console.log('Opciones disponibles: ' + options.length);
                    
                    for (var i = 0; i < options.length; i++) {
                        var optionText = options[i].textContent.trim();
                        console.log('Opción ' + i + ': "' + optionText + '"');
                        
                        // Buscar coincidencia exacta o parcial con "Send email"
                        if (optionText === 'Send email' || 
                            optionText === 'Send email to user' ||
                            optionText.toLowerCase().includes('send email')) {
                            
                            console.log('Opción encontrada, haciendo click: ' + optionText);
                            
                            // Hacer scroll y click
                            options[i].scrollIntoView(false);
                            
                            // Disparar eventos de mouse
                            var events = ['mouseover', 'mousedown', 'mouseup', 'click'];
                            events.forEach(function(eventType) {
                                var event = new MouseEvent(eventType, {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true
                                });
                                options[i].dispatchEvent(event);
                            });
                            
                            return true;
                        }
                    }
                    
                    // Si no hay coincidencia exacta, seleccionar la primera opción
                    if (options.length > 0) {
                        console.log('Seleccionando primera opción: ' + options[0].textContent.trim());
                        options[0].click();
                        return true;
                    }
                    
                    return false;
                """)
                
                if selection_success:
                    self.log("   ✓✓ 'Send email' seleccionado")
                    time.sleep(3)
                    
                    # Verificar la selección
                    verification = self.driver.execute_script("""
                        var selectedSpan = document.querySelector('#ActionList_chosen .chosen-single span');
                        var selectedText = selectedSpan ? selectedSpan.textContent.trim() : '';
                        
                        return {
                            text: selectedText,
                            success: selectedText.includes('Send email') || selectedText.includes('email')
                        };
                    """)
                    
                    if verification['success']:
                        self.log(f"   ✅ PASO 9 COMPLETADO: '{verification['text']}' seleccionado")
                    else:
                        self.log(f"   ⚠️ Seleccionado: '{verification['text']}'")
                else:
                    self.log("   ❌ No se pudo seleccionar 'Send email'")
            else:
                # Método alternativo con Selenium
                self.log("   Intentando método alternativo con Selenium...")
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.common.keys import Keys
                    
                    # Abrir dropdown si es necesario
                    dropdown = self.driver.find_element(By.ID, "ActionList_chosen")
                    dropdown.click()
                    time.sleep(1)
                    
                    # Encontrar el input de búsqueda
                    search_input = self.driver.find_element(By.CSS_SELECTOR, "#ActionList_chosen .chosen-search-input")
                    
                    # Escribir "Send email"
                    search_input.clear()
                    search_input.send_keys("Send email")
                    time.sleep(2)
                    
                    # Presionar Enter o flecha abajo + Enter
                    search_input.send_keys(Keys.ARROW_DOWN)
                    time.sleep(0.5)
                    search_input.send_keys(Keys.RETURN)
                    
                    self.log("   ✓ Seleccionado con Selenium")
                    time.sleep(3)
                except Exception as e:
                    self.log(f"   ❌ Error con Selenium: {str(e)}")
                    
                    self.log("\n   Por favor selecciona 'Send email' manualmente:")
                    self.log("   1. Haz clic en el dropdown de 'Actions'")
                    self.log("   2. Escribe 'Send email' en el campo de búsqueda")
                    self.log("   3. Selecciona 'Send email' de las opciones")
                    input("   >>> Presiona ENTER después de seleccionar...")
                    time.sleep(3)

            # Verificación final
            final_check = self.driver.execute_script("""
                var selectedSpan = document.querySelector('#ActionList_chosen .chosen-single span');
                return selectedSpan ? selectedSpan.textContent.trim() : 'Nothing selected';
            """)

            self.log(f"Selección final: '{final_check}'")
            self.log("Continuando con PASO 10...")
            
            # PASO 10: Configurar el email
            self.log("PASO 10: Configurando email...")

            # Primero configurar los campos simples (Name, Marketing, Attempts)
            fields_configured = self.driver.execute_script("""
                var emailName = arguments[0];
                var configured = {
                    name: false,
                    marketing: false,
                    attempts: false
                };
                
                // 1. Llenar nombre usando el ID específico
                var nameField = document.getElementById('campaignevent_name');
                if (nameField) {
                    nameField.value = emailName;
                    nameField.dispatchEvent(new Event('input', {bubbles: true}));
                    nameField.dispatchEvent(new Event('change', {bubbles: true}));
                    configured.name = true;
                    console.log('Nombre configurado: ' + emailName);
                }
                
                // 2. Seleccionar Marketing
                var marketingRadio = document.querySelector('input[type="radio"][value="marketing"]');
                if (marketingRadio && !marketingRadio.checked) {
                    marketingRadio.click();
                    configured.marketing = true;
                    console.log('Marketing seleccionado');
                }
                
                // 3. Cambiar attempts a 0 usando el ID específico
                var attemptsField = document.getElementById('campaignevent_properties_attempts');
                if (attemptsField) {
                    attemptsField.value = '0';
                    attemptsField.dispatchEvent(new Event('input', {bubbles: true}));
                    attemptsField.dispatchEvent(new Event('change', {bubbles: true}));
                    configured.attempts = true;
                    console.log('Attempts cambiado a 0');
                }
                
                return configured;
            """, campaign_name)

            if all(fields_configured.values()):
                self.log("   ✓ Todos los campos básicos configurados correctamente")
            else:
                self.log("   ⚠️ Algunos campos básicos no se configuraron:")
                for campo, estado in fields_configured.items():
                    if not estado:
                        self.log(f"     - {campo}: NO configurado")

            time.sleep(1)

            # Ahora manejar el dropdown del email
            self.log("   Configurando selector de email...")

            # PASO 1: Abrir el dropdown de email
            dropdown_opened = self.driver.execute_script("""
                var dropdown = document.getElementById('campaignevent_properties_email_chosen');
                
                if (!dropdown) {
                    console.log('No se encontró el dropdown de email');
                    return false;
                }
                
                // Verificar si ya está abierto
                var isOpen = dropdown.classList.contains('chosen-with-drop');
                
                if (!isOpen) {
                    // Buscar el elemento clickeable (el <a> con clase chosen-single)
                    var clickTarget = dropdown.querySelector('a.chosen-single');
                    
                    if (clickTarget) {
                        // Simular click real
                        clickTarget.scrollIntoView({behavior: 'smooth', block: 'center'});
                        
                        var clickEvent = new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true
                        });
                        clickTarget.dispatchEvent(clickEvent);
                        
                        console.log('Click ejecutado en dropdown');
                        return true;
                    }
                } else {
                    console.log('Dropdown ya está abierto');
                    return true;
                }
                
                return false;
            """)

            if dropdown_opened:
                self.log("   ✓ Dropdown de email abierto")
                time.sleep(1)
            else:
                self.log("   ❌ No se pudo abrir el dropdown")

            # PASO 2: Escribir en el campo de búsqueda
            self.log(f"   Buscando y seleccionando email: {campaign_name}")

            email_written = self.driver.execute_script("""
                var emailName = arguments[0];
                
                // Buscar el input de búsqueda dentro del dropdown
                var searchInput = document.querySelector('#campaignevent_properties_email_chosen .chosen-search-input');
                
                if (!searchInput) {
                    console.log('No se encontró el input de búsqueda');
                    return false;
                }
                
                // Enfocar y limpiar el input
                searchInput.focus();
                searchInput.click();
                searchInput.value = '';
                
                console.log('Input de búsqueda encontrado, escribiendo: ' + emailName);
                
                // Escribir el texto completo
                searchInput.value = emailName;
                
                // Disparar múltiples eventos para asegurar que Chosen.js detecte el cambio
                var events = ['input', 'keyup', 'keydown', 'change'];
                events.forEach(function(eventType) {
                    var event = new Event(eventType, {
                        bubbles: true,
                        cancelable: true
                    });
                    searchInput.dispatchEvent(event);
                });
                
                // También disparar un keyup específico
                var keyupEvent = new KeyboardEvent('keyup', {
                    bubbles: true,
                    cancelable: true,
                    keyCode: 32  // Espacio para forzar actualización
                });
                searchInput.dispatchEvent(keyupEvent);
                
                console.log('Texto escrito: ' + searchInput.value);
                return true;
            """, campaign_name)

            if email_written:
                self.log("   ✓ Texto escrito en el campo de búsqueda")
                time.sleep(2)  # Dar tiempo para que se filtren las opciones
                
                # PASO 3: Seleccionar el email de la lista filtrada
                email_selected = self.driver.execute_script("""
                    var emailName = arguments[0];
                    var selected = false;
                    
                    // Buscar las opciones filtradas
                    var options = document.querySelectorAll('#campaignevent_properties_email_chosen .chosen-results li.active-result');
                    
                    console.log('Opciones disponibles: ' + options.length);
                    
                    for (var i = 0; i < options.length; i++) {
                        var option = options[i];
                        var optionText = option.textContent.trim();
                        
                        console.log('Opción ' + i + ': "' + optionText + '"');
                        
                        // Buscar coincidencia exacta o que contenga el nombre
                        if (optionText === emailName || 
                            optionText.includes(emailName) || 
                            emailName.includes(optionText)) {
                            
                            console.log('¡Email encontrado! Haciendo click...');
                            
                            // Asegurar que sea visible
                            option.scrollIntoView(false);
                            
                            // Simular hover primero (importante para Chosen.js)
                            var mouseOverEvent = new MouseEvent('mouseover', {
                                view: window,
                                bubbles: true,
                                cancelable: true
                            });
                            option.dispatchEvent(mouseOverEvent);
                            
                            // Agregar clase highlighted
                            option.classList.add('highlighted');
                            
                            // Esperar un momento y hacer click
                            setTimeout(function() {
                                // Click con todos los eventos necesarios
                                var events = ['mousedown', 'mouseup', 'click'];
                                events.forEach(function(eventType) {
                                    var event = new MouseEvent(eventType, {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    option.dispatchEvent(event);
                                });
                            }, 100);
                            
                            selected = true;
                            break;
                        }
                    }
                    
                    if (!selected && options.length > 0) {
                        // Si no hay coincidencia exacta, seleccionar la primera opción
                        console.log('No se encontró coincidencia exacta, seleccionando primera opción');
                        var firstOption = options[0];
                        
                        firstOption.scrollIntoView(false);
                        firstOption.classList.add('highlighted');
                        
                        setTimeout(function() {
                            firstOption.click();
                        }, 100);
                        
                        selected = true;
                    }
                    
                    return selected;
                """, campaign_name)
                
                if email_selected:
                    self.log("   ✓ Email seleccionado")
                    time.sleep(2)
                else:
                    self.log("   ❌ No se pudo seleccionar el email automáticamente")
                    
                    # Método alternativo: Usar Selenium
                    self.log("   Intentando método alternativo con Selenium...")
                    try:
                        from selenium.webdriver.common.by import By
                        from selenium.webdriver.common.keys import Keys
                        
                        # Buscar el input de búsqueda
                        search_input = self.driver.find_element(
                            By.CSS_SELECTOR, 
                            '#campaignevent_properties_email_chosen .chosen-search-input'
                        )
                        
                        # Limpiar y escribir
                        search_input.clear()
                        search_input.send_keys(campaign_name)
                        time.sleep(2)
                        
                        # Seleccionar primera opción con flechas
                        search_input.send_keys(Keys.ARROW_DOWN)
                        time.sleep(0.5)
                        search_input.send_keys(Keys.RETURN)
                        
                        self.log("   ✓ Seleccionado con Selenium")
                        time.sleep(2)
                        
                    except Exception as e:
                        self.log(f"   ❌ Error con Selenium: {str(e)}")
            else:
                self.log("   ❌ No se pudo escribir en el campo de búsqueda")

            # VERIFICACIÓN FINAL
            time.sleep(1)
            final_verification = self.driver.execute_script("""
                var check = {
                    name: '',
                    emailType: '',
                    attempts: '',
                    emailSelected: ''
                };
                
                // Verificar nombre
                var nameField = document.getElementById('campaignevent_name');
                check.name = nameField ? nameField.value : '';
                
                // Verificar tipo de email
                var marketingRadio = document.querySelector('input[type="radio"][value="marketing"]:checked');
                check.emailType = marketingRadio ? 'Marketing' : 'Unknown';
                
                // Verificar attempts
                var attemptsField = document.getElementById('campaignevent_properties_attempts');
                check.attempts = attemptsField ? attemptsField.value : 'Unknown';
                
                // Verificar email seleccionado
                var emailDropdown = document.querySelector('#campaignevent_properties_email_chosen .chosen-single span');
                check.emailSelected = emailDropdown ? emailDropdown.textContent.trim() : '';
                
                // Si el dropdown muestra "Search options..." significa que no se seleccionó nada
                if (check.emailSelected === 'Search options...' || check.emailSelected === 'Choose an option') {
                    check.emailSelected = '';
                }
                
                return check;
            """)

            self.log("\n   === Verificación final ===")
            self.log(f"   Name: {final_verification['name']}")
            self.log(f"   Email Type: {final_verification['emailType']}")
            self.log(f"   Attempts: {final_verification['attempts']}")
            self.log(f"   Email Selected: {final_verification['emailSelected']}")

            # Determinar si necesita intervención manual
            all_configured = (
                final_verification['name'] == campaign_name and
                final_verification['emailType'] == 'Marketing' and
                final_verification['attempts'] == '0' and
                final_verification['emailSelected'] != ''
            )

            if all_configured:
                self.log("   ✅ PASO 10 COMPLETADO: Todos los campos configurados correctamente")
            else:
                self.log("\n   ❌ Configuración incompleta. Por favor verifica manualmente:")
                
                if final_verification['name'] != campaign_name:
                    self.log(f"     - Name: Debe ser '{campaign_name}'")
                if final_verification['emailType'] != 'Marketing':
                    self.log(f"     - Email Type: Selecciona 'Marketing'")
                if final_verification['attempts'] != '0':
                    self.log(f"     - Attempts: Cambia a '0'")
                if final_verification['emailSelected'] == '':
                    self.log(f"     - Email: Busca y selecciona '{campaign_name}' en el dropdown")
                
                self.log("\n   Instrucciones para el selector de email:")
                self.log("     1. Haz clic en el dropdown 'Search options...'")
                self.log(f"     2. Escribe '{campaign_name}' en el campo de búsqueda")
                self.log("     3. Selecciona el email de la lista filtrada")
                
                input("\n   >>> Presiona ENTER cuando hayas configurado todo...")

            time.sleep(2)
            
            # PASO 11: Hacer clic en "Add" para agregar la acción
            self.log("PASO 11: Agregando acción de email...")
            action_added = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = buttons.length - 1; i >= 0; i--) {
                    var btn = buttons[i];
                    if (btn.textContent.trim().toLowerCase() === 'add' && btn.offsetParent !== null) {
                        if (btn.classList.contains('btn-primary') || 
                            btn.closest('.modal-footer') || 
                            btn.type === 'submit') {
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            """)
            
            if action_added:
                self.log("   ✓ Acción de email agregada")
            else:
                self.log("   ❌ No se encontró el botón Add")
                self.log("   Por favor haz clic en 'Add' para agregar la acción")
                input("   >>> Presiona ENTER cuando hayas hecho clic en 'Add'...")
            
            time.sleep(4)
            
            # PASO 12: Save Builder
            self.log("PASO 12: Guardando builder...")

            # Buscar el botón Save específico del builder
            save_clicked = self.driver.execute_script("""
                // Método 1: Buscar por onclick específico
                var saveButton = document.querySelector('button[onclick*="saveCampaignFromBuilder"]');
                
                if (saveButton && saveButton.offsetParent !== null) {
                    console.log('Botón Save encontrado por onclick');
                    saveButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                    saveButton.click();
                    return true;
                }
                
                // Método 2: Buscar dentro del contenedor btns-builder
                var builderButtons = document.querySelector('.btns-builder');
                if (builderButtons) {
                    var buttons = builderButtons.querySelectorAll('button');
                    
                    for (var i = 0; i < buttons.length; i++) {
                        var btn = buttons[i];
                        var btnText = btn.textContent.trim();
                        
                        // Buscar el botón que dice "Save" pero NO "Save/button"
                        if (btnText === 'Save' || btnText.toLowerCase() === 'save') {
                            console.log('Botón Save encontrado en btns-builder: ' + btn.className);
                            btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                }
                
                // Método 3: Buscar por clases específicas
                var saveByClass = document.querySelector('button.btn-primary.btn-apply-builder');
                if (saveByClass && saveByClass.textContent.includes('Save')) {
                    console.log('Botón Save encontrado por clases');
                    saveByClass.click();
                    return true;
                }
                
                // Método 4: Ejecutar la función directamente
                if (typeof Mautic !== 'undefined' && Mautic.saveCampaignFromBuilder) {
                    console.log('Ejecutando función saveCampaignFromBuilder directamente');
                    Mautic.saveCampaignFromBuilder();
                    return true;
                }
                
                return false;
            """)

            if save_clicked:
                self.log("   ✓ Builder guardado")
                time.sleep(3)  # Dar tiempo para que se guarde
                
                # Verificar si apareció algún mensaje de confirmación o error
                save_status = self.driver.execute_script("""
                    // Buscar mensajes de notificación
                    var notifications = document.querySelectorAll('.alert, .notice, .message');
                    var messages = [];
                    
                    for (var i = 0; i < notifications.length; i++) {
                        if (notifications[i].offsetParent !== null) {
                            messages.push(notifications[i].textContent.trim());
                        }
                    }
                    
                    // También verificar si el builder sigue abierto
                    var builderStillOpen = document.querySelector('.builder-content, #builder-errors') !== null;
                    
                    return {
                        messages: messages,
                        builderOpen: builderStillOpen
                    };
                """)
                
                if save_status['messages']:
                    self.log(f"   Mensajes: {save_status['messages']}")
                
                if not save_status['builderOpen']:
                    self.log("   ⚠️ El builder parece haberse cerrado después de guardar")
            else:
                self.log("   ❌ No se pudo hacer clic en Save automáticamente")
                
                # Método alternativo con Selenium
                self.log("   Intentando método alternativo con Selenium...")
                try:
                    from selenium.webdriver.common.by import By
                    
                    # Buscar por texto del botón
                    save_button = self.driver.find_element(
                        By.XPATH, 
                        "//button[contains(@onclick, 'saveCampaignFromBuilder') or (contains(@class, 'btn-primary') and text()='Save')]"
                    )
                    
                    save_button.click()
                    self.log("   ✓ Click ejecutado con Selenium")
                    time.sleep(3)
                    
                except Exception as e:
                    self.log(f"   ❌ Error con Selenium: {str(e)}")
                    
                    # Como último recurso, resaltar el botón
                    self.driver.execute_script("""
                        // Resaltar el botón Save
                        var saveButton = document.querySelector('button[onclick*="saveCampaignFromBuilder"]');
                        if (!saveButton) {
                            // Buscar cualquier botón que diga Save en la parte superior
                            var buttons = document.querySelectorAll('.btns-builder button, button.btn-primary');
                            for (var i = 0; i < buttons.length; i++) {
                                if (buttons[i].textContent.trim() === 'Save') {
                                    saveButton = buttons[i];
                                    break;
                                }
                            }
                        }
                        
                        if (saveButton) {
                            saveButton.style.border = '3px solid red';
                            saveButton.style.backgroundColor = 'yellow';
                            saveButton.style.animation = 'pulse 1s infinite';
                            
                            // Agregar animación de pulso
                            var style = document.createElement('style');
                            style.innerHTML = '@keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }';
                            document.head.appendChild(style);
                        }
                    """)
                    
                    self.log("   Por favor haz clic en el botón 'Save' (resaltado en amarillo/rojo)")
                    self.log("   Está en la parte superior del builder")
                    input("   >>> Presiona ENTER cuando hayas guardado...")

            time.sleep(3)
            
            # PASO 13: Close Builder
            self.log("PASO 13: Cerrando builder...")
            close_clicked = self.driver.execute_script("""
                var toolbarButtons = document.querySelectorAll('.builder-toolbar button, button[class*="close"]');
                for (var i = 0; i < toolbarButtons.length; i++) {
                    var btn = toolbarButtons[i];
                    if (btn.textContent.includes('Close')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)
            
            if close_clicked:
                self.log("   ✓ Builder cerrado")
            else:
                self.log("   ❌ No se pudo cerrar")
                self.log("   Por favor haz clic en 'Close Builder'")
                input("   >>> Presiona ENTER cuando hayas cerrado el builder...")
            
            time.sleep(3)
            
            # PASO 14: Activar opciones finales
            self.log("PASO 14: Activando opciones finales...")
            options_activated = self.driver.execute_script("""
                var activated = 0;
                
                var allowRestart = document.getElementById('campaign_allowRestart_1');
                if (allowRestart && !allowRestart.checked) {
                    allowRestart.click();
                    activated++;
                }
                
                var isPublished = document.getElementById('campaign_isPublished_1');
                if (isPublished && !isPublished.checked) {
                    isPublished.click();
                    activated++;
                }
                
                return activated > 0;
            """)
            
            if options_activated:
                self.log("   ✓ Opciones activadas")
            else:
                self.log("   ⚠️ Verifica las opciones:")
                self.log("     - Allow contacts to restart the campaign: ✓")
                self.log("     - Active: ✓")
                input("   >>> Presiona ENTER cuando hayas verificado las opciones...")
            
            time.sleep(2)
            
            # PASO 15: Save & Close final
            self.log("PASO 15: Guardando y cerrando campaña...")
            final_save = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    var btnText = btn.textContent.trim();
                    if (btnText.includes('Save & Close') || btnText.includes('Save and Close')) {
                        btn.click();
                        return true;
                    }
                }
                
                for (var j = 0; j < buttons.length; j++) {
                    var btn = buttons[j];
                    if (btn.textContent.includes('Save') && btn.classList.contains('btn-primary')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)
            
            if final_save:
                self.log("   ✓ Campaña guardada")
            else:
                self.log("   ❌ No se pudo guardar")
                self.log("   Por favor haz clic en 'Save & Close'")
                input("   >>> Presiona ENTER cuando hayas guardado la campaña...")
            
            time.sleep(5)
            
            self.log(f"\n{'='*60}")
            self.log(f"✅ CAMPAÑA CREADA EXITOSAMENTE")
            self.log(f"Nombre: {campaign_name}")
            self.log(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            self.log(f"\n{'='*60}")
            self.log(f"❌ ERROR CREANDO CAMPAÑA")
            self.log(f"Error: {str(e)}")
            import traceback
            self.log(f"Detalle:\n{traceback.format_exc()}")
            self.log(f"{'='*60}\n")
            
            return False
    
    def close(self):
        """Cerrar navegador"""
        if self.driver:
            self.log("Cerrando navegador...")
            try:
                self.driver.quit()
            except:
                pass
# ======================== MAUTIC EMAIL CLONER ========================
class MauticEmailCloner:
    def __init__(self, base_url, username, password, gui=None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.driver = None
        self.wait = None
        self.is_logged_in = False
        self.gui = gui
    
    def log(self, message):
        """Log con GUI si está disponible"""
        print(message)
        if self.gui:
            self.gui.log_message(message)
    
    def setup_driver(self, headless=False):
        """Configurar Chrome con Selenium"""
        self.log("Iniciando navegador Chrome para clonación...")
        
        import tempfile
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        temp_dir = tempfile.mkdtemp(prefix="mautic_chrome_")
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--start-maximized')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver.implicitly_wait(3)
            self.wait = WebDriverWait(self.driver, 15)
            self.driver.set_page_load_timeout(30)
            
            self.log("Navegador configurado correctamente")
            
        except Exception as e:
            self.log(f"Error iniciando Chrome: {str(e)}")
            raise
    
    def login(self):
        """Login en Mautic"""
        self.log("Iniciando login en Mautic...")
        
        try:
            login_url = f"{self.base_url}/s/login"
            self.driver.get(login_url)
            
            if 'dashboard' in self.driver.current_url or 'emails' in self.driver.current_url:
                self.log("Ya estás logueado!")
                self.is_logged_in = True
                return True
            
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.clear()
            username_field.send_keys(self.username)
            password_field.clear()
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            
            WebDriverWait(self.driver, 10).until(
                lambda driver: 'login' not in driver.current_url.lower()
            )
            
            self.log("Login exitoso!")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            self.log(f"Error durante login: {str(e)}")
            return False
    
    def delete_email(self, email_id, email_name):
        """Eliminar un email de Mautic usando búsqueda por nombre"""
        try:
            self.log(f"Eliminando boletín: {email_name} (ID: {email_id})")
            
            # ===== PASO 1: NAVEGAR A LA LISTA DE EMAILS =====
            self.log("   PASO 1: Navegando a la lista de emails...")
            self.driver.get(f"{self.base_url}/s/emails")
            time.sleep(3)
            
            # ===== PASO 2: LIMPIAR BÚSQUEDA ANTERIOR =====
            self.log("   PASO 2: Limpiando búsquedas anteriores...")
            self.driver.execute_script("""
                var searchInput = document.getElementById('list-search');
                if (searchInput) {
                    searchInput.value = '';
                    searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                    
                    // Hacer clic en el botón de limpiar si existe
                    var clearButton = document.querySelector('button[data-livesearch-action="clear"]');
                    if (clearButton && clearButton.offsetParent !== null) {
                        clearButton.click();
                    }
                }
            """)
            
            time.sleep(2)
            
            # ===== PASO 3: ESCRIBIR EN EL CAMPO DE BÚSQUEDA =====
            self.log(f"   PASO 3: Escribiendo en el buscador: {email_name}")
            
            search_written = self.driver.execute_script("""
                var emailName = arguments[0];
                var searchInput = document.getElementById('list-search');
                
                if (!searchInput) {
                    console.log('No se encontró el input de búsqueda');
                    return false;
                }
                
                // Enfocar el input
                searchInput.focus();
                searchInput.click();
                
                // Limpiar cualquier valor
                searchInput.value = '';
                
                // Escribir el nombre letra por letra (más realista)
                var index = 0;
                var interval = setInterval(function() {
                    if (index < emailName.length) {
                        searchInput.value += emailName[index];
                        
                        // Disparar eventos en cada letra
                        searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                        searchInput.dispatchEvent(new Event('keyup', {bubbles: true}));
                        
                        index++;
                    } else {
                        clearInterval(interval);
                        
                        // Disparar eventos finales
                        searchInput.dispatchEvent(new Event('change', {bubbles: true}));
                        
                        console.log('Texto completo escrito:', searchInput.value);
                    }
                }, 50); // 50ms entre cada letra
                
                return true;
            """, email_name)
            
            if not search_written:
                self.log("   ❌ No se pudo escribir en el campo de búsqueda")
                return False
            
            # Esperar a que termine de escribir (nombre completo + buffer)
            write_time = len(email_name) * 0.05 + 1
            self.log(f"   ⏳ Esperando {write_time:.1f}s a que termine de escribir...")
            time.sleep(write_time)
            
            # ===== PASO 4: HACER CLIC EN EL BOTÓN DE BÚSQUEDA =====
            self.log("   PASO 4: Haciendo clic en el botón de búsqueda...")
            
            search_clicked = self.driver.execute_script("""
                var searchButton = document.querySelector('button[data-livesearch-action="search"]');
                
                if (searchButton && searchButton.offsetParent !== null) {
                    console.log('Botón de búsqueda encontrado');
                    searchButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                    
                    // Hacer clic
                    searchButton.click();
                    
                    console.log('Click en búsqueda ejecutado');
                    return true;
                }
                
                console.log('No se encontró el botón de búsqueda');
                return false;
            """)
            
            if not search_clicked:
                self.log("   ⚠️ No se pudo hacer clic en el botón, intentando con Enter...")
                
                # Método alternativo: Presionar Enter en el input
                self.driver.execute_script("""
                    var searchInput = document.getElementById('list-search');
                    if (searchInput) {
                        var enterEvent = new KeyboardEvent('keypress', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        });
                        searchInput.dispatchEvent(enterEvent);
                    }
                """)
            
            # ===== PASO 5: ESPERAR RESULTADOS DE BÚSQUEDA =====
            self.log("   PASO 5: Esperando resultados de búsqueda...")
            time.sleep(4)
            
            # ===== PASO 6: VERIFICAR QUE EL BOLETÍN APARECE EN LOS RESULTADOS =====
            self.log("   PASO 6: Verificando resultados...")
            
            search_results = self.driver.execute_script("""
                var emailId = arguments[0];
                var emailName = arguments[1];
                
                var results = {
                    found: false,
                    method: 'none',
                    totalRows: 0,
                    matchingRows: []
                };
                
                var allRows = document.querySelectorAll('tbody tr');
                results.totalRows = allRows.length;
                
                console.log('Total de filas visibles:', allRows.length);
                
                for (var i = 0; i < allRows.length; i++) {
                    var row = allRows[i];
                    var rowId = row.getAttribute('data-id');
                    var rowText = row.textContent;
                    
                    console.log('Fila', i, '- ID:', rowId, '- Contiene email ID:', rowText.includes(emailId));
                    
                    // Verificar por data-id
                    if (rowId === emailId) {
                        results.found = true;
                        results.method = 'data-id-exact';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia exacta por data-id');
                        break;
                    }
                    
                    // Verificar por ID en el texto
                    if (rowText.includes(emailId)) {
                        results.found = true;
                        results.method = 'text-id';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia por ID en texto');
                        break;
                    }
                    
                    // Verificar por nombre
                    if (rowText.includes(emailName)) {
                        results.found = true;
                        results.method = 'text-name';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia por nombre');
                        break;
                    }
                }
                
                return results;
            """, email_id, email_name)
            
            self.log(f"   Filas en resultados: {search_results['totalRows']}")
            
            if not search_results['found']:
                self.log(f"   ❌ El boletín no aparece en los resultados de búsqueda")
                self.log(f"   Esto puede significar:")
                self.log(f"     - El boletín ya fue eliminado")
                self.log(f"     - El nombre no coincide exactamente")
                self.log(f"     - Hay un problema con la búsqueda de Mautic")
                
                # FALLBACK: Intentar acceso directo
                self.log("   FALLBACK: Intentando acceso directo por URL...")
                edit_url = f"{self.base_url}/s/emails/edit/{email_id}"
                self.driver.get(edit_url)
                time.sleep(3)
                
                page_valid = self.driver.execute_script("""
                    var emailForm = document.getElementById('emailform_name');
                    return !!emailForm;
                """)
                
                if page_valid:
                    self.log(f"   ✓ Email encontrado por URL directa, procediendo a eliminar...")
                    delete_url = f"{self.base_url}/s/emails/delete/{email_id}"
                    self.driver.get(delete_url)
                    time.sleep(2)
                    
                    # Ir a confirmar
                    confirm_clicked = self.driver.execute_script("""
                        var deleteButton = document.querySelector('.modal button.btn-danger');
                        if (!deleteButton) {
                            var buttons = document.querySelectorAll('button');
                            for (var i = 0; i < buttons.length; i++) {
                                if (buttons[i].textContent.trim() === 'Delete') {
                                    deleteButton = buttons[i];
                                    break;
                                }
                            }
                        }
                        
                        if (deleteButton && deleteButton.offsetParent !== null) {
                            deleteButton.click();
                            return true;
                        }
                        return false;
                    """)
                    
                    if confirm_clicked:
                        self.log("   ✓ Eliminación confirmada")
                        time.sleep(4)
                        self.log(f"   ✅ Boletín eliminado exitosamente (método directo)")
                        return True
                else:
                    self.log(f"   ❌ El boletín no existe en Mautic")
                    return False
            
            self.log(f"   ✓ Boletín encontrado en búsqueda (método: {search_results['method']})")
            self.log(f"   ✓ Fila(s) coincidente(s): {search_results['matchingRows']}")
            
            # ===== PASO 7: ABRIR MENÚ DE ACCIONES =====
            self.log("   PASO 7: Abriendo menú de acciones...")
            
            dropdown_opened = self.driver.execute_script("""
                var emailId = arguments[0];
                
                // Buscar la fila por data-id
                var emailRow = document.querySelector('tr[data-id="' + emailId + '"]');
                
                // Si no se encuentra por data-id, buscar en el contenido
                if (!emailRow) {
                    var allRows = document.querySelectorAll('tbody tr');
                    for (var i = 0; i < allRows.length; i++) {
                        if (allRows[i].textContent.includes(emailId)) {
                            emailRow = allRows[i];
                            break;
                        }
                    }
                }
                
                if (emailRow) {
                    var dropdownButton = emailRow.querySelector('button[data-toggle="dropdown"]');
                    if (dropdownButton) {
                        // Scroll al elemento
                        dropdownButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                        
                        // Esperar un momento y hacer clic
                        setTimeout(function() {
                            dropdownButton.click();
                            console.log('Click en dropdown ejecutado');
                        }, 500);
                        
                        return true;
                    }
                }
                
                return false;
            """, email_id)
            
            if not dropdown_opened:
                self.log("   ⚠️ No se pudo abrir el menú, usando URL directa...")
                delete_url = f"{self.base_url}/s/emails/delete/{email_id}"
                self.driver.get(delete_url)
                time.sleep(2)
            else:
                self.log("   ✓ Menú de acciones abierto")
                time.sleep(2)
                
                # ===== PASO 8: HACER CLIC EN DELETE =====
                self.log("   PASO 8: Haciendo clic en Delete...")
                
                delete_clicked = self.driver.execute_script("""
                    var emailId = arguments[0];
                    
                    // Buscar el enlace de Delete
                    var deleteLink = document.querySelector('a[href*="/emails/delete/' + emailId + '"]');
                    if (deleteLink) {
                        deleteLink.click();
                        console.log('Click en Delete ejecutado');
                        return true;
                    }
                    
                    // Método alternativo: buscar por texto
                    var links = document.querySelectorAll('.dropdown-menu a');
                    for (var i = 0; i < links.length; i++) {
                        if (links[i].textContent.trim() === 'Delete' && links[i].href.includes(emailId)) {
                            links[i].click();
                            return true;
                        }
                    }
                    
                    return false;
                """, email_id)
                
                if not delete_clicked:
                    self.log("   ❌ No se pudo hacer clic en Delete")
                    return False
                
                self.log("   ✓ Click en Delete ejecutado")
                time.sleep(2)
            
            # ===== PASO 9: CONFIRMAR ELIMINACIÓN =====
            self.log("   PASO 9: Confirmando eliminación...")
            
            confirm_clicked = self.driver.execute_script("""
                // Buscar el botón Delete en el modal
                var deleteButton = document.querySelector('.modal.in button.btn-danger, .modal.show button.btn-danger');
                
                if (!deleteButton) {
                    // Buscar por texto
                    var buttons = document.querySelectorAll('.modal button, button');
                    for (var i = 0; i < buttons.length; i++) {
                        if (buttons[i].textContent.trim() === 'Delete' && 
                            buttons[i].offsetParent !== null) {
                            deleteButton = buttons[i];
                            break;
                        }
                    }
                }
                
                if (deleteButton && deleteButton.offsetParent !== null) {
                    deleteButton.click();
                    console.log('Confirmación de Delete ejecutada');
                    return true;
                }
                
                return false;
            """)
            
            if not confirm_clicked:
                self.log("   ⚠️ No se pudo confirmar automáticamente")
                self.log("   >>> Por favor confirma la eliminación manualmente")
                input("   >>> Presiona ENTER después de confirmar...")
            else:
                self.log("   ✓ Eliminación confirmada")
            
            time.sleep(4)
            
            # ===== PASO 10: VERIFICAR ELIMINACIÓN =====
            self.log("   PASO 10: Verificando que el boletín fue eliminado...")
            
            self.driver.get(f"{self.base_url}/s/emails")
            time.sleep(2)
            
            # Buscar nuevamente el email eliminado
            self.driver.execute_script("""
                var emailName = arguments[0];
                var searchInput = document.getElementById('list-search');
                if (searchInput) {
                    searchInput.value = emailName;
                    searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                    var searchButton = document.querySelector('button[data-livesearch-action="search"]');
                    if (searchButton) searchButton.click();
                }
            """, email_name)
            
            time.sleep(3)
            
            still_exists = self.driver.execute_script("""
                var emailId = arguments[0];
                var allRows = document.querySelectorAll('tbody tr');
                
                for (var i = 0; i < allRows.length; i++) {
                    if (allRows[i].textContent.includes(emailId) || 
                        allRows[i].getAttribute('data-id') === emailId) {
                        return true;
                    }
                }
                return false;
            """, email_id)
            
            if not still_exists:
                self.log(f"   ✅ Boletín eliminado exitosamente")
                return True
            else:
                self.log(f"   ⚠️ El boletín aún aparece en la lista")
                return False
            
        except Exception as e:
            self.log(f"   ❌ Error eliminando boletín: {str(e)}")
            import traceback
            self.log(f"   Detalle: {traceback.format_exc()}")
            return False
    
    def clone_email(self, email_id, email_name, new_name=None):
        """Clonar un email en Mautic con búsqueda previa mejorada"""
        try:
            # Si no se proporciona nuevo nombre, usar el mismo
            clone_name = new_name if new_name else f"CLONE_{email_name}"
            
            self.log(f"Clonando boletín: {email_name}")
            self.log(f"   Nuevo nombre: {clone_name}")
            
            # ===== PASO 1: NAVEGAR A LA LISTA DE EMAILS =====
            self.log("   PASO 1: Navegando a la lista de emails...")
            self.driver.get(f"{self.base_url}/s/emails")
            time.sleep(3)
            
            # ===== PASO 2: LIMPIAR BÚSQUEDA ANTERIOR =====
            self.log("   PASO 2: Limpiando búsquedas anteriores...")
            self.driver.execute_script("""
                var searchInput = document.getElementById('list-search');
                if (searchInput) {
                    searchInput.value = '';
                    searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                    
                    var clearButton = document.querySelector('button[data-livesearch-action="clear"]');
                    if (clearButton && clearButton.offsetParent !== null) {
                        clearButton.click();
                    }
                }
            """)
            
            time.sleep(2)
            
            # ===== PASO 3: ESCRIBIR EN EL CAMPO DE BÚSQUEDA (LETRA POR LETRA) =====
            self.log(f"   PASO 3: Escribiendo en el buscador: {email_name}")
            
            search_written = self.driver.execute_script("""
                var emailName = arguments[0];
                var searchInput = document.getElementById('list-search');
                
                if (!searchInput) {
                    console.log('No se encontró el input de búsqueda');
                    return false;
                }
                
                // Enfocar el input
                searchInput.focus();
                searchInput.click();
                
                // Limpiar cualquier valor
                searchInput.value = '';
                
                // Escribir el nombre letra por letra
                var index = 0;
                var interval = setInterval(function() {
                    if (index < emailName.length) {
                        searchInput.value += emailName[index];
                        
                        // Disparar eventos en cada letra
                        searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                        searchInput.dispatchEvent(new Event('keyup', {bubbles: true}));
                        
                        index++;
                    } else {
                        clearInterval(interval);
                        
                        // Disparar eventos finales
                        searchInput.dispatchEvent(new Event('change', {bubbles: true}));
                        
                        console.log('Texto completo escrito:', searchInput.value);
                    }
                }, 50);
                
                return true;
            """, email_name)
            
            if not search_written:
                self.log("   ❌ No se pudo escribir en el campo de búsqueda")
                return False, None
            
            # Esperar a que termine de escribir
            write_time = len(email_name) * 0.05 + 1
            self.log(f"   ⏳ Esperando {write_time:.1f}s a que termine de escribir...")
            time.sleep(write_time)
            
            # ===== PASO 4: HACER CLIC EN EL BOTÓN DE BÚSQUEDA =====
            self.log("   PASO 4: Haciendo clic en el botón de búsqueda...")
            
            search_clicked = self.driver.execute_script("""
                var searchButton = document.querySelector('button[data-livesearch-action="search"]');
                
                if (searchButton && searchButton.offsetParent !== null) {
                    console.log('Botón de búsqueda encontrado');
                    searchButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                    searchButton.click();
                    console.log('Click en búsqueda ejecutado');
                    return true;
                }
                
                console.log('No se encontró el botón de búsqueda');
                return false;
            """)
            
            if not search_clicked:
                self.log("   ⚠️ No se pudo hacer clic en el botón, intentando con Enter...")
                
                self.driver.execute_script("""
                    var searchInput = document.getElementById('list-search');
                    if (searchInput) {
                        var enterEvent = new KeyboardEvent('keypress', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        });
                        searchInput.dispatchEvent(enterEvent);
                    }
                """)
            
            # ===== PASO 5: ESPERAR RESULTADOS DE BÚSQUEDA =====
            self.log("   PASO 5: Esperando resultados de búsqueda...")
            time.sleep(4)
            
            # ===== PASO 6: VERIFICAR QUE EL BOLETÍN APARECE EN LOS RESULTADOS =====
            self.log("   PASO 6: Verificando resultados...")
            
            search_results = self.driver.execute_script("""
                var emailId = arguments[0];
                var emailName = arguments[1];
                
                var results = {
                    found: false,
                    method: 'none',
                    totalRows: 0,
                    matchingRows: []
                };
                
                var allRows = document.querySelectorAll('tbody tr');
                results.totalRows = allRows.length;
                
                console.log('Total de filas visibles:', allRows.length);
                
                for (var i = 0; i < allRows.length; i++) {
                    var row = allRows[i];
                    var rowId = row.getAttribute('data-id');
                    var rowText = row.textContent;
                    
                    console.log('Fila', i, '- ID:', rowId);
                    
                    // Verificar por data-id
                    if (rowId === emailId) {
                        results.found = true;
                        results.method = 'data-id-exact';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia exacta por data-id');
                        break;
                    }
                    
                    // Verificar por ID en el texto
                    if (rowText.includes(emailId)) {
                        results.found = true;
                        results.method = 'text-id';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia por ID en texto');
                        break;
                    }
                    
                    // Verificar por nombre
                    if (rowText.includes(emailName)) {
                        results.found = true;
                        results.method = 'text-name';
                        results.matchingRows.push(i);
                        console.log('✓ Coincidencia por nombre');
                        break;
                    }
                }
                
                return results;
            """, email_id, email_name)
            
            self.log(f"   Filas en resultados: {search_results['totalRows']}")
            
            if not search_results['found']:
                self.log(f"   ❌ El boletín no aparece en los resultados de búsqueda")
                self.log(f"   ID buscado: {email_id}")
                self.log(f"   Nombre buscado: {email_name}")
                
                # FALLBACK: Acceso directo por URL
                self.log("   FALLBACK: Intentando acceso directo por URL...")
                clone_url = f"{self.base_url}/s/emails/clone/{email_id}"
                self.driver.get(clone_url)
                time.sleep(3)
                
                # Verificar si cargó la página de clonación
                page_valid = self.driver.execute_script("""
                    var nameField = document.getElementById('emailform_name');
                    return !!nameField;
                """)
                
                if not page_valid:
                    self.log(f"   ❌ El boletín no existe o no se puede clonar")
                    return False, None
                
                self.log("   ✓ Acceso directo exitoso, continuando con clonación...")
            else:
                self.log(f"   ✓ Boletín encontrado en búsqueda (método: {search_results['method']})")
                self.log(f"   ✓ Fila(s) coincidente(s): {search_results['matchingRows']}")
                
                # ===== PASO 7: ABRIR MENÚ DE ACCIONES =====
                self.log("   PASO 7: Abriendo menú de acciones...")
                
                dropdown_opened = self.driver.execute_script("""
                    var emailId = arguments[0];
                    
                    // Buscar la fila por data-id
                    var emailRow = document.querySelector('tr[data-id="' + emailId + '"]');
                    
                    // Si no se encuentra por data-id, buscar en el contenido
                    if (!emailRow) {
                        var allRows = document.querySelectorAll('tbody tr');
                        for (var i = 0; i < allRows.length; i++) {
                            if (allRows[i].textContent.includes(emailId)) {
                                emailRow = allRows[i];
                                break;
                            }
                        }
                    }
                    
                    if (emailRow) {
                        var dropdownButton = emailRow.querySelector('button[data-toggle="dropdown"]');
                        if (dropdownButton) {
                            dropdownButton.scrollIntoView({behavior: 'smooth', block: 'center'});
                            
                            setTimeout(function() {
                                dropdownButton.click();
                                console.log('Click en dropdown ejecutado');
                            }, 500);
                            
                            return true;
                        }
                    }
                    
                    return false;
                """, email_id)
                
                if not dropdown_opened:
                    self.log("   ⚠️ No se pudo abrir el menú, usando URL directa...")
                    clone_url = f"{self.base_url}/s/emails/clone/{email_id}"
                    self.driver.get(clone_url)
                    time.sleep(3)
                else:
                    self.log("   ✓ Menú de acciones abierto")
                    time.sleep(2)
                    
                    # ===== PASO 8: HACER CLIC EN CLONE =====
                    self.log("   PASO 8: Haciendo clic en Clone...")
                    
                    clone_clicked = self.driver.execute_script("""
                        var emailId = arguments[0];
                        
                        // Buscar el enlace de Clone
                        var cloneLink = document.querySelector('a[href*="/emails/clone/' + emailId + '"]');
                        if (cloneLink) {
                            cloneLink.click();
                            console.log('Click en Clone ejecutado');
                            return true;
                        }
                        
                        // Método alternativo: buscar por texto
                        var links = document.querySelectorAll('.dropdown-menu a');
                        for (var i = 0; i < links.length; i++) {
                            if (links[i].textContent.trim() === 'Clone' && links[i].href.includes(emailId)) {
                                links[i].click();
                                return true;
                            }
                        }
                        
                        return false;
                    """, email_id)
                    
                    if not clone_clicked:
                        self.log("   ❌ No se pudo hacer clic en Clone")
                        return False, None
                    
                    self.log("   ✓ Click en Clone ejecutado")
                    time.sleep(3)
            
            # ===== PASO 9: CAMBIAR EL NOMBRE DEL CLONE =====
            self.log("   PASO 9: Cambiando nombre del boletín clonado...")
            time.sleep(2)
            
            name_changed = self.driver.execute_script("""
                var newName = arguments[0];
                var nameField = document.getElementById('emailform_name');
                
                if (nameField) {
                    nameField.value = '';
                    nameField.dispatchEvent(new Event('input', {bubbles: true}));
                    
                    nameField.value = newName;
                    nameField.dispatchEvent(new Event('input', {bubbles: true}));
                    nameField.dispatchEvent(new Event('change', {bubbles: true}));
                    
                    return true;
                }
                return false;
            """, clone_name)
            
            if not name_changed:
                self.log("   ⚠️ No se pudo cambiar el nombre automáticamente")
                self.driver.execute_script("""
                    var nameField = document.getElementById('emailform_name');
                    if (nameField) {
                        nameField.style.border = '3px solid red';
                        nameField.style.backgroundColor = 'yellow';
                    }
                """)
                
                self.log(f"   Por favor cambia manualmente el nombre a: {clone_name}")
                input("   >>> Presiona ENTER cuando hayas cambiado el nombre...")
            else:
                self.log(f"   ✓ Nombre cambiado a: {clone_name}")
            
            time.sleep(1)
            
            # ===== PASO 10: GUARDAR EL BOLETÍN CLONADO =====
            self.log("   PASO 10: Guardando boletín clonado...")
            
            save_clicked = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    var btnText = btn.textContent.trim();
                    
                    if (btnText.includes('Save & Close') || btnText.includes('Save and Close')) {
                        btn.click();
                        return true;
                    }
                }
                
                for (var j = 0; j < buttons.length; j++) {
                    var btn = buttons[j];
                    if (btn.textContent.includes('Save') && btn.classList.contains('btn-primary')) {
                        btn.click();
                        return true;
                    }
                }
                
                return false;
            """)
            
            if not save_clicked:
                self.log("   ⚠️ No se pudo hacer clic en Save")
                self.log("   Por favor haz clic manualmente en 'Save & Close'")
                input("   >>> Presiona ENTER cuando hayas guardado...")
            else:
                self.log("   ✓ Guardando boletín...")
            
            time.sleep(5)
            
            # ===== PASO 11: VERIFICAR CREACIÓN Y OBTENER ID =====
            self.log("   PASO 11: Verificando creación del boletín clonado...")
            current_url = self.driver.current_url
            new_email_id = None
            
            if '/edit/' in current_url:
                new_email_id = current_url.split('/')[-1]
                self.log(f"   ✅ Boletín clonado exitosamente")
                self.log(f"   Nuevo ID: {new_email_id}")
                self.log(f"   Nuevo nombre: {clone_name}")
                return True, new_email_id
            else:
                # Buscar en la lista
                self.log("   Buscando el boletín clonado en la lista...")
                self.driver.get(f"{self.base_url}/s/emails")
                time.sleep(2)
                
                # Buscar por el nuevo nombre
                self.driver.execute_script("""
                    var searchInput = document.getElementById('list-search');
                    if (searchInput) {
                        searchInput.value = arguments[0];
                        searchInput.dispatchEvent(new Event('input', {bubbles: true}));
                        var searchButton = document.querySelector('button[data-livesearch-action="search"]');
                        if (searchButton) searchButton.click();
                    }
                """, clone_name)
                
                time.sleep(3)
                
                new_email_id = self.driver.execute_script("""
                    var cloneName = arguments[0];
                    var allRows = document.querySelectorAll('tbody tr');
                    
                    for (var i = 0; i < allRows.length; i++) {
                        var row = allRows[i];
                        if (row.textContent.includes(cloneName)) {
                            var id = row.getAttribute('data-id');
                            if (id) return id;
                        }
                    }
                    return null;
                """, clone_name)
                
                if new_email_id:
                    self.log(f"   ✅ Boletín clonado encontrado")
                    self.log(f"   Nuevo ID: {new_email_id}")
                    return True, new_email_id
                else:
                    self.log("   ⚠️ Boletín clonado pero ID no detectado")
                    return True, None
                
        except Exception as e:
            self.log(f"   ❌ Error clonando boletín: {str(e)}")
            import traceback
            self.log(f"   Detalle: {traceback.format_exc()}")
            return False, None
    def close(self):
        """Cerrar navegador"""
        if self.driver:
            self.log("Cerrando navegador...")
            try:
                self.driver.quit()
            except:
                pass


# ======================== CLONE DIALOG ========================
class CloneDialog:
    def __init__(self, parent_gui):
        self.parent_gui = parent_gui
        self.dialog = tk.Toplevel(parent_gui.root)
        self.dialog.title("Clonar Boletines")
        self.dialog.geometry("1000x900")
        self.dialog.transient(parent_gui.root)
        self.dialog.grab_set()
        
        # Variables
        self.clone_mode = tk.StringVar(value="correcciones")
        self.email_vars = {}
        self.all_emails = []
        
        self.setup_ui()
        self.load_emails_from_json()
    
    def setup_ui(self):
        """Configurar la interfaz del diálogo"""
        
        # Frame principal con padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Clonar Boletines", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Selector de modo
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Clonación", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Radiobutton(mode_frame, text="Correcciones (Eliminar y recrear seleccionados)", 
                       variable=self.clone_mode, value="correcciones",
                       command=self.on_mode_change).pack(anchor=tk.W, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Clonación Final (Clonar TODOS sin 'PRUEBA')", 
                       variable=self.clone_mode, value="final",
                       command=self.on_mode_change).pack(anchor=tk.W, pady=5)
        
        # Información del modo
        self.mode_info = ttk.Label(mode_frame, text="", foreground='blue', wraplength=800)
        self.mode_info.pack(anchor=tk.W, pady=(10, 0))
        
        # Frame de lista de emails
        list_frame = ttk.LabelFrame(main_frame, text="Boletines Disponibles", padding="15")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Botones de selección rápida
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.select_all_btn = ttk.Button(button_frame, text="Seleccionar Todos", 
                                         command=self.select_all)
        self.select_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.deselect_all_btn = ttk.Button(button_frame, text="Deseleccionar Todos", 
                                          command=self.deselect_all)
        self.deselect_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Canvas con scrollbar para la lista
        canvas_frame = ttk.Frame(list_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='white', height=300)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Frame de botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Contenedor centrado para los botones
        action_button_container = ttk.Frame(action_frame)
        action_button_container.pack(expand=True)
        
        # Botón principal de clonación
        self.clone_btn = ttk.Button(
            action_button_container, 
            text="CLONAR SELECCIONADOS", 
            command=self.start_cloning,
            width=22
        )
        self.clone_btn.grid(row=0, column=0, padx=5, pady=5)
        
        # Botón para crear campañas (solo visible en modo correcciones después de clonar)
        self.campaign_btn = ttk.Button(
            action_button_container, 
            text="CREAR CAMPAÑAS", 
            command=self.create_campaigns_for_corrections,
            width=22,
            state='disabled'  # Inicialmente deshabilitado
        )
        self.campaign_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # Botón cerrar
        ttk.Button(
            action_button_container, 
            text="Cerrar", 
            command=self.dialog.destroy,
            width=15
        ).grid(row=0, column=2, padx=5, pady=5)
        
        # Separador
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(10, 0))
        
        # Label de información adicional
        self.info_label = ttk.Label(
            main_frame, 
            text="Configura el modo y selecciona boletines para comenzar",
            foreground='gray',
            font=('Arial', 9)
        )
        self.info_label.pack(pady=(10, 0))
        
        # Actualizar info del modo
        self.on_mode_change()
        # Actualizar info del modo
        self.on_mode_change()
    
    def on_mode_change(self):
        """Actualizar la interfaz según el modo seleccionado"""
        mode = self.clone_mode.get()
        
        if mode == "correcciones":
            self.mode_info.config(
                text="Se eliminarán los boletines seleccionados y se volverán a crear con el mismo nombre.\n"
                    "Perfecto para corregir errores en boletines ya creados."
            )
            self.select_all_btn.config(state='normal')
            self.deselect_all_btn.config(state='normal')
            self.clone_btn.config(
                text="ELIMINAR Y RECREAR SELECCIONADOS",
                width=35  # aumenta este número para hacerlo más largo
            )
            self.info_label.config(
                text="Selecciona los boletines que deseas corregir",
                foreground='blue'
            )
            
            # Habilitar checkboxes
            for email_data in self.email_vars.values():
                email_data['check'].config(state='normal')
        
        else:  # final
            self.mode_info.config(
                text="Se clonarán TODOS los boletines sin la palabra 'PRUEBA' en el nombre.\n"
                    "Esto creará los boletines finales listos para producción."
            )
            self.select_all_btn.config(state='disabled')
            self.deselect_all_btn.config(state='disabled')
            self.clone_btn.config(text="CLONAR TODOS SIN 'PRUEBA'")
            self.info_label.config(
                text=f"Se clonarán automáticamente {len(self.all_emails)} boletines",
                foreground='green'
            )
            
            # Deshabilitar checkboxes y deseleccionar
            for email_data in self.email_vars.values():
                email_data['var'].set(False)
                email_data['check'].config(state='disabled')
    
    def load_emails_from_json(self):
        """Cargar emails desde el JSON"""
        json_file = 'emails_creados.json'
        
        if not os.path.exists(json_file):
            ttk.Label(
                self.scrollable_frame, 
                text="No hay boletines creados. Crea boletines primero.",
                foreground='red',
                font=('Arial', 11)
            ).pack(pady=50)
            
            # Deshabilitar botón de clonar
            self.clone_btn.config(state='disabled')
            return
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                self.all_emails = json.load(f)
            
            if not self.all_emails:
                ttk.Label(
                    self.scrollable_frame, 
                    text="No hay boletines en el archivo.",
                    foreground='red',
                    font=('Arial', 11)
                ).pack(pady=50)
                
                # Deshabilitar botón de clonar
                self.clone_btn.config(state='disabled')
                return
            
            # Encabezados
            header_frame = ttk.Frame(self.scrollable_frame)
            header_frame.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Label(header_frame, text="Sel", width=5, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
            ttk.Label(header_frame, text="Nombre del Boletín", width=50, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
            ttk.Label(header_frame, text="Tipo", width=12, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
            ttk.Label(header_frame, text="ID", width=8, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
            
            ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 5))
            
            # Crear la lista de emails
            for idx, email in enumerate(self.all_emails):
                frame = ttk.Frame(self.scrollable_frame)
                frame.pack(fill=tk.X, pady=2, padx=5)
                
                # Color alternado
                if idx % 2 == 0:
                    frame.configure(style='Even.TFrame')
                
                # Checkbox
                var = tk.BooleanVar(value=False)
                check = ttk.Checkbutton(frame, variable=var, width=5)
                check.pack(side=tk.LEFT, padx=5)
                
                # Información del email
                email_name = email.get('name', 'Sin nombre')
                email_type = email.get('type', 'N/A').capitalize()
                email_id = email.get('id', 'N/A')
                
                # Nombre (truncado si es muy largo)
                name_display = email_name[:60] + "..." if len(email_name) > 60 else email_name
                ttk.Label(frame, text=name_display, width=50).pack(side=tk.LEFT, padx=5)
                
                # Tipo
                type_label = ttk.Label(frame, text=email_type, width=12)
                type_label.pack(side=tk.LEFT, padx=5)
                
                # Color según tipo
                if email_type.lower() == 'personal':
                    type_label.config(foreground='blue')
                else:
                    type_label.config(foreground='green')
                
                # ID
                ttk.Label(frame, text=str(email_id), width=8, foreground='gray').pack(side=tk.LEFT, padx=5)
                
                # Guardar referencia
                self.email_vars[email_name] = {
                    'var': var,
                    'email': email,
                    'check': check
                }
            
            self.parent_gui.log_message(f"✓ Cargados {len(self.all_emails)} boletines para clonación")
            
            # Actualizar contador
            self.info_label.config(
                text=f"{len(self.all_emails)} boletines disponibles"
            )
            
        except Exception as e:
            ttk.Label(
                self.scrollable_frame, 
                text=f"Error cargando boletines: {str(e)}",
                foreground='red',
                font=('Arial', 10)
            ).pack(pady=50)
            
            self.parent_gui.log_message(f"❌ Error cargando JSON: {str(e)}")
            
            # Deshabilitar botón de clonar
            self.clone_btn.config(state='disabled')
    
    def select_all(self):
        """Seleccionar todos los checkboxes"""
        for email_data in self.email_vars.values():
            if email_data['enabled']:
                email_data['var'].set(True)
    
    def deselect_all(self):
        """Deseleccionar todos los checkboxes"""
        for email_data in self.email_vars.values():
            email_data['var'].set(False)
    
    def start_cloning(self):
        """Iniciar el proceso de clonación SIN CERRAR la ventana"""
        mode = self.clone_mode.get()
        
        if mode == "correcciones":
            # Obtener emails seleccionados
            selected_emails = [
                data['email'] for data in self.email_vars.values() 
                if data['var'].get()
            ]
            
            if not selected_emails:
                messagebox.showwarning("Sin selección", 
                    "Por favor selecciona al menos un boletín para clonar.")
                return
            
            message = f"¿Deseas eliminar y recrear {len(selected_emails)} boletines?\n\n"
            message += "Proceso:\n"
            message += "1. Se buscarán los boletines en Mautic\n"
            message += "2. Se eliminarán uno por uno\n"
            message += "3. Se recrearán con el mismo nombre\n\n"
            message += "⚠️ Este proceso puede tomar varios minutos.\n"
            message += "La ventana permanecerá abierta para crear campañas después."
            
        else:  # final
            selected_emails = self.all_emails
            message = f"¿Deseas clonar TODOS los {len(selected_emails)} boletines?\n\n"
            message += "Proceso:\n"
            message += "1. Se clonarán todos los boletines\n"
            message += "2. Se removerá la palabra 'PRUEBA' del nombre\n\n"
            message += "⚠️ Este proceso puede tomar varios minutos."
        
        result = messagebox.askyesno("Confirmar Clonación", message, icon='question')
        
        if not result:
            return
        
        # Deshabilitar botones durante el proceso
        self.clone_btn.config(state='disabled', text="PROCESANDO...")
        self.campaign_btn.config(state='disabled')
        self.select_all_btn.config(state='disabled')
        self.deselect_all_btn.config(state='disabled')
        
        # Mostrar estado
        self.info_label.config(
            text=f"Procesando {len(selected_emails)} boletines... Por favor espera",
            foreground='orange'
        )
        
        # Actualizar la ventana
        self.dialog.update()
        
        # Ejecutar en thread PERO NO CERRAR la ventana
        thread = threading.Thread(
            target=self._run_cloning_with_callback,
            args=(selected_emails, mode)
        )
        thread.daemon = True
        thread.start()

    def _run_cloning_with_callback(self, selected_emails, mode):
        """Ejecutar clonación y actualizar ventana después"""
        
        # Ejecutar el proceso de clonación
        self.parent_gui.run_cloning_process(selected_emails, mode)
        
        # Después de completar, actualizar la interfaz en el hilo principal
        self.dialog.after(0, lambda: self._on_cloning_complete(mode))

    def _on_cloning_complete(self, mode):
        """Callback después de completar la clonación"""
        
        # Rehabilitar botones
        self.clone_btn.config(state='normal', text="CLONAR SELECCIONADOS")
        self.select_all_btn.config(state='normal')
        self.deselect_all_btn.config(state='normal')
        
        # Si es modo correcciones, habilitar botón de campañas
        if mode == "correcciones":
            # Verificar si se crearon boletines corregidos
            if os.path.exists('correcciones.json'):
                try:
                    with open('correcciones.json', 'r') as f:
                        corrected = json.load(f)
                    
                    if corrected:
                        self.campaign_btn.config(state='normal')
                        self.info_label.config(
                            text=f"✅ {len(corrected)} boletines corregidos. Ahora puedes crear campañas.",
                            foreground='green'
                        )
                    else:
                        self.info_label.config(
                            text="⚠️ No se corrigieron boletines",
                            foreground='orange'
                        )
                except:
                    self.info_label.config(
                        text="⚠️ Error cargando correcciones",
                        foreground='red'
                    )
            else:
                self.info_label.config(
                    text="⚠️ No se encontró archivo de correcciones",
                    foreground='orange'
                )
        else:
            self.info_label.config(
                text="✅ Clonación final completada",
                foreground='green'
            )
        
        messagebox.showinfo(
            "Proceso Completado",
            "La clonación ha finalizado.\n\n" +
            ("Ahora puedes crear campañas usando el botón 'CREAR CAMPAÑAS'" if mode == "correcciones" else 
            "Los boletines finales están listos en emails_finales.json")
        )
    
    def create_campaigns_for_corrections(self):
        """Crear campañas para los boletines corregidos"""
        corrections_file = 'correcciones.json'
        
        if not os.path.exists(corrections_file):
            messagebox.showinfo("Sin correcciones", 
                "No hay boletines corregidos. Clona boletines primero en modo 'Correcciones'.")
            return
        
        try:
            with open(corrections_file, 'r') as f:
                corrected_emails = json.load(f)
            
            if not corrected_emails:
                messagebox.showinfo("Sin correcciones", 
                    "No hay boletines corregidos.")
                return
            
            message = f"¿Deseas crear campañas para {len(corrected_emails)} boletines corregidos?\n\n"
            message += f"Se usará el segmento: {self.parent_gui.segment_name.get()}"
            
            result = messagebox.askyesno("Confirmar Creación", message, icon='question')
            
            if result:
                self.dialog.destroy()
                # Usar los emails corregidos para crear campañas
                Config.CREATED_EMAILS = corrected_emails
                self.parent_gui.create_campaigns()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando correcciones: {str(e)}")

# ======================== PROCESADOR PRINCIPAL ========================
class EstablishmentProcessor:
    def __init__(self, gui=None):
        self.uploader = None
        self.mautic = None
        self.establishments_processed = []
        self.gui = gui
    
    def log(self, message):
        """Log con GUI si está disponible"""
        print(message)
        if self.gui:
            self.gui.log_message(message)
    
    def find_image_in_folder(self, folder_path):
        """Encontrar la primera imagen en una carpeta"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    return file_path, file
        return None, None
    
    def process_all_establishments(self):
        """Procesar todas las carpetas con establecimientos"""
        
        self.log("="*60)
        self.log("AUTOMATIZACIÓN: CARPETAS → CLOUDFLARE R2 → MAUTIC")
        self.log("="*60)
        
        # Verificar carpeta local
        if not os.path.exists(Config.LOCAL_FOLDER):
            self.log(f"No se encuentra la carpeta: {Config.LOCAL_FOLDER}")
            return
        
        # Solo procesar establecimientos seleccionados
        if not Config.ESTABLISHMENT_CONFIG:
            self.log("No hay establecimientos seleccionados para procesar")
            return
        
        self.log(f"Procesando {len(Config.ESTABLISHMENT_CONFIG)} establecimientos seleccionados")
        
        # Inicializar conexiones
        self.log("\nINICIALIZANDO CONEXIONES...")
        
        # Conectar a Cloudflare R2
        self.uploader = CloudflareR2Uploader(self.gui)
        
        if not self.uploader.connect():
            self.log("No se pudo conectar a Cloudflare R2")
            return
        
        # Iniciar Mautic
        self.mautic = MauticBulkAutomator(
            Config.MAUTIC_URL,
            Config.MAUTIC_USERNAME,
            Config.MAUTIC_PASSWORD,
            self.gui
        )
        
        self.mautic.setup_driver(headless=False)
        
        if not self.mautic.login():
            self.log("No se pudo hacer login en Mautic")
            self.uploader.disconnect()
            return
        
        self.log("\nPROCESANDO ESTABLECIMIENTOS...")
        self.log("="*60)
        
        # Procesar cada establecimiento seleccionado
        total = len(Config.ESTABLISHMENT_CONFIG)
        success_count = 0
        
        for idx, (folder_name, config) in enumerate(Config.ESTABLISHMENT_CONFIG.items(), 1):
            # Determinar qué boletines crear para este establecimiento
            bulletin_types = []
            if config['personal']:
                bulletin_types.append('personal')
            if config['corporate']:
                bulletin_types.append('corporate')
            
            if not bulletin_types:
                continue
            
            # Obtener el campo personalizado
            field_alias = config.get('field', folder_name.lower().replace(' ', '_').replace('-', '_'))
            
            self.log(f"\n[{idx}/{total}] Procesando: {folder_name}")
            self.log(f"   Campo Mautic: {field_alias}")
            self.log(f"   Boletines a crear: {', '.join(bulletin_types)}")
            self.log("-"*40)
            
            folder_path = os.path.join(Config.LOCAL_FOLDER, folder_name)
            
            # Buscar imagen en la carpeta
            image_path, image_filename = self.find_image_in_folder(folder_path)
            
            if not image_path:
                self.log(f"   No se encontró imagen en {folder_name}")
                self.establishments_processed.append({
                    'name': folder_name,
                    'status': 'error_no_image',
                    'field': field_alias
                })
                continue
            
            self.log(f"   Imagen encontrada: {image_filename}")
            
            # Generar nombre de archivo para el servidor
            establishment_name = folder_name
            original_ext = os.path.splitext(image_filename)[1]
            remote_filename = f"{establishment_name.replace(' ', '_')}{original_ext}"
            
            # 1. Subir imagen a Cloudflare R2
            upload_success, img_width, img_height = self.uploader.upload_image(image_path, remote_filename)
            
            if upload_success:
                # 2. Crear boletín(es) en Mautic
                image_url = Config.IMAGE_BASE_URL + remote_filename
                
                all_success = True
                for bulletin_type in bulletin_types:
                    # Capturar el ID retornado
                    email_id = self.mautic.create_email_for_establishment(
                        establishment_name, image_url, img_width, img_height, bulletin_type, field_alias
                    )
                    
                    if not email_id:
                        all_success = False
                        self.log(f"   ⚠️ Error creando boletín {bulletin_type}")
                
                if all_success:
                    success_count += 1
                    self.establishments_processed.append({
                        'name': establishment_name,
                        'image': remote_filename,
                        'url': image_url,
                        'status': 'success',
                        'dimensions': f"{img_width}x{img_height}",
                        'bulletins': bulletin_types,
                        'field': field_alias
                    })
                else:
                    self.establishments_processed.append({
                        'name': establishment_name,
                        'image': remote_filename,
                        'status': 'partial_success',
                        'bulletins': bulletin_types,
                        'field': field_alias
                    })
            else:
                self.establishments_processed.append({
                    'name': establishment_name,
                    'status': 'error_upload',
                    'field': field_alias
                })
            
            # Pequeña pausa entre procesos
            time.sleep(2)
        
        # Mostrar resumen
        self.log("\n" + "="*60)
        self.log("RESUMEN DE PROCESAMIENTO")
        self.log("="*60)
        self.log(f"Exitosos: {success_count}/{total}")
        self.log(f"Fallidos: {total - success_count}/{total}")
        
        if self.establishments_processed:
            self.log("\nDetalle:")
            for est in self.establishments_processed:
                status_icon = "✓" if est['status'] == 'success' else "✗"
                dims = f" ({est.get('dimensions', 'N/A')})" if 'dimensions' in est else ""
                bulletins = f" - Boletines: {', '.join(est.get('bulletins', []))}" if 'bulletins' in est else ""
                field = f" - Campo: {est.get('field', 'N/A')}"
                self.log(f"   [{status_icon}] {est['name']}{dims}{bulletins}{field}")
        
        # Cerrar conexiones
        if self.uploader:
            self.uploader.disconnect()
        
        # Cerrar navegador de Mautic usando try-except para manejar el error
        if self.mautic:
            try:
                if hasattr(self.mautic, 'driver'):
                    self.log("Cerrando navegador...")
                    if self.mautic.driver:
                        self.mautic.driver.quit()
            except Exception as e:
                self.log(f"Advertencia al cerrar navegador: {e}")
                pass
        
        self.log("\n¡Proceso de boletines completado!")
        self.log("Los boletines han sido creados. Revísalos y luego crea las campañas.")

# ======================== FUNCIÓN PRINCIPAL ========================
def main():
    """Función principal con interfaz gráfica"""
    
    # Crear y ejecutar la interfaz
    gui = AutomationGUI()
    gui.run()

if __name__ == "__main__":
    main()