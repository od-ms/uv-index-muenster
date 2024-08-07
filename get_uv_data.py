#!/usr/bin/env python
# coding=utf-8
"""
This script loads UV Index data from DWD
And saves it as csv and geojson
"""

import os
import os.path
import time
import csv
import json
import random
import logging
import datetime
from decimal import Decimal
from datetime import datetime
from pyfiglet import Figlet
import requests
from pyproj import Transformer


DATADIR = 'public/data/'

DWD_UVI_URL = 'https://maps.dwd.de/geoserver/ows?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&BBOX=404072.89991016534622759,5756457.63294644746929407,406854.51113235193770379,5758566.31513796653598547&CRS=EPSG:25832&WIDTH=1083&HEIGHT=821&LAYERS=dwd:UVIndex&STYLES=&FORMAT=image/png&QUERY_LAYERS=dwd:UVIndex&INFO_FORMAT=application/json&I=585&J=318'

HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/vnd.mds.provider+json;version=0.4'
}

COLOR_PALETTE = {
    2: '#4EB400',
    3: '#A0CE00',
    4: '#F7E400',
    5: '#F8B600',
    6: '#F88700',
    7: '#F85900',
    8: '#E82C0E',
    9: '#D8001D',
    10: '#FF0099',
    11: '#B54CFF',
    100: '#998CFF'
}
COLOR_PALETTE_ALT = {
    1: '#658D1B',
    2: '#84BD00',
    3: '#97D700',
    4: '#F7EA48',
    5: '#FCE300',
    6: '#FFCD00',
    7: '#ECA154',
    8: '#FF8200',
    9: '#EF3340',
    10: '#DA291C',
    11: '#BF0D3E',
    12: '#4B1E88',
    13: '#62e59F',
    14: '#794CB6',
    15: '#9063CD',
    16: '#A77AE4',
    17: '#BE91FB',
    18: '#D5ABFF',
    19: '#ECBFFF',
    20: '#FFD6FF',
    21: '#FFEDFF',
    100: '#FFFFFF'
}
COLOR_RISKS_LEVELS = {
    3: ['#97D700', 'Low', 'Niedrig'],
    6: ['#FCE300', 'Moderate', 'Mittel'],
    8: ['#FF8200', 'High', 'Hoch'],
    11: ['#EF3340', 'Very High', 'Sehr Hoch'],
    100: ['#9063CD', 'Extreme', 'Extrem']
}


