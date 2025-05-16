import reflex as rx
import pandas as pd
from sqlalchemy import create_engine, text
from fpdf import FPDF
from datetime import datetime, timedelta

# Database configuration (replace with your actual credentials)
DB_CONFIG = {
    'host': '172.18.0.2',
    'user': 'root',
    'password': '123',
    'database': 'colegio',  # Replace with your database name
}

# Crear el motor de conexión
if DB_CONFIG['database']:
    engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
else:
    engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}")

class State(rx.State):
    """Estado de la aplicación."""
    date: str = ""  # Variable para almacenar la fecha ingresada
    apellido: str = ""  # Variable para almacenar el apellido a buscar
    procedure_result: str = ""
    error_message: str = ""
    pdf_generated: bool = False
    pdf_url: str = ""
    pdf_url_primario: str = ""
    pdf_url_secundario: str = ""
    primario_count: int = 0
    secundario_count: int = 0
    viandas_data: list[dict] = []  # Para almacenar resultados de viandas
    viandas_error: str = ""        # Para errores específicos de viandas
    alumnos_encontrados: list[dict] = []  # Para almacenar resultados de búsqueda
    busqueda_error: str = ""       # Para errores de búsqueda
    nuevo_saldo: dict[str, str] = {}  # Para almacenar los nuevos saldos por alumno
    fechas_alumno: list[dict] = []  # Para almacenar las fechas del alumno actual
    alumno_actual: str = ""  # Para almacenar el nombre del alumno actual
    
    def set_date(self, date: str):
        """Actualiza la fecha ingresada."""
        self.date = date
        self.procedure_result = ""  # Limpiar resultados anteriores
        self.pdf_generated = False  # Limpiar estado del PDF
        self.primario_count = 0  # Reset counts
        self.secundario_count = 0

    def set_apellido(self, apellido: str):
        """Actualiza el apellido ingresado."""
        self.apellido = apellido
        self.alumnos_encontrados = []  # Limpiar resultados anteriores
        self.busqueda_error = ""  # Limpiar errores anteriores

    def buscar_alumno(self):
        """Busca alumnos por apellido."""
        try:
            # Limpiar resultados anteriores
            self.alumnos_encontrados = []
            self.busqueda_error = ""
            self.nuevo_saldo = {}  # Limpiar los saldos anteriores
            
            # Validar que se haya ingresado un apellido
            if not self.apellido.strip():
                self.busqueda_error = "Por favor ingrese un apellido para buscar"
                return
                
            with engine.connect() as connection:
                # Construir la consulta de manera segura
                query = text("""
                    SELECT nombre, curso, COALESCE(saldo, 0) as saldo 
                    FROM alumnos 
                    WHERE nombre LIKE :apellido 
                    AND habilitado = '1'
                    ORDER BY nombre
                """)
                
                # Ejecutar la consulta con parámetros
                result = connection.execute(
                    query, 
                    {"apellido": f"%{self.apellido}%"}
                )
                
                # Obtener todos los resultados
                rows = result.fetchall()
                
                # Imprimir datos para depuración
                print("\n=== Datos de la consulta ===")
                print(f"Apellido buscado: {self.apellido}")
                print(f"Total de resultados: {len(rows)}")
                
                if rows:
                    print("\nResultados encontrados:")
                    for row in rows:
                        print(f"Nombre: {row[0]}, Curso: {row[1]}, Saldo: {row[2]}")
                    
                    # Convertir resultados a lista de diccionarios
                    self.alumnos_encontrados = [
                        {
                            "nombre": row[0], 
                            "curso": row[1], 
                            "saldo": int(row[2]) if row[2] is not None else 0
                        }
                        for row in rows
                    ]
                else:
                    print("\nNo se encontraron resultados")
                    self.busqueda_error = "No se encontraron alumnos con ese apellido"
                
        except Exception as e:
            print(f"\nError en la búsqueda: {str(e)}")
            self.busqueda_error = f"Error en la búsqueda: {str(e)}"
            self.alumnos_encontrados = []

    def asignar_curso(self, grado):
        try:
            if grado.startswith("SECUNDARIO"):
                return "SEC " + grado.split()[1] + " " + grado.split()[2]
            elif grado.startswith("PRIMARIO"):
                return "PRI " + grado.split()[1] + " " + grado.split()[2]
            else:
                return "Curso no válido"
        except Exception as e:
            print(f"Error en asignar_variable: {e}")
            return "Error al procesar curso"

    def call_descontardia(self):
        """Ejecuta el procedimiento almacenado con la fecha ingresada."""
        try:
            with engine.connect() as connection:
                query = text(f"CALL descontardia('{self.date}');")
                result=connection.execute(query)
                rowCount=result.fetchall()[0]
                print(rowCount)
                 # Verificar integridad
                if rowCount == 0:
                    self.error_message = "Ningún alumno fue actualizado"
                else:
                    self.error_message = f"{rowCount} alumnos actualizados"
                    
            connection.commit()
        except Exception as e:
            self.error_message = f"Error al ejecutar el procedimiento: {e}"
            self.procedure_result = "" # Limpiar resultados si hay error
            connection.rollback()

    def get_viandas_hoy(self):
        """Ejecuta el procedimiento viandashoy"""
        try:
            with engine.connect() as connection:
                # Ejecutar el stored procedure
                result = connection.execute(
                    text(f"CALL viandashoy('{self.date}')")
                )
                
                # Convertir resultados a lista de diccionarios
                self.viandas_data = [
                    {"curso": row[0], "nombre": row[1]}
                    for row in result.fetchall()
                ]
                
                self.viandas_error = ""
                
        except Exception as e:
            self.viandas_error = f"Error obteniendo viandas: {e}"
            self.viandas_data = []
            
    def generate_report(self):
        try:
            # Fetch data from database
            date = self.date
            pdf_filename_primario = f"primario_{date}.pdf"
            pdf_filename_secundario = f"secundario_{date}.pdf"

            query = f"""
            SELECT id, nombre, curso, saldo 
            FROM alumnos a 
            WHERE a.habilitado = '1' 
            AND a.saldo > 0  
            AND a.id IN (
                SELECT alumnos_id 
                FROM diasalumcom  
                WHERE fecha = '{date}' 
                AND reservado = '1'
            )
            ORDER BY a.curso, a.nombre;
            """

            try:
                data = pd.read_sql(query, engine)
            except Exception as e:
                print(f"Error al leer datos: {e}")
                return

            # Count Primario and Secundario students
            self.primario_count = len(data[data['curso'].str.startswith('PRIMARIO')])
            self.secundario_count = len(data[data['curso'].str.startswith('SECUNDARIO')])
            
            # Process data for PDF generation
            primario = data[data['curso'].str.startswith('PRIMARIO')]
            secundario = data[data['curso'].str.startswith('SECUNDARIO')]

            primario_groups = primario.groupby(primario['curso'])
            secundario_students = secundario.sort_values(by='curso').copy()  # Ordena por nombre

            # PDF Generation
            class PDFWithHeader(FPDF):
                def __init__(self):
                    super().__init__(format='A4')  # Configura el tamaño de página a A4
                    
                def header(self):
                    self.set_font("Arial", size=24)
                    self.cell(0, 10, f"{date} - Mate de Luna Multieventos", ln=True, align='R')
                    self.ln(10)

            # Generar PDF para primario
            pdf_primario = PDFWithHeader()
            pdf_primario.set_auto_page_break(auto=True, margin=10) # Avoid text overlap

            def add_group_to_pdf(group_name, students):
                pdf_primario.add_page()
                pdf_primario.set_font("Arial", style="B", size=32)
                pdf_primario.cell(200, 10, txt=f"{group_name}", ln=True, align='C')
                pdf_primario.set_font("Arial", size=30)
                for _, student in students.iterrows():
                    # Obtener saldo y calcular viandas restantes
                    saldo = int(student['saldo']) if 'saldo' in student else 1
                    viandas_restantes = max(saldo - 1, 0)
                    pdf_primario.cell(
                        200, 12,
                        txt=f"{student['nombre']} ({viandas_restantes})",
                        ln=True
                    )

            for group_name, students in primario_groups:
                add_group_to_pdf(group_name, students)

            # Save PDF para primario
            pdf_primario_filepath = f"assets/{pdf_filename_primario}"  # Store in assets folder for Reflex
            pdf_primario.output(pdf_primario_filepath)

            # Generar PDF para secundario
            pdf_secundario = PDFWithHeader()
            pdf_secundario.set_auto_page_break(auto=True, margin=10) # Avoid text overlap

            # Solo imprimir la lista de alumnos si hay alumnos de secundaria
            if not secundario_students.empty:
                pdf_secundario.add_page()
                pdf_secundario.set_font("Arial", style="B", size=24)
                pdf_secundario.cell(200, 10, txt="SECUNDARIO (Cursos 1-6)", ln=True, align='C')
                pdf_secundario.set_font("Arial", size=18)
                for _, student in secundario_students.iterrows():
                    curso_procesado = self.asignar_curso(student['curso'])
                    saldo = int(student['saldo']) if 'saldo' in student else 1
                    viandas_restantes = max(saldo - 1, 0)
                    pdf_secundario.cell(
                        200, 10,
                        txt=f"{student['nombre']} ({curso_procesado}) ({viandas_restantes})",
                        ln=True
                    )

            # Agregar resumen total en una nueva página
            pdf_secundario.add_page()
            pdf_secundario.set_font("Courier", style="B", size=16)
            pdf_secundario.cell(200, 10, txt=f"Total de estudiantes de Primaria: {self.primario_count}", ln=True, align='L')
            pdf_secundario.cell(200, 10, txt=f"Total de estudiantes de Secundaria: {self.secundario_count}", ln=True, align='L')
            pdf_secundario.cell(200, 10, txt=f"Total general: {self.primario_count + self.secundario_count}", ln=True, align='L')

            # Save PDF para secundario
            pdf_secundario_filepath = f"assets/{pdf_filename_secundario}"  # Store in assets folder for Reflex
            pdf_secundario.output(pdf_secundario_filepath)
            
            self.pdf_url_primario = f"/{pdf_primario_filepath}" # Correct URL for Reflex
            self.pdf_url_secundario = f"/{pdf_secundario_filepath}" # Correct URL for Reflex
            self.pdf_generated = True
            self.error_message = "" # Clear any previous errors

        except Exception as e:
            self.error_message = f"Error generating PDF: {e}"
            self.pdf_generated = False

    def marcar_feriado(self):
        """Marca el día como feriado actualizando el campo reservado a 0."""
        try:
            with engine.connect() as connection:
                query = text(f"""
                    UPDATE diasalumcom 
                    SET reservado = '0' 
                    WHERE fecha = '{self.date}'
                """)
                result = connection.execute(query)
                row_count = result.rowcount
                
                if row_count == 0:
                    self.error_message = "No se encontraron registros para actualizar"
                else:
                    self.error_message = f"Se marcó como feriado el día {self.date}. {row_count} registros actualizados."
                    
            connection.commit()
        except Exception as e:
            self.error_message = f"Error al marcar el día como feriado: {e}"
            connection.rollback()

    def set_nuevo_saldo(self, alumno_id: str, valor: str):
        """Actualiza el nuevo saldo y genera preview de fechas."""
        self.nuevo_saldo[alumno_id] = valor
        self.alumno_actual = alumno_id
        if valor.isdigit():
            fechas = self.obtener_proximas_fechas(int(valor))
            # Convertir las fechas a una lista de diccionarios
            self.fechas_alumno = [
                {"fecha": fecha, "seleccionada": True}
                for fecha in fechas
            ]

    def toggle_fecha(self, fecha_idx: int):
        """Alterna la selección de una fecha y ajusta las fechas si es necesario."""
        if not self.fechas_alumno:
            return
            
        # Cambiar el estado del checkbox
        self.fechas_alumno[fecha_idx]["seleccionada"] = not self.fechas_alumno[fecha_idx]["seleccionada"]
        
        # Si se desmarcó una fecha, agregar una nueva al final
        if not self.fechas_alumno[fecha_idx]["seleccionada"]:
            ultima_fecha = datetime.strptime(self.fechas_alumno[-1]["fecha"], '%Y-%m-%d')
            nueva_fecha = ultima_fecha + timedelta(days=1)
            
            # Buscar el siguiente día hábil
            while nueva_fecha.weekday() >= 4:  # Si es viernes o fin de semana
                nueva_fecha += timedelta(days=1)
                
            nueva_fecha_str = nueva_fecha.strftime('%Y-%m-%d')
            self.fechas_alumno.append({
                "fecha": nueva_fecha_str,
                "seleccionada": True
            })

    def obtener_proximas_fechas(self, cantidad_viandas: int) -> list:
        """
        Genera una lista de las próximas fechas hábiles (lunes a jueves) 
        comenzando desde el próximo lunes.
        """
        try:
            fechas = []
            fecha_actual = datetime.now()
            
            # Encontrar el próximo lunes
            dias_hasta_lunes = (7 - fecha_actual.weekday()) % 7
            if dias_hasta_lunes == 0:
                dias_hasta_lunes = 7  # Si hoy es lunes, comenzar desde el próximo
            
            fecha_inicio = fecha_actual + timedelta(days=dias_hasta_lunes)
            fecha = fecha_inicio
            
            while len(fechas) < cantidad_viandas:
                # Si es un día hábil (1-4 = lunes a jueves)
                if fecha.weekday() < 4:
                    fechas.append(fecha.strftime('%Y-%m-%d'))
                fecha += timedelta(days=1)
                
            return fechas
            
        except Exception as e:
            print(f"Error generando fechas: {e}")
            return []

    def actualizar_saldo(self, alumno_id: str, nombre: str):
        """Actualiza el saldo del alumno y genera los registros de viandas."""
        try:
            if alumno_id not in self.nuevo_saldo or not self.nuevo_saldo[alumno_id].isdigit():
                self.error_message = "Por favor ingrese un valor numérico válido"
                return
                
            nuevo_valor = int(self.nuevo_saldo[alumno_id])
            
            # Primero obtener el ID del alumno
            with engine.connect() as connection:
                # Obtener ID del alumno
                query_id = text("SELECT id FROM alumnos WHERE nombre = :nombre")
                result = connection.execute(query_id, {"nombre": nombre})
                alumno_row = result.fetchone()
                
                if not alumno_row:
                    self.error_message = f"No se encontró el alumno {nombre}"
                    return
                    
                alumno_id = alumno_row[0]
                
                # Actualizar saldo
                query_saldo = text("""
                    UPDATE alumnos 
                    SET saldo = :saldo 
                    WHERE id = :id
                """)
                connection.execute(
                    query_saldo,
                    {"saldo": nuevo_valor, "id": alumno_id}
                )
                
                # Obtener fechas seleccionadas
                fechas_seleccionadas = [
                    fecha_dict["fecha"]
                    for fecha_dict in self.fechas_alumno
                    if fecha_dict["seleccionada"]
                ]
                
                if fechas_seleccionadas:
                    # Primero eliminar registros futuros existentes
                    query_delete = text("""
                        DELETE FROM diasalumcom 
                        WHERE alumnos_id = :alumno_id 
                        AND fecha >= CURDATE()
                    """)
                    connection.execute(query_delete, {"alumno_id": alumno_id})
                    
                    # Insertar solo los registros seleccionados
                    for fecha in fechas_seleccionadas:
                        query_insert = text("""
                            INSERT INTO diasalumcom (alumnos_id, fecha, reservado) 
                            VALUES (:alumno_id, :fecha, '1')
                            ON DUPLICATE KEY UPDATE reservado = '1'
                        """)
                        connection.execute(
                            query_insert,
                            {"alumno_id": alumno_id, "fecha": fecha}
                        )
                
                connection.commit()
                
                # Actualizar el saldo en la lista de alumnos encontrados
                for alumno in self.alumnos_encontrados:
                    if alumno["nombre"] == nombre:
                        alumno["saldo"] = nuevo_valor
                        break
                        
                self.error_message = f"Saldo actualizado correctamente para {nombre}. Se programaron {len(fechas_seleccionadas)} viandas."
                
                # Limpiar las fechas
                self.fechas_alumno = []
                self.alumno_actual = ""
            
        except Exception as e:
            self.error_message = f"Error al actualizar el saldo: {str(e)}"

