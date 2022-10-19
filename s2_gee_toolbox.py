import ee

def add_NDVI(image):
    """Adds a Normalized Difference Vegetation Index band to Sentinel-2 images

    Parameters
    -----------
    image : ee.Image
         A Sentinel-2 SR product

    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
    return image.addBands([ndvi])

def add_DVI(image):
    """Adds a Difference Vegetation Index band to Sentinel-2 images

    Parameters
    -----------
    image : ee.Image
         A Sentinel-2 SR product

    """
    red = image.select('B4')
    nir = image.select('B8')
    dvi = nir.subtract(red).rename('dvi')
    dvi = dvi.divide(1e4)
    return image.addBands([dvi])

def get_cloudless_col(aoi, start_date, end_date, **params):

    """ Returns a cloud free Sentinel-2 ImageCollection

    Parameters
    -----------
    aoi : ee.Geometry or ee.Feature or ee.FeatureCollection
         Area of interest to filter the image collection to

    start_date : str
         Initial date for the Sentine-2 image collection (inclusive)

    end_date : str
         Final date for the Sentinel-2 image collection (exclusive)

    **params : 
    |
    |---- CLOUD_FILTER : int -> Defaults to 60
    |               Maximum image cloud cover percent allowed in image collection
    |
    |---- CLD_PRB_THRESH : int -> Defaults to 50
    |               Cloud probability in percentage. Values greater than it are
    |               considered cloud
    |
    |---- NIR_DRK_THRESH : float -> Defaults to 0.15
    |               Near infrared reflectance ranging from 0 to 1. Values less than
    |               it are considered potential cloud shadows
    |
    |---- CLD_PROJ_DIST : float -> Defaults to 1
    |               Maximum distance in km to search for cloud shadows from cloud edges
    |
    '---- BUFFER : int -> Defaults to 50
                    Distance in m to dilate the edge of could-identified objects

    """

    # Initialize default paramters
    _params = {
        'CLOUD_FILTER': 60,
        'CLD_PRB_THRESH': 50,
        'NIR_DRK_THRESH': 0.15,
        'CLD_PRJ_DIST': 1,
        'BUFFER': 50
    }

    # Replace default parameters for user supplied ones if any
    for _param in _params:
        param = params.get(_param, None)
        if param is None:
            params[_param] = _params[_param]


    # Import and filter S2 SR.
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR')
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', params['CLOUD_FILTER'])))

    # Import and filter s2cloudless.
    s2_cloudless_col = (ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
        .filterBounds(aoi)
        .filterDate(start_date, end_date))

    # Join the filtered s2cloudless collection to the SR collection by the 'system:index' property.
    ic = ee.ImageCollection(ee.Join.saveFirst('s2cloudless').apply(**{
        'primary': s2_sr_col,
        'secondary': s2_cloudless_col,
        'condition': ee.Filter.equals(**{
            'leftField': 'system:index',
            'rightField': 'system:index'
        })
    }))

    def add_cloud_bands(img):
        # Get s2cloudless image, subset the probability band.
        cld_prb = ee.Image(img.get('s2cloudless')).select('probability')

        # Condition s2cloudless by the probability threshold value.
        is_cloud = cld_prb.gt(params['CLD_PRB_THRESH']).rename('clouds')

        # Add the cloud probability layer and cloud mask as image bands.
        return img.addBands(ee.Image([cld_prb, is_cloud]))

    def add_shadow_bands(img):
        # Identify water pixels from the SCL band.
        not_water = img.select('SCL').neq(6)

        # Identify dark NIR pixels that are not water (potential cloud shadow pixels).
        SR_BAND_SCALE = 1e4
        dark_pixels = img.select('B8').lt(params['NIR_DRK_THRESH']*SR_BAND_SCALE).multiply(not_water).rename('dark_pixels')

        # Determine the direction to project cloud shadow from clouds (assumes UTM projection).
        shadow_azimuth = ee.Number(90).subtract(ee.Number(img.get('MEAN_SOLAR_AZIMUTH_ANGLE')));

        # Project shadows from clouds for the distance specified by the CLD_PRJ_DIST input.
        cld_proj = (img.select('clouds').directionalDistanceTransform(shadow_azimuth, params['CLD_PRJ_DIST']*10)
            .reproject(**{'crs': img.select(0).projection(), 'scale': 100})
            .select('distance')
            .mask()
            .rename('cloud_transform'))

        # Identify the intersection of dark pixels with cloud shadow projection.
        shadows = cld_proj.multiply(dark_pixels).rename('shadows')

        # Add dark pixels, cloud projection, and identified shadows as image bands.
        return img.addBands(ee.Image([dark_pixels, cld_proj, shadows]))

    def add_cld_shdw_mask(img):
        # Add cloud component bands.
        img_cloud = add_cloud_bands(img)

        # Add cloud shadow component bands.
        img_cloud_shadow = add_shadow_bands(img_cloud)

        # Combine cloud and shadow mask, set cloud and shadow as value 1, else 0.
        is_cld_shdw = img_cloud_shadow.select('clouds').add(img_cloud_shadow.select('shadows')).gt(0)

        # Remove small cloud-shadow patches and dilate remaining pixels by BUFFER input.
        # 20 m scale is for speed, and assumes clouds don't require 10 m precision.
        is_cld_shdw = (is_cld_shdw.focalMin(2).focalMax(params['BUFFER']*2/20)
            .reproject(**{'crs': img.select([0]).projection(), 'scale': 20})
            .rename('cloudmask'))

        # Add the final cloud-shadow mask to the image.
        return img_cloud_shadow.addBands(is_cld_shdw)

    def apply_cld_shdw_mask(img):
        # Subset the cloudmask band and invert it so clouds/shadow are 0, else 1.
        not_cld_shdw = img.select('cloudmask').Not()

        # Subset reflectance bands and update their masks, return the result.
        return img.select('B.*').updateMask(not_cld_shdw)

    return ic.map(add_cld_shdw_mask).map(apply_cld_shdw_mask)

