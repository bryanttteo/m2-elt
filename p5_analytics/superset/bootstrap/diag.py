import zipfile, yaml
from superset.app import create_app
app=create_app()
with app.app_context():
    from superset.dashboards.schemas import ImportV1DashboardSchema
    from superset.charts.schemas import ImportV1ChartSchema
    from superset.datasets.schemas import ImportV1DatasetSchema
    from superset.databases.schemas import ImportV1DatabaseSchema
    from marshmallow import ValidationError
    z=zipfile.ZipFile("/app/dist/olist_bundle.zip")
    contents={n.split("olist_bundle/",1)[1]:z.read(n).decode() for n in z.namelist()}
    schemas={"databases/":ImportV1DatabaseSchema(),"datasets/":ImportV1DatasetSchema(),"charts/":ImportV1ChartSchema(),"dashboards/":ImportV1DashboardSchema()}
    for path,raw in sorted(contents.items()):
        for pref,sch in schemas.items():
            if path.startswith(pref):
                try: sch.load(yaml.safe_load(raw)); 
                except ValidationError as e: print("FAIL",path,"->",e.messages)
    print("done")