def navbar():
    """Componente de navegación."""
    return rx.hstack(
        rx.vstack(
            rx.heading("Mate de Luna", size="3"),
            rx.heading("Multieventos", size="2", color="gray"),
            spacing="1",
        ),
        rx.spacer(),
        rx.hstack(
            rx.link(
                rx.button("Inicio", variant="ghost"),
                href="/",
            ),
            rx.link(
                rx.button("Alumnos", variant="ghost"),
                href="/alumnos",
            ),
            spacing="3",
        ),
        width="100%",
        border_bottom="1px solid #e2e8f0",
        padding="1em",
        bg="white",
    )

def index():
    """Página principal con la gestión de fechas y reportes."""
    return rx.vstack(
        navbar(),
        rx.vstack(
            rx.heading("Gestión de Viandas y Reportes", size="4"),
            # Sección de Fecha
            rx.vstack(
                rx.text("Ingrese una fecha:", font_weight="bold"),
                rx.input(
                    placeholder="YYYY-MM-DD",
                    value=State.date,
                    on_change=State.set_date,
                    width="100%",
                ),
                rx.vstack(
                    rx.button(
                        "Descontar Día",
                        color_scheme="red",
                        on_click=State.call_descontardia,
                        width="100%",
                    ),
                    rx.button(
                        "Generar Reporte",
                        on_click=State.generate_report,
                        width="100%",
                    ),
                    rx.button(
                        "Viandas de Hoy",
                        on_click=State.get_viandas_hoy,
                        width="100%",
                    ),
                    rx.button(
                        "Marcar como Feriado",
                        on_click=State.marcar_feriado,
                        width="100%",
                    ),
                    columns=[2, 2, 4],
                    spacing="4",
                ),
                width="100%",
                padding="1em",
                border="1px solid #e2e8f0",
                border_radius="0.5em",
                spacing="4",
                align="center",
            ),
            
            # Sección de Resultados
            rx.vstack(
                # Mensajes de error
                rx.cond(
                    State.error_message != "",
                    rx.text(State.error_message, color="red"),
                ),
                rx.cond(
                    State.viandas_error != "",
                    rx.text(State.viandas_error, color="red"),
                ),
                
                # Resultados de viandas
                rx.cond(
                    State.viandas_data != [],
                    rx.vstack(
                        rx.text("Viandas para hoy:", font_weight="bold"),
                        rx.foreach(
                            State.viandas_data,
                            lambda item: rx.text(f"{item['curso']} - {item['nombre']}")
                        ),
                        rx.text("Total de viandas:", font_weight="bold"),
                        rx.text(State.viandas_data.length()),  
                        align="start",
                        padding="1em",
                        border="1px solid #e2e8f0",
                        border_radius="0.5em",
                        width="100%",
                    ),
                ),
                
                # Enlaces a PDFs
                rx.cond(
                    State.pdf_generated,
                    rx.vstack(
                        rx.link(
                            "Descargar Reporte Primario PDF",
                            href=State.pdf_url_primario,
                            border="0.1em solid",
                            padding="0.5em",
                            border_radius="0.5em",
                            color_scheme="blue",
                            is_external=True,
                            font_weight="bold",
                            width="100%",
                        ),
                        rx.link(
                            "Descargar Reporte Secundario PDF",
                            href=State.pdf_url_secundario,
                            border="0.1em solid",
                            padding="0.5em",
                            border_radius="0.5em",
                            color_scheme="blue",
                            is_external=True,
                            font_weight="bold",
                            width="100%",
                        ),
                        columns=[1, 1, 1],
                        spacing="4",
                    ),
                ),
                width="100%",
                spacing="4",
            ),
            width="100%",
            spacing="4",
            padding="2em",
            max_width="1200px",
            margin="0 auto",
        ),
    )

