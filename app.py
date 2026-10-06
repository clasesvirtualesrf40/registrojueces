import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Inscripción a Competencias",
    page_icon="🏆",
    layout="centered"
)

# -----------------------------------------------------------------------------
# CONEXIÓN CON GOOGLE SHEETS
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_hoja(worksheet_name):
    """Carga los datos de una pestaña específica de Google Sheets."""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        # Limpiar filas completamente vacías
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()

def guardar_hoja(df, worksheet_name):
    """Guarda un DataFrame actualizado en Google Sheets."""
    conn.update(worksheet=worksheet_name, data=df)

# Cargar los DataFrames al iniciar
df_competencias = cargar_hoja("competencias")
df_equipos = cargar_hoja("equipos")
df_participantes = cargar_hoja("participantes")

# Asegurar tipos de datos adecuados
if not df_competencias.empty:
    df_competencias["id"] = df_competencias["id"].astype(int)
    df_competencias["max_cupos"] = df_competencias["max_cupos"].astype(int)

if not df_equipos.empty:
    df_equipos["id"] = df_equipos["id"].astype(int)
    df_equipos["competencia_id"] = df_equipos["competencia_id"].astype(int)

if not df_participantes.empty:
    df_participantes["id"] = df_participantes["id"].astype(int)
    df_participantes["equipo_id"] = df_participantes["equipo_id"].astype(int)

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

    if df_competencias.empty:
        st.warning("⚠️ No hay competencias registradas en el sistema por el momento.")
    else:
        # Calcular cupos ocupados por competencia
        cupos_info = []
        for _, comp in df_competencias.iterrows():
            c_id = comp["id"]
            c_nombre = comp["nombre"]
            max_c = comp["max_cupos"]

            # Obtener equipos de esta competencia
            eq_ids = df_equipos[df_equipos["competencia_id"] == c_id]["id"].tolist() if not df_equipos.empty else []
            
            # Contar participantes registrados en estos equipos
            if not df_participantes.empty and eq_ids:
                total_inscritos = len(df_participantes[df_participantes["equipo_id"].isin(eq_ids)])
            else:
                total_inscritos = 0

            cupos_restantes = max_c - total_inscritos
            if cupos_restantes > 0:
                texto_label = f"{c_nombre} ({cupos_restantes} puestos disponibles)"
                cupos_info.append({"id": c_id, "nombre": c_nombre, "label": texto_label})

        if not cupos_info:
            st.warning("⚠️ Todas las competencias han agotado sus cupos disponibles.")
        else:
            opciones_dict = {item["label"]: item["id"] for item in cupos_info}

            with st.form("form_inscripcion", clear_on_submit=True):
                nombre = st.text_input("Nombre Completo *", placeholder="Ej. Juan Pérez")
                edad = st.number_input("Edad *", min_value=12, max_value=99, value=18, step=1)
                whatsapp = st.text_input("WhatsApp / Teléfono *", placeholder="Ej. +5215512345678")
                carrera = st.text_input("Nombre de la Carrera *", placeholder="Ej. Ingeniería en Sistemas")
                
                comp_seleccionada_label = st.selectbox("Selecciona Competencia *", list(opciones_dict.keys()))
                submitted = st.form_submit_button("Completar Registro")

                if submitted:
                    if not nombre.strip() or not whatsapp.strip() or not carrera.strip():
                        st.error("❌ Por favor completa todos los campos requeridos (*).")
                    else:
                        competencia_id = opciones_dict[comp_seleccionada_label]

                        # --- LÓGICA DE ASIGNACIÓN / CREACIÓN DE EQUIPOS ---
                        # 1. Obtener los equipos existentes para esta competencia
                        eq_comp = df_equipos[df_equipos["competencia_id"] == competencia_id] if not df_equipos.empty else pd.DataFrame()
                        
                        equipo_destino_id = None

                        if not eq_comp.empty and not df_participantes.empty:
                            for _, eq in eq_comp.iterrows():
                                e_id = eq["id"]
                                cant_integrantes = len(df_participantes[df_participantes["equipo_id"] == e_id])
                                if cant_integrantes < 3:
                                    equipo_destino_id = e_id
                                    break

                        # 2. Si no hay equipo con espacio, crear uno nuevo
                        if equipo_destino_id is None:
                            nuevo_eq_id = 1 if df_equipos.empty else int(df_equipos["id"].max()) + 1
                            num_equipo = len(eq_comp) + 1
                            nuevo_equipo = {
                                "id": nuevo_eq_id,
                                "competencia_id": competencia_id,
                                "nombre": f"Equipo {num_equipo}"
                            }
                            df_equipos = pd.concat([df_equipos, pd.DataFrame([nuevo_equipo])], ignore_index=True)
                            guardar_hoja(df_equipos, "equipos")
                            equipo_destino_id = nuevo_eq_id

                        # 3. Registrar participante
                        nuevo_part_id = 1 if df_participantes.empty else int(df_participantes["id"].max()) + 1
                        nuevo_participante = {
                            "id": nuevo_part_id,
                            "nombre": nombre.strip(),
                            "edad": int(edad),
                            "whatsapp": whatsapp.strip(),
                            "carrera": carrera.strip(),
                            "equipo_id": equipo_destino_id
                        }
                        
                        df_participantes = pd.concat([df_participantes, pd.DataFrame([nuevo_participante])], ignore_index=True)
                        guardar_hoja(df_participantes, "participantes")

                        st.success(f"✅ ¡Inscripción realizada con éxito, {nombre}!")
                        st.rerun()

