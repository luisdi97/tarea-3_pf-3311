import streamlit as st
import pandas as pd
import plotly.express as px

import geopandas as gpd
import folium

from streamlit_folium import st_folium

import numpy as np
import networkx as nx
from shapely.geometry import MultiLineString, LineString, Point
from scipy.spatial import cKDTree

import pyproj

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

    # ----- Análisis para obtener el grafo -----

    # Separar las líneas en listas
    red_vial_gdf['split_lines'] = (
        red_vial_gdf['geometry'].apply(split_LineString)
    )

    # Crear filas separadas por cada elementos de la lista
    red_vial_gdf = red_vial_gdf.explode('split_lines', ignore_index=True)

    # Agregar pesos iguales a la distancia de cada segmento
    red_vial_gdf['weight'] = (
        gpd.GeoSeries(red_vial_gdf['split_lines']).length
    )

    # Obtener los puntos de inicio y fin de cada segmento y ponerles un nombre
    #  de acuerdo a sus coordenadas

    red_vial_gdf['source_Point'] = (
        red_vial_gdf['split_lines']
        .apply(lambda x: Point(x.coords[0]))
    )

    red_vial_gdf['source_Point_X'] = (
        red_vial_gdf['source_Point']
        .apply(lambda x: x.x)
    )

    red_vial_gdf['source_Point_Y'] = (
        red_vial_gdf['source_Point']
        .apply(lambda x: x.y)
    )

    red_vial_gdf['source'] = (
        red_vial_gdf['source_Point_X'].astype(str)
        .str.replace('.', '_')
        + '-'
        + red_vial_gdf['source_Point_Y'].astype(str)
        .str.replace('.', '_')
    )

    red_vial_gdf['target_Point'] = (
        red_vial_gdf['split_lines']
        .apply(lambda x: Point(x.coords[1]))
    )

    red_vial_gdf['target_Point_X'] = (
        red_vial_gdf['target_Point']
        .apply(lambda x: x.x)
    )

    red_vial_gdf['target_Point_Y'] = (
        red_vial_gdf['target_Point']
        .apply(lambda x: x.y)
    )

    red_vial_gdf['target'] = (
        red_vial_gdf['target_Point_X'].astype(str)
        .str.replace('.', '_')
        + '-'
        + red_vial_gdf['target_Point_Y'].astype(str)
        .str.replace('.', '_')
    )

    # Obtener los nodos de inicio y fin de los segmentos en un GeoDataFrame
    #  aparte

    red_vial_gdf_nodes = pd.concat([
        red_vial_gdf
        .loc[:, ['source_Point_X', 'source_Point_Y', 'source_Point', 'source']]
        .rename(
            columns={
                'source_Point_X': 'node_Point_X',
                'source_Point_Y': 'node_Point_Y',
                'source_Point': 'geometry',
                'source': 'node',
            }
        ),
        red_vial_gdf
        .loc[:, ['target_Point_X', 'target_Point_Y', 'target_Point', 'target']]
        .rename(
            columns={
                'target_Point_X': 'node_Point_X',
                'target_Point_Y': 'node_Point_Y',
                'target_Point': 'geometry',
                'target': 'node',
            }
        ),
    ])

    red_vial_gdf_nodes = (
        gpd.GeoDataFrame(
            red_vial_gdf_nodes,
            geometry='geometry',
            crs=red_vial_gdf.crs,
        )
    )

    red_vial_gdf_nodes = red_vial_gdf_nodes.drop_duplicates(subset=['node'])

    red_vial_gdf_nodes = (
        red_vial_gdf_nodes
        .rename(
            columns={'node_Point_X': 'CoordX', 'node_Point_Y': 'CoordY'}
        )
    )

    # Simplificar
    red_vial_simple = (
        red_vial_gdf.simplify(tolerance=10, preserve_topology=True)
    )

    return red_vial_gdf, red_vial_simple, red_vial_gdf_nodes


# Función para cargar los datos y almacenarlos en caché
# para mejorar el rendimiento
@st.cache_resource
def cargar_datos_redvial_200k():
    red_vial_gdf, red_vial_simple, red_vial_gdf_nodes = (
        red_vial_red_vial_nodos()
    )

    # Crear un grafo con los segmentos de línea

    G = nx.from_pandas_edgelist(
        red_vial_gdf,
        edge_attr=["weight"],
        create_using=nx.MultiGraph(),
    )

    return red_vial_gdf, red_vial_simple, red_vial_gdf_nodes, G