# Basic logger configuration
logging.basicConfig(level=logging.DEBUG, format='<%(asctime)s %(levelname)s> %(message)s')
logging.addLevelName( logging.WARNING, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName( logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
logging.info("=====> START %s <=====", datetime.now())

# Use cosmic font, it rocks
HEADLINE_FONT = "standard"

SESSION = requests.Session()


def read_url_with_cache(cachefile_name, url):
    """Http Requests holen und zwischenspeichern"""
    filename = f'{cachefile_name}.json'

    current_ts = time.time()
    cache_max_age = 60 * 60 * 3 # hours
    generate_cache_file = True
    filecontent = "{}"
    if os.path.isfile(filename):
        file_mod_time = os.path.getmtime(filename)
        time_diff = current_ts - file_mod_time
        if time_diff > cache_max_age:
            logging.debug("# CACHE file age %s too old: %s", time_diff, filename)
        else:
            generate_cache_file = False
            logging.debug("(using cached file instead of url get)")
            with open(filename, "r", encoding="utf-8") as myfile:
                filecontent = "".join(line.rstrip() for line in myfile)

    if generate_cache_file:
        logging.debug("# URL HTTP GET %s ", filename)
        req = SESSION.get(url, headers=HEADERS)
        if req.status_code > 399:
            logging.error('  - Request result: HTTP %s - %s', req.status_code, req)
            raise FileNotFoundError

        open(filename, 'wb').write(req.content)
        filecontent = req.text
        time.sleep(1)

    jsn = json.loads(filecontent)
    if jsn.get('status') == 404:
        logging.warning('  - missing url: %s', url)
        return json.loads("{}")
    return jsn




def main():
    """Hauptmethode, hier passieren die wichtigen Dinge"""
    cache_filename = 'dwd-geoserver'
    url = DWD_UVI_URL
    big_debug_text(f"load {cache_filename}")
    logging.debug(".---------------------------------------------------------->>>>>>>>>>>>> . . ")
    logging.debug("| Fetching %s: %s", cache_filename, url)
    response = read_url_with_cache(cache_filename, url)
    logging.debug("RESPONSE %s bytes", len(str(response)))
    stationen = response.get('features')
    logging.debug("ANZAHL STATIONEN %s", len(stationen))
    value = stationen[0]['properties']['value']
    uv_value = f'{value:0.2f}'
    uv_date = stationen[0]['properties']['TIME']
    uv_timestamp = response.get('timeStamp')
    color_who = get_dict_value(uv_value, COLOR_PALETTE)
    color_alt = get_dict_value(uv_value, COLOR_PALETTE_ALT)
    uv_object = get_dict_value(uv_value, COLOR_RISKS_LEVELS)
    uv_name_en = uv_object[1]
    uv_name_de = uv_object[2]
    color_risklevel = uv_object[0]
    big_debug_text(f"UV-Index: {uv_value}")
    name = 'uv-index-muenster'

    write_json_file([[
        get_center(),
        {
            'date': uv_date,
            'uv-index': uv_value,
            'timestamp': uv_timestamp,
            'risk_level_en': uv_name_en,
            'risk_level_de': uv_name_de,
            'color': color_who,
            'color_alt': color_alt,
            'color_level': color_risklevel
        }]]
        , f'{DATADIR}{name}.json')

    write_csv_file(
        ['Timestamp','Date','UV-Index'],
        [[uv_timestamp, uv_date, uv_value]],
        f'{DATADIR}/{name}.csv')


def get_dict_value(uv_index, dictionary):
    """ look up the closest dictionary entry """
    uv_content = []
    for list_index, list_content in dictionary.items():
        if Decimal(uv_index) < Decimal(list_index):
            uv_content = list_content
            break
    logging.debug("Found %s -> %s", uv_index, uv_content)
    return uv_content


def write_json_file(data, outfile_name):
    """ Create and write output format: GeoJSON """

    big_debug_text("..write GeoJSON", "graceful")

    features = []
    for entry in data:

        features.append(
          {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": entry[0]
            },
            "properties": entry[1]
          }
        )

    logging.info('Got %s Stationen', len(features))

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    logging.info( "Writing file '%s'", outfile_name)
    with open(outfile_name, "w", encoding="utf-8") as outfile:
        json.dump(geojson, outfile, ensure_ascii=True, indent=2)


def write_csv_file(csv_header, data, outfile_name):
    """ Create and write output format: CSV """

    big_debug_text("..write CSV", "graceful")

    file_exists = os.path.isfile(outfile_name)

    with open(outfile_name, 'a', newline='', encoding='utf-8') as outfile:
        outwriter = csv.writer(outfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        if not file_exists:
            outwriter.writerow(csv_header)
        for datarow in data:
            outwriter.writerow(datarow)

    logging.info( "Number of entries: %s", len(data))
    logging.info( "Wrote file '%s'", outfile_name)


def get_center():
    """Berechnet den Mittelpunkt von bbox"""
    bbox_format = 'EPSG:25832'
    bbox = [
        [404072.89991016534622759,5756457.63294644746929407],
        [406854.51113235193770379,5758566.31513796653598547]
    ]
    v0 = bbox[0]
    v1 = bbox[1]
    half_x = (v1[0]-v0[0])/2
    half_y = (v1[1]-v0[1])/2
    x = v0[0] + half_x
    y = v0[1] + half_y
    transformer = Transformer.from_crs(bbox_format, "EPSG:4326")
    lat_lon = transformer.transform(x,y)

    # Calculated position is not cool enough, lets return Domplatz instead
    return [7.625567054486122, 51.962577929548495]


def big_debug_text(text, font=HEADLINE_FONT):
    """ Write some fancy big text into log-output """
    custom_fig = Figlet(font=font, width=120)
    logging.info("\n\n%s", custom_fig.renderText(text))



big_debug_text("START...")

main()

big_debug_text("DONE!")
