"""
Curve manipulation utilities for NURBS curves in Maya rigging.
Provides functions for modifying curve properties like color and thickness.
"""

import maya.cmds as cmds


def set_curve_thickness(curves, thickness):
    """
    Set line thickness for NURBS curves.
    
    Args:
        curves (str or list): Curve node name(s) to modify
        thickness (float): Line width value (typically 1.0-3.0)
    
    Returns:
        None
    """
    if isinstance(curves, str):
        curves = [curves]
    
    for curve in curves:
        cmds.setAttr(f"{curve}.overrideEnabled", 1)
        
        if cmds.attributeQuery("lineWidth", node=curve, exists=True):
            cmds.setAttr(f"{curve}.lineWidth", thickness)
        else:
            cmds.addAttr(curve, longName="lineWidth", attributeType="float", defaultValue=1)
            cmds.setAttr(f"{curve}.lineWidth", keyable=True)
            cmds.setAttr(f"{curve}.lineWidth", thickness)


def set_curve_color(curves, color_index):
    """
    Set override color for NURBS curves.
    
    Args:
        curves (str or list): Curve node name(s) to modify
        color_index (int): Maya color index (1-31)
    
    Returns:
        None
    """
    if isinstance(curves, str):
        curves = [curves]
    
    for curve in curves:
        cmds.setAttr(f"{curve}.overrideEnabled", 1)
        cmds.setAttr(f"{curve}.overrideColor", color_index)


def get_curve_shapes(obj):
    """
    Get NURBS curve shape nodes from a transform.
    
    Args:
        obj (str): Transform node name
    
    Returns:
        list: List of shape node paths
    """
    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
    return shapes if shapes else []


def style_curve(curve_transform, color_index=None, thickness=None):
    """
    Apply color and/or thickness styling to a curve in one call.
    
    Args:
        curve_transform (str): Curve transform node name
        color_index (int, optional): Maya color index (1-31)
        thickness (float, optional): Line width value
    
    Returns:
        None
    """
    shapes = get_curve_shapes(curve_transform)
    if not shapes:
        cmds.warning(f"No curve shapes found for {curve_transform}")
        return
    
    shape = shapes[0]
    
    if color_index is not None:
        set_curve_color(shape, color_index)
    
    if thickness is not None:
        set_curve_thickness(shape, thickness)
