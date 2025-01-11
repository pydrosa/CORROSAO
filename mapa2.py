import zipfile
import os
import geopandas as gpd
import folium
from folium.features import GeoJsonTooltip
import pandas as pd
from shapely.geometry import mapping
import json
import fiona

def create_and_export_corrosion_zones(zip_path, output_dir="output"):
    # Criar diretório de saída se não existir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 1. Carregar o shapefile da costa
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("temp")
    
    shapefile_path = None
    for root, dirs, files in os.walk("temp"):
        for file in files:
            if file.endswith(".shp"):
                shapefile_path = os.path.join(root, file)
                break
    
    coastline = gpd.read_file(shapefile_path)
    
    # 2. Carregar o shapefile do Brasil para fazer o recorte
    # Você pode baixar de: https://www.ibge.gov.br/geociencias/downloads-geociencias.html
    brasil = gpd.read_file('C:/Users/josep/Nova pasta/BR_UF_2023.shp')  # Substitua pelo caminho do seu arquivo
    alagoas = brasil[brasil['SIGLA_UF'] == 'AL']
    
    if coastline.crs != alagoas.crs:
        coastline = coastline.to_crs(alagoas.crs)
    
    # 3. Transformar para UTM para trabalhar com metros
    utm_crs = "EPSG:32724"  # UTM 24S
    coastline_utm = coastline.to_crs(utm_crs)
    alagoas_utm = alagoas.to_crs(utm_crs)
    
    # 4. Criar as zonas
    zones_data = [
        ("C5 - Muito Alta", 0, 2000),
        ("C4 - Alta", 2000, 5000),
        ("C3 - Média", 5000, 10000),
        ("C2 - Baixa", 10000, 20000)
    ]
    
    zones_list = []
    merged_coastline = coastline_utm.geometry.union_all()
    
    for name, inner, outer in zones_data:
        if inner == 0:
            zone = merged_coastline.buffer(outer)
        else:
            outer_buffer = merged_coastline.buffer(outer)
            inner_buffer = merged_coastline.buffer(inner)
            zone = outer_buffer.difference(inner_buffer)
        
        # Recortar com o limite de Alagoas
        zone = gpd.GeoDataFrame(geometry=[zone], crs=utm_crs)
        zone = gpd.overlay(zone, alagoas_utm, how='intersection')
        
        if not zone.empty:
            zone['Zone'] = name
            zones_list.append(zone)
    
    # 5. Combinar todas as zonas
    zones = pd.concat(zones_list, ignore_index=True)
    
    # 6. Converter para WGS 84 para exportação
    zones_wgs84 = zones.to_crs("EPSG:4326")
    
    # 7. Exportar em diferentes formatos
    # Shapefile
    zones_wgs84.to_file(os.path.join(output_dir, "zonas_corrosao.shp"))
    
    # GeoJSON
    zones_wgs84.to_file(os.path.join(output_dir, "zonas_corrosao.geojson"), driver='GeoJSON')
    
    # KML
    # Primeiro, garantir que temos os drivers necessários
    if 'KML' in fiona.supported_drivers:
        zones_wgs84.to_file(os.path.join(output_dir, "zonas_corrosao.kml"), driver='KML')
    
    # 8. Criar o mapa Folium para visualização
    bounds = zones_wgs84.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=9,
        tiles='cartodbpositron'
    )
    
    colors = {
        'C5 - Muito Alta': '#ff0000',
        'C4 - Alta': '#ff6600',
        'C3 - Média': '#ffcc00',
        'C2 - Baixa': '#99cc00'
    }
    
    # Adicionar as zonas ao mapa
    for idx, row in zones_wgs84.iterrows():
        feature = {
            'type': 'Feature',
            'properties': {'Zone': row['Zone']},
            'geometry': mapping(row.geometry)
        }
        
        feature_collection = {
            'type': 'FeatureCollection',
            'features': [feature]
        }
        
        style_function = lambda x, color=colors[row['Zone']]: {
            'fillColor': color,
            'color': color,
            'weight': 1,
            'fillOpacity': 0.5
        }
        
        folium.GeoJson(
            feature_collection,
            name=row['Zone'],
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['Zone'],
                aliases=['Zona de Corrosão:'],
                style='background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;'
            )
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    # Adicionar legenda
    legend_html = '''
    <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white;
                padding: 10px; border: 2px solid grey; border-radius: 5px">
        <p><strong>Zonas de Corrosão</strong></p>
        <p><span style="color: #ff0000;">■</span> C5 - Muito Alta (0-2km)</p>
        <p><span style="color: #ff6600;">■</span> C4 - Alta (2-5km)</p>
        <p><span style="color: #ffcc00;">■</span> C3 - Média (5-10km)</p>
        <p><span style="color: #99cc00;">■</span> C2 - Baixa (10-20km)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    m.fit_bounds(m.get_bounds())
    m.save(os.path.join(output_dir, "mapa_zonas_corrosao.html"))
    
    return "Arquivos salvos no diretório: " + output_dir

# Uso do código
try:
    zip_path = "COSTA ALAGOANA.zip"
    resultado = create_and_export_corrosion_zones(zip_path)
    print(resultado)
except Exception as e:
    print(f"Erro ao processar os dados: {str(e)}")
    import traceback
    traceback.print_exc()