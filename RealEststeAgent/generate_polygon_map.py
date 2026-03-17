import pandas as pd
import folium
import requests
import time
import os

# Set paths
base_dir = r"c:\Users\Lenovo\OneDrive\Desktop\Real Estste Agent\RealEststeAgent"
csv_path = os.path.join(base_dir, "RealEststeAgent", "static", "house_price_dataset_india_12k.csv")
html_path = os.path.join(base_dir, "RealEststeAgent", "templates", "location_map.html")

# Read data
df = pd.read_csv(csv_path)

# Aggregate properties by city
city_stats = df.groupby('City').agg(
    property_count=('House_ID', 'count'),
    avg_price=('Market_Price_INR', 'mean')
).reset_index()

# Initialize map centered on India with a premium dark theme
m = folium.Map(location=[19.5, 76.0], zoom_start=5, tiles='CartoDB dark_matter')

# Add density legend
legend_html = '''
<div style="
    position: fixed; 
    bottom: 30px; left: 30px; width: 220px; height: 160px; 
    background-color: rgba(30, 30, 30, 0.9); border:1px solid #444; z-index:9999; font-size:14px;
    padding: 15px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.6); color: #fff; font-family: 'Inter', sans-serif;">
    <b style="color: #00B98E; font-size: 15px; border-bottom: 1px solid #444; padding-bottom: 5px; display: block; margin-bottom: 10px;">Property Density</b>
    <i style="background:#20c997; width:14px; height:14px; float:left; margin-right:8px; border-radius:3px;"></i> 0 - 2000 listings<br>
    <i style="background:#ffc107; width:14px; height:14px; float:left; margin-right:8px; border-radius:3px; margin-top: 4px;"></i> 2001 - 2400 listings<br>
    <i style="background:#fd7e14; width:14px; height:14px; float:left; margin-right:8px; border-radius:3px; margin-top: 4px;"></i> 2401 - 2700 listings<br>
    <i style="background:#e83e8c; width:14px; height:14px; float:left; margin-right:8px; border-radius:3px; margin-top: 4px;"></i> 2701+ listings<br>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

headers = {
    'User-Agent': 'RealEstateApp/1.0 (info@estateiq.com)'
}

for _, row in city_stats.iterrows():
    city = row['City']
    count = row['property_count']
    price = row['avg_price']
    
    # Determine premium color (Teal, Gold, Coral, Pink)
    if count <= 2000:
        color = '#20c997'
        fill_opacity = 0.4
    elif count <= 2400:
        color = '#ffc107'
        fill_opacity = 0.5
    elif count <= 2700:
        color = '#fd7e14'
        fill_opacity = 0.6
    else:
        color = '#e83e8c'
        fill_opacity = 0.7
        
    # Fetch GeoJSON boundary
    url = f"https://nominatim.openstreetmap.org/search?city={city}&country=India&format=json&polygon_geojson=1"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200 and len(response.json()) > 0:
        data = response.json()[0]
        if 'geojson' in data:
            geojson = data['geojson']
            
            tooltip_html = f"""
            <div style='font-family: "Inter", sans-serif; padding: 10px; width: 190px; background-color: rgba(30, 30, 30, 0.95); color: #fff; border-radius: 6px; border: 1px solid #555;'>
                <h4 style='margin: 0 0 8px 0; color: {color}; border-bottom: 1px solid #555; padding-bottom: 5px;'>{city}</h4>
                <div style='display: flex; justify-content: space-between; margin-bottom: 4px;'>
                    <span style='color: #aaa;'>Listings:</span> 
                    <b>{int(count):,}</b>
                </div>
                <div style='display: flex; justify-content: space-between;'>
                    <span style='color: #aaa;'>Avg Price:</span> 
                    <b>₹ {price:,.0f}</b>
                </div>
            </div>
            """
            
            folium.GeoJson(
                geojson,
                style_function=lambda feature, color=color, fill_opacity=fill_opacity: {
                    'fillColor': color,
                    'color': color,
                    'weight': 1.5,
                    'fillOpacity': fill_opacity,
                    'opacity': 0.8
                },
                tooltip=tooltip_html
            ).add_to(m)
            
    # Respect Nominatim limits
    time.sleep(1.2)

m.save(html_path)
print("Map generated and saved to", html_path)