# -----------------------------------------------------------------------------
# SECCIÓN 2: PANEL ADMINISTRADOR
# -----------------------------------------------------------------------------
elif opcion == "🔒 Panel Administrador":
    st.title("⚙️ Panel de Administración")
    
    admin_password = st.sidebar.text_input("Contraseña Admin", type="password")
    
    # Puedes modificar esta clave de acceso según tus necesidades
    CLAVE_ADMIN_CORRECTA = "admin123"

    if admin_password == CLAVE_ADMIN_CORRECTA:
        st.success("Acceso autorizado.")

        # Construir reporte completo cruzando DataFrames
        if not df_participantes.empty and not df_equipos.empty and not df_competencias.empty:
            df_merged = df_participantes.merge(
                df_equipos, left_on="equipo_id", right_on="id", suffixes=("_part", "_eq")
            ).merge(
                df_competencias, left_on="competencia_id", right_on="id", suffixes=("_eq", "_comp")
            )

            df_reporte = df_merged[[
                "id_part", "nombre_part", "edad", "whatsapp", "carrera", "nombre_comp", "nombre_eq"
            ]].rename(columns={
                "id_part": "ID",
                "nombre_part": "Nombre",
                "edad": "Edad",
                "whatsapp": "WhatsApp",
                "carrera": "Carrera",
                "nombre_comp": "Competencia",
                "nombre_eq": "Equipo"
            }).sort_values(by="ID", ascending=False)
        else:
            df_reporte = pd.DataFrame()

        # -------------------------------------------------------------
        # 1. EXPORTAR DATOS A EXCEL
        # -------------------------------------------------------------
        st.subheader("📥 Exportar Reporte de Inscritos")
        
        if not df_reporte.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_reporte.to_excel(writer, index=False, sheet_name="Participantes")
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
        # 2. CREAR / EDITAR / ELIMINAR COMPETENCIAS
        # -------------------------------------------------------------
        st.subheader("🏆 Gestión de Competencias")
        
        tab_crear, tab_editar = st.tabs(["➕ Crear Competencia", "✏️ Editar / Eliminar Competencia"])

        with tab_crear:
            with st.form("form_nueva_comp", clear_on_submit=True):
                nombre_comp = st.text_input("Nombre de la Competencia")
                max_cupos_comp = st.number_input("Límite de Cupos Máximo", min_value=1, value=3, step=1)
                btn_crear = st.form_submit_button("Guardar Competencia")

                if btn_crear:
                    if nombre_comp.strip():
                        if not df_competencias.empty and nombre_comp.strip().lower() in df_competencias["nombre"].str.lower().values:
                            st.error("Error: Ya existe una competencia con ese nombre.")
                        else:
                            nuevo_comp_id = 1 if df_competencias.empty else int(df_competencias["id"].max()) + 1
                            nueva_row = {
                                "id": nuevo_comp_id,
                                "nombre": nombre_comp.strip(),
                                "max_cupos": int(max_cupos_comp)
                            }
                            df_competencias = pd.concat([df_competencias, pd.DataFrame([nueva_row])], ignore_index=True)
                            guardar_hoja(df_competencias, "competencias")
                            st.success(f"Competencia '{nombre_comp}' creada exitosamente.")
                            st.rerun()
                    else:
                        st.error("Ingresa un nombre válido.")

        with tab_editar:
            if not df_competencias.empty:
                comp_dict = {f"{r['nombre']} (Cupos: {r['max_cupos']})": r['id'] for _, r in df_competencias.iterrows()}
                comp_sel_label = st.selectbox("Selecciona Competencia a Gestionar", list(comp_dict.keys()))
                comp_sel_id = comp_dict[comp_sel_label]

                comp_actual = df_competencias[df_competencias['id'] == comp_sel_id].iloc[0]

                nuevo_nombre = st.text_input("Nuevo Nombre", value=comp_actual['nombre'])
                nuevo_cupo = st.number_input("Nuevo Límite de Cupos", min_value=1, value=int(comp_actual['max_cupos']))

                col_act, col_elim = st.columns(2)
                with col_act:
                    if st.button("Actualizar Competencia"):
                        df_competencias.loc[df_competencias['id'] == comp_sel_id, 'nombre'] = nuevo_nombre.strip()
                        df_competencias.loc[df_competencias['id'] == comp_sel_id, 'max_cupos'] = int(nuevo_cupo)
                        guardar_hoja(df_competencias, "competencias")
                        st.success("Competencia actualizada.")
                        st.rerun()

                with col_elim:
                    if st.button("🗑️ Eliminar Competencia", type="primary"):
                        df_competencias = df_competencias[df_competencias['id'] != comp_sel_id]
                        guardar_hoja(df_competencias, "competencias")
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
            
            participantes_dict = {
                f"ID {r['ID']}: {r['Nombre']} ({r['Competencia']} - {r['Equipo']})": r['ID']
                for _, r in df_reporte.iterrows()
            }
            
            p_seleccionado_label = st.selectbox("Selecciona el participante que deseas eliminar:", list(participantes_dict.keys()))
            p_id_eliminar = participantes_dict[p_seleccionado_label]

            if st.button("🗑️ Eliminar Inscripción Seleccionada"):
                df_participantes = df_participantes[df_participantes['id'] != p_id_eliminar]
                guardar_hoja(df_participantes, "participantes")
                st.success("La inscripción ha sido eliminada de Google Sheets. El cupo se ha liberado automáticamente.")
                st.rerun()
        else:
            st.info("No hay participantes registrados aún.")

    elif admin_password != "":
        st.error("🔒 Contraseña incorrecta.")
