import ee


def zonalStats(ic, fc, **params):
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
    |               The reducer to apply
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

    _params = {
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
    for _param in _params:
        param = params.get(_param, None)
        if param is None:
            params[_param] = _params[_param]
    
    if params['imgPropsRename'] is None:
       params['imgPropsRename'] = params['imgProps']
    if params['bandsRename'] is None:
        params['bandsRename'] = params['bands']

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

    results = (ic.map(ic_reducedRegions)).flatten().filter(ee.Filter.notNull(params['bandsRename']))
    return results

