import ee

def add_DpRVIc(image: ee.Image) -> ee.Image:
    """Adds a DualPol Radar Vegetation Index[1] band to Sentinel-1 images

    [1] Bhogapurapu, N., Dey, S., Mandal, D., Bhattacharya, A., Karthikeyan, L., McNairn, H., & Rao, Y. S. (2022). 
    Soil moisture retrieval over croplands using dual-pol L-band GRD SAR data. 
    In Remote Sensing of Environment (Vol. 271, p. 112900). Elsevier BV. https://doi.org/10.1016/j.rse.2022.112900 

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