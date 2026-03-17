import pandas as pd
import folium
from folium.plugins import BeautifyIcon
import os

# Paths
data_path = r"c:\Users\Lenovo\OneDrive\Desktop\Real Estste Agent\RealEststeAgent\RealEststeAgent\static\house_price_dataset_india_12k.csv"
output_path = r"c:\Users\Lenovo\OneDrive\Desktop\Real Estste Agent\RealEststeAgent\RealEststeAgent\templates\location_map.html"

# 1. Load dataset
df = pd.read_csv(data_path)

# Custom mapping for cities since exact lat/lon isn't in original dataset
# Providing exact geographic centroids for our primary dataset cities
city_coords = {
    'Mumbai': {'Latitude': 19.0760, 'Longitude': 72.8777},
    'Pune': {'Latitude': 18.5204, 'Longitude': 73.8567},
    'Bangalore': {'Latitude': 12.9716, 'Longitude': 77.5946},
    'Hyderabad': {'Latitude': 17.3850, 'Longitude': 78.4867},
    'Nagpur': {'Latitude': 21.1458, 'Longitude': 79.0882}
}

# 2. Group by City and aggregate Property Count & Avg Price
city_stats = df.groupby('City').agg(
    Property_Count=('Market_Price_INR', 'count'),
    Avg_Price=('Market_Price_INR', 'mean')
).reset_index()

# 3. Join logic
city_stats['Latitude'] = city_stats['City'].map(lambda x: city_coords.get(x, {}).get('Latitude', 0))
city_stats['Longitude'] = city_stats['City'].map(lambda x: city_coords.get(x, {}).get('Longitude', 0))

# 4. Color logic requirement
def get_color(count):
    if count <= 100: return 'green'
    elif count <= 300: return 'yellow'
    elif count <= 600: return 'orange'
    else: return 'red'

# Generate Map centered roughly across India
m = folium.Map(location=[18.5, 76.0], zoom_start=5, tiles='CartoDB positron')

# Draw circles 
for idx, row in city_stats.iterrows():
    city = row['City']
    lat = row['Latitude']
    lon = row['Longitude']
    count = row['Property_Count']
    avg_price = row['Avg_Price']
    color = get_color(count)
    
    # Tooltip 
    tooltip_html = f"""
    <div style='font-family: Arial; padding: 5px; width: 180px;'>
        <h4 style='margin: 0 0 5px 0; color: #333;'>{city}</h4>
        <b>Properties:</b> {count}<br>
        <b>Avg Price:</b> ₹ {avg_price:,.0f}
    </div>
    """
    
    # Calculate radius size dynamically to represent property counts
    # (capped out roughly so huge discrepancies still look visually attractive)
    radius = min(count / 30, 60) + 12 
    
    folium.CircleMarker(
        location=[lat, lon],
        radius=radius,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.6,
        tooltip=tooltip_html,
        weight=2
    ).add_to(m)

# Legend Plugin logic natively with MacroElement
legend_html = '''
{% macro html(this, kwargs) %}
<div style="
    position: fixed; 
    bottom: 30px; left: 30px; width: 160px; height: 130px; 
    background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
    padding: 10px; border-radius: 5px; box-shadow: 2px 2px 5px rgba(0,0,0,0.5);">
    <b>Property Density</b><br>
    <i style="background:green; width:15px; height:15px; float:left; margin-right:5px; border-radius:50%;"></i> 0 - 100<br>
    <i style="background:yellow; width:15px; height:15px; float:left; margin-right:5px; border-radius:50%;"></i> 101 - 300<br>
    <i style="background:orange; width:15px; height:15px; float:left; margin-right:5px; border-radius:50%;"></i> 301 - 600<br>
    <i style="background:red; width:15px; height:15px; float:left; margin-right:5px; border-radius:50%;"></i> 601+<br>
</div>
{% endmacro %}
'''
from branca.element import MacroElement, Template
macro = MacroElement()
macro._template = Template(legend_html)
m.get_root().add_child(macro)

# Export Full Interactive Map
m.save(output_path)
print(f"Map successfully generated and saved to {output_path}")
