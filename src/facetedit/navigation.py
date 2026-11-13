"""Validated, portable camera preferences and keyboard bindings."""
import math
import string

DEFAULT_BINDINGS={'forward':'w','back':'s','left':'a','right':'d','up':'e','down':'q','boost':'shift_l'}
KEYS=tuple(string.ascii_lowercase)+('space','up','down','left','right','prior','next','shift_l','shift_r')


def validate_navigation(raw):
    result={}
    for key,default,low,high in (('fov',65.,30,110),('speed',8.,1,64),('sensitivity',1.,.1,3),('boost',4.,1,16)):
        value=raw.get(key,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError(f'{key} must be between {low} and {high}')
        result[key]=float(value)
    invert=raw.get('invert_y',False)
    if type(invert) is not bool:raise ValueError('Invert look must be true or false')
    result['invert_y']=invert
    bindings=raw.get('bindings',DEFAULT_BINDINGS)
    if not isinstance(bindings,dict) or bindings.keys()!=DEFAULT_BINDINGS.keys() or any(v not in KEYS for v in bindings.values()):
        raise ValueError('Choose a supported key for every navigation action')
    if len(set(bindings.values()))!=len(bindings):raise ValueError('Navigation bindings must use different keys')
    # Space and the opposite Shift key are aliases only when unassigned.
    result['bindings']=dict(bindings)
    return result


def apply_navigation(view, values):
    values=validate_navigation(values)
    view.stop_flight()
    view.camera.fov=values['fov'];view.camera.speed=values['speed'];view.default_speed=values['speed']
    view.camera.sensitivity=values['sensitivity'];view.camera.invert_y=values['invert_y'];view.camera.boost_factor=values['boost']
    view.navigation_keys=dict(values['bindings'])
    view.schedule()
