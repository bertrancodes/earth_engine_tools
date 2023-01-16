import ee
from time import sleep

from rich.live import Live
from rich.table import Table
from rich.progress import Progress, TimeElapsedColumn, TextColumn, SpinnerColumn


def zonalStats(ic: ee.ImageCollection, fc: ee.FeatureCollection, **params) -> ee.FeatureCollection:
    """ 
    Python traslation of user "swinswm" zonalStats function for the GEE JavaScript API.
    Returns zonal statistics for the selected ImageCollection over the FeatureCollection
    
    Parameters
    -----------
    ic : ee.ImageCollection
         Image collection to extract values from

    fc : ee.FeatureCollection
         Feature collection that provides regions to reduce image pixels by
    
    **params :
    |
    |---- reducer : ee.Reducer -> defaults to ee.Reducer.mean()
    |               The reducer to apply. Two additional string options: "classic"
    |               performs ee.Reducer.mean() and ee.Reducer.stdDev() and "full"
    |               performs ee.Reducer.mean(), ee.Reducer.stdDev(), ee.Reducer.median(), 
    |               ee.Reducer.min() and ee.Reducer.max(). Optional 
    |
    |---- scale : int -> defaults to None
    |               A nominal scale in meters of the projection to work in. If None, 
    |               the native nominal image scale is used. Optional.
    |
    |---- crs : str -> defaults to None
    |               The projection to work in. If None, the native image CRS
    |               is used. Optional.
    |
    |---- bands : list of str -> defaults to None
    |               A list of image band names to reduce values for. If None, all bands 
    |               will be reduced. Band names define column names in the resulting 
    |               reduction table. Optional.
    |
    |---- bandsRename : list of str -> defaults to None
    |               A list of desired image band names. The lenght and order must
    |               correspond to the params['bands'] list. If None, band names 
    |               will be unchanged. Band names define column names in the 
    |               resulting reduction table. Optional.
    |
    |---- imgProps : list of str -> defaults to None
    |               A list of image properties to include in the table of region
    |               reduction results. If None, all image properties are included. Optional
    |
    '---- imgPropsRename : list of str -> defaults to None
                    A list of image property names to replace those provided by 
                    params['imgProps']. The lenght and order must match the
                    params['imgProps'] entries. Optional.

    
    """
    # Initialize default parameters.
    imgRep = ic.first()
    nonSystemImgProps = ee.Feature(geom = None).copyProperties(imgRep).propertyNames()

    defaults = {
    'reducer': ee.Reducer.mean(),
    'scale': None,
    'crs': None,
    'bands': imgRep.bandNames(),
    'bandsRename': None,
    'imgProps': nonSystemImgProps,
    'imgPropsRename': None,
    'datetimeName': 'datetime',
    'datetimeFormat': 'YYYY-MM-dd HH:mm:ss'
    }

    # Replace default parameters for user supplied ones if any
    for default in defaults:
        param = params.get(default, None)
        if param is None:
            params[default] = defaults[default]
    
    if params['imgPropsRename'] is None:
       params['imgPropsRename'] = params['imgProps']
    
    if params['bandsRename'] is None:
        params['bandsRename'] = params['bands']
    
    if params['reducer'] == 'classic':
        params.update({'reducer': ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs = True)})
        band_props = [band + '_mean' for band in iter(params['bandsRename'])]
        band_props.extend([band + '_stdDev' for band in iter(params['bandsRename'])])

    elif params['reducer'] == 'full':
        params.update({'reducer': ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs = True)
        .combine(ee.Reducer.median(), sharedInputs = True)
        .combine(ee.Reducer.min(), sharedInputs = True)
        .combine(ee.Reducer.max(), sharedInputs = True)
        })
        band_props = [band + '_mean' for band in iter(params['bandsRename'])]
        band_props.extend([band + '_stdDev' for band in iter(params['bandsRename'])])
        band_props.extend([band + '_median' for band in iter(params['bandsRename'])])
        band_props.extend([band + '_min' for band in iter(params['bandsRename'])])
        band_props.extend([band + '_max' for band in iter(params['bandsRename'])])
    
    else:
        band_props = params['bandsRename']

  # Map the reduceRegions function over the image collection.
    def ic_reducedRegions(img):
        img = ee.Image(img.select(params['bands'], params['bandsRename'])).set(params['datetimeName'], img.date().format(params['datetimeFormat'])).set('timestamp', img.get('system:time_start'))


        propsFrom = ee.List(params['imgProps']).cat(ee.List([params['datetimeName'], 'timestamp']))
        propsTo = ee.List(params['imgPropsRename']).cat(ee.List([params['datetimeName'], 'timestamp']))
        imgProps = img.toDictionary(propsFrom).rename(propsFrom, propsTo)

        # Subset points that intersect the given image.
        fcSub = fc.filterBounds(img.geometry())

        return img.reduceRegions(
        collection = fcSub,
        reducer = params['reducer'],
        scale = params['scale'],
        crs = params['crs']
        ).map(lambda feat: feat.set(imgProps))

    results = (ic.map(ic_reducedRegions)).flatten().filter(ee.Filter.notNull(band_props))
    return results



def fancy_status(status, name):
    if status == 'COMPLETED':
        fancy_status = '✅ ' + '[green]' + name+': ' + status
        return fancy_status
    elif status in ['CANCELLED', 'FAILED']:
        fancy_status = '❌ ' + '[red]' + name+': ' + status
        return fancy_status
    else:
        fancy_status = '⏳ ' + '[cyan]' + name +': '+ status + '...'
        return fancy_status


def showTaskManager(tasks):

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    )
    
    task_names = []
    
    with progress as p:
        # Initialize tasks
        for task in tasks:
            task_names.append(task.status().get('description'))
            p.add_task(f"", start=True)
        while not set([task.status().get('state') for task in tasks]).issubset(['COMPLETED', 'SUCCEEDED', 'CANCELLED', 'FAILED']):
            for i, taskID in enumerate(p.task_ids):
                status = [task.status().get('state') for task in tasks][i]
                name = task_names[i]

                #status = task.status().get('state')
                p.update(taskID, description = '{:<3} {:<35}'.format(*fancy_status(status, name).split(' ',1)))
                if status in ['COMPLETED', 'CANCELLED']:
                    p.advance(taskID, advance=100)
            sleep(10)
    return