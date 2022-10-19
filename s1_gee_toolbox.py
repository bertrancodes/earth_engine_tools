import ee

def add_DpRVIc(image):
    """Adds a DualPol Radar Vegetation Index band to Sentinel-1 images

    Parameters
    -----------
    image : ee.Image
         A Sentinel-1 GRD product

    """
    vv = image.select('VV')
    vh = image.select('VH')
    q = vh.divide(vv).rename('q')
    image = image.addBands([q])
    
    m_Expression = '(1 - q) / (1 + q)'
    beta_Expression = '1 / (1 + q)'
    dprvi_Expression = '1 - beta * m'
   
    m = image.expression(
        expression = m_Expression,
        opt_map = {'q': image.select('q')}
    ).rename('m')
    
    beta = image.expression(
        expression = beta_Expression,
        opt_map = {'q': image.select('q')}
    ).rename('beta')

    image = image.addBands([m, beta])
    
    dprvi_c = image.expression(
        expression = dprvi_Expression,
        opt_map = {
           'beta': image.select('beta'),
           'm': image.select('m') 
        }
    ).rename('DpRVIc')

    image = image.addBands([dprvi_c])
    
    return image.select(['VV', 'VH', 'DpRVIc'])