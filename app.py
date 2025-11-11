import streamlit as st
import plotly.express as px
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import os


# ----- Fuentes de datos -----

# El archivo original se obtuvo mediante el servicio WFS:
#  https://geos.snitcr.go.cr/be/IGN_200/wfs y la capa
#  IGN_200:redvial_200k

archivo_redvial_200k = os.path.join('datos', 'redvial_200k.gpkg')

# El archivo original se obtuvo mediante el servicio WFS:
#  https://geos.snitcr.go.cr/be/IGN_200/wfs y la capa
#  IGN_200:edificaciones_y_construcciones_200k

archivo_edificaciones_y_construcciones_200k = (
    os.path.join('datos', 'edificaciones_y_construcciones_200k.gpkg')
)

# El archivo original se obtuvo mediante el servicio WFS:
#  https://geos.snitcr.go.cr/be/IGN_5_CO/wfs y la capa
#  IGN_5_CO:limiteprovincial_5k

archivo_limiteprovincial_5k = os.path.join('datos', 'limiteprovincial_5k.gpkg')


# ----- Funciones para recuperar y analizar los datos -----
def red_vial_red_vial_nodos():
    red_vial_gdf = gpd.read_file(archivo_redvial_200k)

    # Asegurarse que el CRS sea CRTM05 (EPSG 5367)
    red_vial_gdf = red_vial_gdf.to_crs(epsg=5367)

    # Reducción de columnas
    red_vial_gdf = red_vial_gdf[['categoria', 'geometry']]

    return red_vial_gdf


# Función para cargar los datos y almacenarlos en caché
# para mejorar el rendimiento
@st.cache_resource
def cargar_datos_redvial_200k():
    red_vial_gdf = (
        red_vial_red_vial_nodos()
    )

    return red_vial_gdf


@st.cache_data
def cargar_datos_edificaciones_y_construcciones_200k():
    limiteprovincial_gdf = (
        gpd.read_file(archivo_limiteprovincial_5k)
    )

    # Asegurarse que el CRS sea CRTM05 (EPSG 5367)
    limiteprovincial_gdf = (
        limiteprovincial_gdf.to_crs(epsg=5367)
    )

    # Reducción de columnas
    limiteprovincial_gdf = (
        limiteprovincial_gdf[['PROVINCIA', 'geometry']]
    )

    edificaciones_y_construcciones_gdf = (
        gpd.read_file(archivo_edificaciones_y_construcciones_200k)
    )

    # Asegurarse que el CRS sea CRTM05 (EPSG 5367)
    edificaciones_y_construcciones_gdf = (
        edificaciones_y_construcciones_gdf.to_crs(epsg=5367)
    )

    # Reducción de columnas
    edificaciones_y_construcciones_gdf = (
        edificaciones_y_construcciones_gdf[['categoria', 'nombre', 'geometry']]
    )

    # Unión espacial
    edificaciones_y_construcciones_gdf = (
        edificaciones_y_construcciones_gdf.sjoin(
            limiteprovincial_gdf,
            predicate='intersects'
        )
    )

    return edificaciones_y_construcciones_gdf


@st.cache_data
def cargar_datos_limiteprovincial_5k():
    limiteprovincial_gdf = (
        gpd.read_file(archivo_limiteprovincial_5k)
    )

    # Asegurarse que el CRS sea CRTM05 (EPSG 5367)
    limiteprovincial_gdf = (
        limiteprovincial_gdf.to_crs(epsg=5367)
    )

    # Reducción de columnas
    limiteprovincial_gdf = (
        limiteprovincial_gdf[['PROVINCIA', 'geometry']]
    )

    return limiteprovincial_gdf


# Título de la aplicación
st.title(
    'Datos de la red vial, edificaciones y provincias del SNIT para análisis'
    ' con grafos'
)

# ----- Carga de datos -----

