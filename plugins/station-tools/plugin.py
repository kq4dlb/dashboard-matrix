def render(widget_id, settings, station):
    if widget_id=='station-card':
        return {'format':'metrics','title':'Station Identity','metrics':[
          {'label':'Callsign','value':station.get('CALLSIGN','')},{'label':'Grid','value':station.get('GRIDSQUARE','')},
          {'label':'Latitude','value':station.get('LAT','')},{'label':'Longitude','value':station.get('LONG','')} ]}
    return {'format':'metrics','title':'Coordinates','metrics':[{'label':'Latitude','value':station.get('LAT','')},{'label':'Longitude','value':station.get('LONG','')} ]}
