"""
Data models for the TCR simulation application.
"""


class Geometry:
    """Represents a single solid block in the system."""
    def __init__(self, name, length, width, height):
        self.name = name
        self.length = length  # float in meters
        self.width = width    # float in meters
        self.height = height  # float in meters
        self.area = length * width  # automatically calculated (m^2)
    
    def is_valid(self):
        """Check if all parameters are set and valid."""
        return (self.name and len(self.name.strip()) > 0 and
                self.length and self.length > 0 and
                self.width and self.width > 0 and
                self.height and self.height > 0)
    
    def __repr__(self):
        return f"Geometry({self.name}, L={self.length}, W={self.width}, H={self.height})"


class Interface:
    """Represents the contact interface between two adjacent geometries."""
    def __init__(self, geom_top, geom_bottom, has_tcr=False):
        self.geom_top = geom_top
        self.geom_bottom = geom_bottom
        self.has_tcr = has_tcr
        # A_nominal is the minimum contact area between the two surfaces
        self.A_nominal = min(geom_top.area, geom_bottom.area)
    
    def __repr__(self):
        return f"Interface({self.geom_top.name} → {self.geom_bottom.name}, TCR={self.has_tcr}, A_nominal={self.A_nominal:.6f})"
