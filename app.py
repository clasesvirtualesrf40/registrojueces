import sqlite3
import io
import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Inscripción a Competencias",
    page_icon="🏆",
    layout="centered"
)

# -----------------------------------------------------------------------------
# CONEXIÓN Y CREACIÓN DE LA BASE DE DATOS (SQLite)
# -----------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect('competencias_app.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tabla de Competencias
    c.execute('''
        CREATE TABLE IF NOT EXISTS competencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            max_cupos INTEGER NOT NULL DEFAULT 3
        )
    ''')
    
    # Tabla de Equipos
    c.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competencia_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            FOREIGN KEY (competencia_id) REFERENCES competencias (id) ON DELETE CASCADE
        )
    ''')
    
    # Tabla de Participantes
    c.execute('''
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            edad INTEGER NOT NULL,
            whatsapp TEXT NOT NULL,
            carrera TEXT NOT NULL,
            equipo_id INTEGER NOT NULL,
            FOREIGN KEY (equipo_id) REFERENCES equipos (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar tablas al cargar
init_db()

# -----------------------------------------------------------------------------
# MENÚ NAVEGACIÓN LATERAL
# -----------------------------------------------------------------------------
st.sidebar.title("📌 Menú Principal")
opcion = st.sidebar.radio("Selecciona una sección:", ["📝 Formulario de Inscripción", "🔒 Panel Administrador"])

# -----------------------------------------------------------------------------
# SECCIÓN 1: FORMULARIO DE INSCRIPCIÓN DE PARTICIPANTES
# -----------------------------------------------------------------------------
if opcion == "📝 Formulario de Inscripción":
    st.title("🏆 Inscripción a Competencias")
    st.write("Por favor, completa tus datos para inscribirte.")

    conn = get_db_connection()
    
    # Consulta de competencias con cálculo de inscritos
    query_comp = '''
        SELECT 
            c.id, 
            c.nombre, 
            c.max_cupos, 
            COUNT(p.id) AS total_inscritos
        FROM competencias c
        LEFT JOIN equipos e ON c.id = e.competencia_id
        LEFT JOIN participantes p ON e.id = p.equipo_id
        GROUP BY c.id
    '''
    competencias_df = pd.read_sql_query(query_comp, conn)

    # Filtrar solo aquellas con cupos disponibles
    opciones_disponibles = {}
    for _, row in competencias_df.iterrows():
        cupos_restantes = int(row['max_cupos']) - int(row['total_inscritos'])
        if cupos_restantes > 0:
            texto_label = f"{row['nombre']} ({cupos_restantes} puestos disponibles)"
            opciones_disponibles[texto_label] = row['id']

    if not opciones_disponibles:
        st.warning("⚠️ No hay competencias con cupos disponibles por el momento.")
    else:
        with st.form("form_inscripcion", clear_on_submit=True):
            nombre = st.text_input("Nombre Completo *", placeholder="Ej. Juan Pérez")
            edad = st.number_input("Edad *", min_value=12, max_value=99, value=18, step=1)
            whatsapp = st.text_input("WhatsApp / Teléfono *", placeholder="Ej. +5215512345678")
            carrera = st.text_input("Nombre de la Carrera *", placeholder="Ej. Ingeniería en Sistemas")
            
            comp_seleccionada_label = st.selectbox("Selecciona Competencia *", list(opciones_disponibles.keys()))
            
            submitted = st.form_submit_button("Completar Registro")

            if submitted:
                if not nombre.strip() or not whatsapp.strip() or not carrera.strip():
                    st.error("❌ Por favor completa todos los campos requeridos (*).")
                else:
                    competencia_id = opciones_disponibles[comp_seleccionada_label]
                    c = conn.cursor()

                    # Buscar un equipo existente en la competencia con menos de 3 integrantes
                    c.execute('''
                        SELECT e.id, COUNT(p.id) as integrantes
                        FROM equipos e
                        LEFT JOIN participantes p ON e.id = p.equipo_id
                        WHERE e.competencia_id = ?
                        GROUP BY e.id
                        HAVING integrantes < 3
                        LIMIT 1
                    ''', (competencia_id,))
                    equipo_disponible = c.fetchone()

                    if equipo_disponible:
                        equipo_id = equipo_disponible['id']
                    else:
                        # Si no hay equipo con espacio, crear uno nuevo
                        c.execute("SELECT COUNT(*) FROM equipos WHERE competencia_id = ?", (competencia_id,))
                        num_nuevo_equipo = c.fetchone()[0] + 1
                        c.execute("INSERT INTO equipos (competencia_id, nombre) VALUES (?, ?)", 
                                  (competencia_id, f"Equipo {num_nuevo_equipo}"))
                        conn.commit()
                        equipo_id = c.lastrowid

                    # Registrar al participante en el equipo asignado
                    c.execute('''
                        INSERT INTO participantes (nombre, edad, whatsapp, carrera, equipo_id)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (nombre.strip(), edad, whatsapp.strip(), carrera.strip(), equipo_id))
                    conn.commit()

                    st.success(f"✅ ¡Inscripción realizada con éxito, {nombre}!")
                    st.rerun()
    
    conn.close()

# -----------------------------------------------------------------------------
# SECCIÓN 2: PANEL ADMINISTRADOR
# -----------------------------------------------------------------------------
elif opcion == "🔒 Panel Administrador":
    st.title("⚙️ Panel de Administración")
    
    # Control de acceso con clave
    admin_password = st.sidebar.text_input("Contraseña Admin", type="password")
    
    # Define la contraseña de administración deseada aquí
    CLAVE_ADMIN_CORRECTA = "admin123"

    if admin_password == CLAVE_ADMIN_CORRECTA:
        st.success("Acceso autorizado.")
        conn = get_db_connection()

        # -------------------------------------------------------------
        # 1. EXPORTAR DATOS A EXCEL
        # -------------------------------------------------------------
        st.subheader("📥 Exportar Reporte de Inscritos")
        query_reporte = '''
            SELECT 
                p.id AS ID_Participante, 
                p.nombre AS Nombre, 
                p.edad AS Edad, 
                p.whatsapp AS WhatsApp, 
                p.carrera AS Carrera, 
                c.nombre AS Competencia, 
                e.nombre AS Equipo
            FROM participantes p
            JOIN equipos e ON p.equipo_id = e.id
            JOIN competencias c ON e.competencia_id = c.id
            ORDER BY p.id DESC
        '''
        df_reporte = pd.read_sql_query(query_reporte, conn)

        if not df_reporte.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_reporte.to_excel(writer, index=False, sheet_name='Participantes')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Descargar Reporte en Excel (.xlsx)",
                data=excel_data,
                file_name="Reporte_Participantes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de participantes disponibles para exportar.")

        st.divider()

        # -------------------------------------------------------------
        # 2. CREAR / EDITAR COMPETENCIAS
        # -------------------------------------------------------------
        st.subheader("🏆 Gestión de Competencias")
        
        # Consultar competencias existentes
        competencias_lista = pd.read_sql_query('''
            SELECT 
                c.id, 
                c.nombre, 
                c.max_cupos, 
                COUNT(p.id) as total_inscritos
            FROM competencias c
            LEFT JOIN equipos e ON c.id = e.competencia_id
            LEFT JOIN participantes p ON e.id = p.equipo_id
            GROUP BY c.id
        ''', conn)

        tab_crear, tab_editar = st.tabs(["➕ Crear Competencia", "✏️ Editar / Eliminar Competencia"])

        with tab_crear:
            with st.form("form_nueva_comp", clear_on_submit=True):
                nombre_comp = st.text_input("Nombre de la Competencia")
                max_cupos_comp = st.number_input("Límite de Cupos Máximo", min_value=1, value=3, step=1)
                btn_crear = st.form_submit_button("Guardar Competencia")

                if btn_crear:
                    if nombre_comp.strip():
                        try:
                            c = conn.cursor()
                            c.execute("INSERT INTO competencias (nombre, max_cupos) VALUES (?, ?)", 
                                      (nombre_comp.strip(), max_cupos_comp))
                            conn.commit()
                            st.success(f"Competencia '{nombre_comp}' creada exitosamente.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Error: Ya existe una competencia con ese nombre.")
                    else:
                        st.error("Ingresa un nombre válido.")

        with tab_editar:
            if not competencias_lista.empty:
                comp_dict = {f"{r['nombre']} (Inscritos: {r['total_inscritos']}/{r['max_cupos']})": r['id'] for _, r in competencias_lista.iterrows()}
                comp_sel_label = st.selectbox("Selecciona Competencia a Gestionar", list(comp_dict.keys()))
                comp_sel_id = comp_dict[comp_sel_label]

                comp_actual = competencias_lista[competencias_lista['id'] == comp_sel_id].iloc[0]

                nuevo_nombre = st.text_input("Nuevo Nombre", value=comp_actual['nombre'])
                nuevo_cupo = st.number_input("Nuevo Límite de Cupos", min_value=1, value=int(comp_actual['max_cupos']))

                col_act, col_elim = st.columns(2)
                with col_act:
                    if st.button("Actualizar Competencia"):
                        c = conn.cursor()
                        c.execute("UPDATE competencias SET nombre = ?, max_cupos = ? WHERE id = ?", 
                                  (nuevo_nombre.strip(), nuevo_cupo, comp_sel_id))
                        conn.commit()
                        st.success("Competencia actualizada.")
                        st.rerun()

                with col_elim:
                    if st.button("🗑️ Eliminar Competencia", type="primary"):
                        c = conn.cursor()
                        c.execute("DELETE FROM competencias WHERE id = ?", (comp_sel_id,))
                        conn.commit()
                        st.warning("Competencia eliminada correctamente.")
                        st.rerun()
            else:
                st.info("No hay competencias creadas.")

        st.divider()

        # -------------------------------------------------------------
        # 3. GESTIÓN Y ELIMINACIÓN DE PARTICIPANTES (BORRAR REGISTROS MAL LLENADOS)
        # -------------------------------------------------------------
        st.subheader("📋 Lista de Participantes Registrados")
        
        if not df_reporte.empty:
            st.dataframe(df_reporte, use_container_width=True)

            st.write("### ❌ Eliminar Inscripción con Error")
            
            # Mapeo para seleccionar participante a eliminar
            participantes_dict = {
                f"ID {r['ID_Participante']}: {r['Nombre']} ({r['Competencia']} - {r['Equipo']})": r['ID_Participante']
                for _, r in df_reporte.iterrows()
            }
            
            p_seleccionado_label = st.selectbox("Selecciona el participante que deseas eliminar:", list(participantes_dict.keys()))
            p_id_eliminar = participantes_dict[p_seleccionado_label]

            if st.button("🗑️ Eliminar Inscripción Seleccionada"):
                c = conn.cursor()
                c.execute("DELETE FROM participantes WHERE id = ?", (p_id_eliminar,))
                conn.commit()
                st.success("La inscripción ha sido eliminada. El cupo ha sido liberado automáticamente.")
                st.rerun()
        else:
            st.info("No hay participantes registrados aún.")

        conn.close()

    elif admin_password != "":
        st.error("🔒 Contraseña incorrecta.")
