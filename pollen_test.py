import os
from pathlib import Path
from geopy.geocoders import Nominatim
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv


def load_api_key() -> str:
    dotenv_path = Path(__file__).with_name('.env')
    load_dotenv(dotenv_path=dotenv_path)

    return (
        os.getenv('AMBEE_API_KEY')
        or os.getenv('AMBEE_KEY')
        or os.getenv('API_KEY')
        or ''
    ).strip().strip('"').strip("'")


def fetch_pollen(lat: float, lng: float, api_key: str) -> tuple[int, dict]:
    url = 'https://api.ambeedata.com/latest/pollen/by-lat-lng'
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
    }
    params = {'lat': lat, 'lng': lng}
    response = requests.get(url, headers=headers, params=params, timeout=20)

    payload = {}
    try:
        payload = response.json()
    except Exception:
        pass

    return response.status_code, payload


def risk_color(level: str | None) -> list[int]:
    colors = {
        'Very Low': [56, 142, 60, 180],
        'Low': [76, 175, 80, 180],
        'Moderate': [255, 193, 7, 200],
        'High': [255, 87, 34, 220],
        'Very High': [183, 28, 28, 230],
    }
    return colors.get(level or '', [33, 150, 243, 180])

def area_to_coords(area: str) -> tuple[float, float]:
    geolocator = Nominatim(user_agent="pollen_map_app")
    location = geolocator.geocode(area)
    if not location:
        raise ValueError(f"Area not found: {area}")
    return location.latitude, location.longitude


def high_pollen_types(risk: dict) -> list[str]:
    high_levels = {'High', 'Very High'}
    triggered = []
    for pollen_type in ('tree_pollen', 'grass_pollen', 'weed_pollen'):
        if risk.get(pollen_type) in high_levels:
            triggered.append(pollen_type.replace('_pollen', '').title())
    return triggered


def main() -> None:
    st.set_page_config(page_title='Pollen Map', page_icon=':seedling:', layout='wide')
    st.title('Pollen Map')
    st.caption('Live pollen risk from Ambee by Country city area.')

    api_key = load_api_key()
    if not api_key:
        st.error(
            'Missing API key in .env. Add one of: AMBEE_API_KEY, AMBEE_KEY, API_KEY.'
        )
        st.code('AMBEE_API_KEY=your_real_ambee_key', language='bash')
        st.stop()

    col1, col2 = st.columns([3, 1])
    with col1:
        area = st.text_input('Area / City/country', value='New york city')
    with col2:
        run = st.button('Get Pollen Data', type='primary', use_container_width=True)

    if not run:
        st.info('Enter an area/city and click Get Pollen Data.')
        return

    try:
        lat, lng = area_to_coords(area)
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f'Geocoding failed: {exc}')
        return

    st.caption(f'Coordinates used: {lat:.5f}, {lng:.5f}')

    with st.spinner('Fetching pollen data...'):
        status_code, payload = fetch_pollen(lat, lng, api_key)

    if status_code in (401, 403):
        st.error('Authentication failed (401/403). Check your Ambee API key in .env.')
        return

    if status_code != 200:
        st.error(f'API error: {status_code}')
        if payload:
            st.json(payload)
        return

    row = (payload.get('data') or [{}])[0]
    risk = row.get('Risk', {})
    counts = row.get('Count', {})
    updated_at = row.get('updatedAt', 'n/a')
    high_types = high_pollen_types(risk)

    if high_types:
        joined_types = ', '.join(high_types)
        st.warning(
            f'Medication reminder: {joined_types} pollen is high. '
            'Consider taking your allergy medication as prescribed.'
        )
    else:
        st.success('No high pollen types right now.')

    tree_level = risk.get('tree_pollen')
    map_data = [
        {
            'lat': float(lat),
            'lon': float(lng),
            'label': f"Tree {tree_level or 'n/a'}",
            'color': risk_color(tree_level),
        }
    ]

    st.subheader('Map')
    deck = pdk.Deck(
        map_style=pdk.map_styles.LIGHT,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lng, zoom=10, pitch=0),
        layers=[
            pdk.Layer(
                'ScatterplotLayer',
                data=map_data,
                get_position='[lon, lat]',
                get_radius=1200,
                get_fill_color='color',
                pickable=True,
            )
        ],
        tooltip={'text': '{label}'},
    )
    st.pydeck_chart(deck, use_container_width=True)

    st.subheader('Pollen Details')
    a, b, c = st.columns(3)
    a.metric('Tree Pollen', risk.get('tree_pollen', 'n/a'))
    b.metric('Grass Pollen', risk.get('grass_pollen', 'n/a'))
    c.metric('Weed Pollen', risk.get('weed_pollen', 'n/a'))

    x, y, z = st.columns(3)
    x.metric('Tree Count', counts.get('tree_pollen', 'n/a'))
    y.metric('Grass Count', counts.get('grass_pollen', 'n/a'))
    z.metric('Weed Count', counts.get('weed_pollen', 'n/a'))

    st.caption(f'Updated at: {updated_at}')


if __name__ == '__main__':
    main()