# Mostrar un mensaje mientras se cargan los datos de redvial_200k
estado_carga_redvial_200k = st.text('Cargando datos de redvial_200k...')
# Cargar los datos
red_vial_gdf = (
    cargar_datos_redvial_200k()
)
# Actualizar el mensaje una vez que los datos han sido cargados
estado_carga_redvial_200k.text('Los datos de redvial_200k fueron cargados.')

# Cargar datos geoespaciales de edificaciones_y_construcciones_200k
estado_carga_edificaciones_y_construcciones_200k = (
    st.text('Cargando datos de edificaciones_y_construcciones_200k...')
)
edificaciones_y_construcciones_gdf = (
    cargar_datos_edificaciones_y_construcciones_200k()
)
(
    estado_carga_edificaciones_y_construcciones_200k
    .text(
        'Los datos de edificaciones_y_construcciones_200k fueron cargados.'
    )
)

# Mostrar un mensaje mientras se cargan los datos de limiteprovincial_5k
estado_carga_limiteprovincial_5k = (
    st.text('Cargando datos de limiteprovincial_5k...')
)
# Cargar los datos
limiteprovincial_gdf = cargar_datos_limiteprovincial_5k()
# Actualizar el mensaje una vez que los datos han sido cargados
(
    estado_carga_limiteprovincial_5k
    .text(
        'Los datos de limiteprovincial_5k fueron cargados.'
    )
)

# ----- Lista de selección en la barra lateral -----

# Obtener la lista de provincias únicas
lista_provincias = (
    edificaciones_y_construcciones_gdf['PROVINCIA'].unique().tolist()
)

lista_provincias.sort()

# Añadir la opción "Todos" al inicio de la lista
opciones_provincias = ['Todas'] + lista_provincias

# Crear el selectbox en la barra lateral
provincia_seleccionada = st.sidebar.selectbox(
    'Selecciona una provincia',
    opciones_provincias
)

# ----- Filtrar datos según la selección -----

if provincia_seleccionada != 'Todas':
    # Filtrar los datos para la provincia seleccionada
    datos_filtrados = (
        edificaciones_y_construcciones_gdf[
            edificaciones_y_construcciones_gdf['PROVINCIA'] ==
            provincia_seleccionada
        ]
    )
else:
    # No aplicar filtro
    datos_filtrados = edificaciones_y_construcciones_gdf.copy()

# ----- Tabla de edificaciones y construcciones por provincia -----

# Mostrar la tabla
st.subheader('Edificaciones y construcciones por provincia')
st.dataframe(datos_filtrados, hide_index=True)

# ----- Gráfico de pastel de categorías de edificaciones y construcciones por
# provincia -----

# Cálculo del conteo por categoría
datos_filtrados_conteo = (
    datos_filtrados
    .groupby('categoria')['geometry']
    .count()
    .sort_values(ascending=True)
    .reset_index()
)

# Creación del gráfico de pastel
fig = px.pie(
    datos_filtrados_conteo,
    names='categoria',
    values='geometry',
    title='Distribución de categorías de edificios o construcciones',
    labels={'categoria': 'Categoría', 'geometry': 'Cantidad'}
)

# Atributos globales de la figura
fig.update_layout(
    legend_title_text='Categoría'
)

# Atributos de las propiedades visuales
fig.update_traces(textposition='inside', textinfo='percent')

# Mostrar el gráfico
st.subheader(
    'Distribución de categorías de edificaciones y construcciones por'
    ' provincia'
)
st.plotly_chart(fig)

# ----- Mapa con folium -----

# Crear el mapa interactivo con las edificaciones y construcciones al mapa
mapa = datos_filtrados.explore(
    name='Edificaciones y Construcciones',
    marker_type='circle',
    marker_kwds={'radius': 20, 'color': 'red'},
    tooltip=['categoria', 'nombre'],
    popup=True
)

# Agregar el control de capas al mapa
folium.LayerControl().add_to(mapa)

# Mostrar el mapa
st.subheader('Mapa de edificaciones y construcciones por provincia')
st_folium(mapa)