def alumnos_page():
    """Página específica para la búsqueda y gestión de alumnos."""
    return rx.vstack(
        navbar(),
        rx.vstack(
            rx.heading("Búsqueda de Alumnos", size="3"),
            rx.vstack(
                rx.text("Buscar alumno por apellido:", font_weight="bold"),
                rx.hstack(
                    rx.input(
                        placeholder="Ingrese apellido",
                        value=State.apellido,
                        on_change=State.set_apellido,
                    ),
                    rx.button("Buscar", on_click=State.buscar_alumno),
                    spacing="2",
                ),
                width="100%",
                padding="1em",
                border="1px solid #e2e8f0",
                border_radius="0.5em",
            ),
            
            # Mensajes de error
            rx.cond(
                State.error_message != "",
                rx.text(State.error_message, color="red"),
            ),
            rx.cond(
                State.busqueda_error != "",
                rx.text(State.busqueda_error, color="red"),
            ),
            
            # Resultados de búsqueda
            rx.cond(
                State.alumnos_encontrados != [],
                rx.vstack(
                    rx.text("Resultados de la búsqueda:", font_weight="bold"),
                    rx.foreach(
                        State.alumnos_encontrados,
                        lambda item: rx.vstack(
                            rx.text(f"Nombre: {item['nombre']}", font_weight="bold"),
                            rx.text(f"Curso: {item['curso']}"),
                            rx.hstack(
                                rx.text(f"Saldo actual: {item['saldo']}"),
                                rx.input(
                                    placeholder="Nuevo saldo",
                                    on_change=lambda value, nombre=item['nombre']: State.set_nuevo_saldo(nombre, value),
                                    width="100px",
                                ),
                                spacing="2",
                            ),
                            # Mostrar fechas previstas con checkboxes
                            rx.cond(
                                State.alumno_actual == item['nombre'],
                                rx.vstack(
                                    rx.text("Fechas previstas:", font_weight="bold"),
                                    rx.hstack(
                                        rx.foreach(
                                            State.fechas_alumno,
                                            lambda fecha_dict, idx: rx.checkbox(
                                                fecha_dict["fecha"],
                                                is_checked=fecha_dict["seleccionada"],
                                                on_change=lambda checked, i=idx: State.toggle_fecha(i),
                                            ),
                                        ),
                                        wrap="wrap",
                                        spacing="4",
                                    ),
                                ),
                            ),
                            rx.button(
                                "Actualizar",
                                on_click=lambda nombre=item['nombre']: State.actualizar_saldo(nombre, nombre),
                            ),
                            rx.divider(),
                            align="start",
                            padding="1em",
                        ),
                    ),
                    align="start",
                    padding="1em",
                    border="1px solid #e2e8f0",
                    border_radius="0.5em",
                    width="100%",
                ),
            ),
            width="100%",
            spacing="4",
            padding="2em",
            max_width="800px",
            margin="0 auto",
        ),
    )

app = rx.App()
app.add_page(index)
app.add_page(alumnos_page, route="/alumnos")
# app.compile()



## aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
#            secundario_groups = secundario.groupby(secundario['curso'].str.extract(r'(SECUNDARIO \d+)')[0])h${title $}*3