@st.cache_data
def cargar_datos_edificaciones_y_construcciones_200k():
    _, _, red_vial_gdf_nodes = red_vial_red_vial_nodos()

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

    # Determinar las edificaciones y construcciones más cercanas a cada nodo
    #  del grafo, pero más cercanos que 1000 m

    edificaciones_y_construcciones_gdf = (
        gdf_closest(edificaciones_y_construcciones_gdf, red_vial_gdf_nodes)
    )

    edificaciones_y_construcciones_gdf = (
        edificaciones_y_construcciones_gdf
        .loc[edificaciones_y_construcciones_gdf['distance'] < 1000].copy()
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


# ----- Funciones para grafos -----
def create_list_LineStrings(geom):
    """Separar la línea en segmentos
    """
    return list(map(LineString, zip(geom.coords[:-1], geom.coords[1:])))


def split_LineString(curve):
    """Wrapper alrededor de create_list_LineStrings para tomar en cuenta
     MultiLineString u otros tipos
    """
    if type(curve) is LineString:
        return create_list_LineStrings(curve)
    elif type(curve) is MultiLineString:
        lista_return = []
        for geom in curve.geoms:
            lista_return += create_list_LineStrings(geom)
        return lista_return
    else:
        raise Exception('curve is ' + str(type(curve)))


def gdf_closest(gdf1, gdf2):
    """Encontrar los puntos más cercanos de un GeoDataFrame a otro
     GeoDataFrame mediante cKDTree
    """
    serie1 = gdf1['geometry']
    serie2 = gdf2['geometry']

    arr_1 = np.array(list(serie1.apply(lambda x: (x.x, x.y))))
    arr_2 = np.array(list(serie2.apply(lambda x: (x.x, x.y))))

    cKDTree_2 = cKDTree(arr_2)

    distance, index = cKDTree_2.query(arr_1, k=1)

    gdf2_closest = (
        gdf2.iloc[index]
        .reset_index(drop=True)
        .rename(columns={'geometry': 'geometry_closest'})
    )

    gdf1 = gdf1.reset_index(drop=True)

    gdf1_final = gdf1.join(gdf2_closest)

    gdf1_final['distance'] = distance

    return gdf1_final


# ----- Conversión de coordenadas -----
source_crs = 'EPSG:4326'
target_crs = 'EPSG:5367'

latlon_to_CR = pyproj.Transformer.from_crs(source_crs, target_crs)


# Título de la aplicación
st.title(
    'Datos de la red vial, edificaciones y provincias del SNIT para análisis'
    ' con grafos'
)

# ----- Carga de datos -----

# Mostrar un mensaje mientras se cargan los datos de redvial_200k
estado_carga_redvial_200k = st.text('Cargando datos de redvial_200k...')
# Cargar los datos
red_vial_gdf, red_vial_simple, red_vial_gdf_nodes, G = (
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

# ----- Ruta más corta con el grafo -----

# Obtener la lista de categorías de edificaciones y construcciones
lista_categorias = (
    edificaciones_y_construcciones_gdf['categoria'].dropna().unique().tolist()
)

lista_categorias.sort()

# Seleccionar categoría de edificaciones y construcciones
categoria_seleccionada = st.selectbox(
    'Seleccione una categoría',
    lista_categorias
)

st.title("Haga clic en el mapa para seleccionar una ubicación")

# Inicializar estado
if "marker_location" not in st.session_state:
    st.session_state.marker_location = [9.9, -84.0]

# Crear mapa centrado en la última ubicación
m = folium.Map(location=st.session_state.marker_location, zoom_start=20)

# Agregar marcador en la posición actual
folium.Marker(
    location=st.session_state.marker_location,
    popup="Ubicación actual",
).add_to(m)

# Mostrar mapa y capturar clics
map_data = st_folium(m, height=500, width=700)

# Si el usuario hace clic, actualizar posición
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.marker_location = [lat, lon]

# Mostrar coordenadas
lat, lon = st.session_state.marker_location
CoordX, CoordY = latlon_to_CR.transform(lat, lon)
st.write(f"Posición actual del marcador: X={CoordX:.2f}, Y={CoordY:.2f}")

if st.button("Determinar ruta:"):
    list_nodes = (
        edificaciones_y_construcciones_gdf
        .loc[
            (
                edificaciones_y_construcciones_gdf['categoria'] ==
                categoria_seleccionada
            ),
            'node'
        ]
        .tolist()
    )

    # Se busca el nodo más cercano a ese punto y se usa como punto de inicio
    _, ix_nearest = red_vial_gdf_nodes.sindex.nearest(Point(CoordX, CoordY))

    node_nearest = red_vial_gdf_nodes.loc[ix_nearest, 'node'].values[0]

    source = node_nearest

    # Se determinan todas las rutas de cada punto a la edificación de la
    #  edificación y construcción más cercana
    lengths, paths = nx.multi_source_dijkstra(G, sources=list_nodes)

    # Se muestra la distancia:
    st.write(f"La distancia de la ruta más corta es: {lengths[source]}")

    # Obtener nodos de la ruta
    nodos_ruta = paths[source]

    # Filtrar ruta
    red_vial_gdf_nodes_ruta = (
        red_vial_gdf_nodes.loc[red_vial_gdf_nodes['node'].isin(nodos_ruta)]
    )

    # Filtrar nodo fuente
    red_vial_gdf_nodes_fuente = (
        red_vial_gdf_nodes.loc[red_vial_gdf_nodes['node'] == source]
    )

    # ----- Mapa con folium -----

    # Crear el mapa interactivo de la ruta
    mapa_ruta = red_vial_simple.explore()

    # Añadir las edificaciones y construcciones al mapa
    edificaciones_y_construcciones_gdf.explore(
        m=mapa_ruta,  # se usa el mapa que se creó en la instrucción anterior
        name='Edificaciones y Construcciones',
        marker_type='circle',
        marker_kwds={'radius': 20, 'color': 'red'},
        tooltip=['categoria', 'nombre'],
        popup=True
    )

    red_vial_gdf_nodes_ruta.explore(
        m=mapa_ruta,  # se usa el mapa que se creó en la instrucción anterior
        name='Ruta',
        marker_kwds={'color': 'black'},
        tooltip=['node'],
        popup=True
    )

    red_vial_gdf_nodes_fuente.explore(
        m=mapa_ruta,  # se usa el mapa que se creó en la instrucción anterior
        name='Fuente',
        marker_kwds={'color': 'yellow'},
        tooltip=['node'],
        popup=True
    )

    # Agregar un control de capas al mapa
    folium.LayerControl().add_to(mapa_ruta)

    # Mostrar el mapa
    st.subheader('Mapa de la ruta más corta')
    st_folium(mapa_ruta)
