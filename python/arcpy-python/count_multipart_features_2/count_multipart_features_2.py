#-------------------------------------------------------------------------------
# Name:        Count Multipart
# Purpose:     This takes an input feature class/shapefile, adds a new field
#              and adds a value for how many features make up each multipart
#
# Author:      Lucas Danzinger/Hayden Welch
#
# Created:     30/05/2013 (Lucas Danzinger) - Original script
#              01/02/2024 (Hayden Welch) - Updated Version with handler class
#-------------------------------------------------------------------------------

import arcpy
import os
from typing import Generator, Any

class Feature:
    """
    This class will handle the describe object and provide a few properties
    and cursor methods
    """
    def __init__(self, path: str) -> None:
        if not arcpy.Exists(path): # Validate that the input feature exists
             raise ValueError(f"{path} does not exist")
        self.__dict__ = arcpy.da.Describe(path)  # Write the describe object to the instance attributes
        
    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]
    
    @property
    def workspace_path(self) -> os.PathLike:
        return self.workspace.catalogPath
    
    @property
    def shape_type(self) -> str:
        return self.shapeType
    
    @property
    def id_field(self) -> str:
        # Data Access cursors can handle the OID with OID@
        return 'OID@'  # self.OIDFieldName
    
    @property
    def shape_field(self) -> str:
        # Data Access requires SHAPE@ to get the geometry object
        return 'SHAPE@'  # self.shapeFieldName
    
    def get_rows(self, fields: list[str], *,
              query: str=None) -> Generator[dict[str, Any], None, None]:
        """This function will take an input feature class and get rows based on a query
        featureclass: The path to the feature class
        fields: The fields to be retrieved
        query: The query to be used to select the rows to be retrieved
        return: A generator of the rows to be retrieved (row_dict)
        """
        with arcpy.da.SearchCursor(self.catalogPath, fields, query) as cursor:
            for row in cursor:
                yield dict(zip(cursor.fields, row))
        return
    
    def update_rows(self, fields: list[str], *,
                 query: str=None) -> Generator[tuple[arcpy.da.UpdateCursor, dict[str, Any]], None, None]:
        """This function will take an input feature class and update rows based on a query
        featureclass: The path to the feature class
        fields: The fields to be updated
        query: The query to be used to select the rows to be updated
        return: A generator of the rows to be updated (cursor, row_dict)
        """
        with arcpy.da.UpdateCursor(self.catalogPath, fields, query) as cursor:
            for row in cursor:
                yield (cursor, dict(zip(cursor.fields, row)))
        return

def count_multipart(feature_path: os.PathLike, *,
                    field_name: str="PartCount", 
                    overwrite: bool=False,
                    report_only: bool=False):
    """This function will take an input feature class and add a new field
    featureclass: The path to the feature class
    field_name: The name of the count field to be added ("PartCount" by default)
    """
    # Get the Feature object
    feature_class: Feature = Feature(feature_path)
    
    # Set the workspace to the feature class workspace
    arcpy.env.workspace = feature_class.workspace_path
    
    # MultiPatch is not supported for multipart features
    if feature_class.shape_type == "MultiPatch":
        raise ValueError("This is not a supported geometry shape type. Please select a Multipoint, Polyline, or Polygon")
    
    # Count the number of parts for each multipart feature and add it to a dictionary
    multipart_counts: dict[str, Any] = \
        {
            row[feature_class.id_field]: row[feature_class.shape_field].partCount  # Get the number of parts for each multipart
            for row in feature_class.get_rows([feature_class.id_field, feature_class.shape_field])
            if row[feature_class.shape_field] and row[feature_class.shape_field].isMultipart  # Only get the rows that are multipart
        }
    
    # Don't bother updating the rows if there are no multipart features
    if len(multipart_counts) == 0:
        print("No multipart features found")
        return
    
    if not report_only:  # Only set up the output field and update the rows if we are not just reporting
        # Set up the output field
        if field_name in feature_class.field_names:
            if not overwrite:
                raise ValueError(f"The field {field_name} already exists in {feature_path}")
            else:
                arcpy.DeleteField_management(feature_path, field_name)

        arcpy.AddField_management(feature_path, field_name, 'SHORT')  # Add the field
    
        # Update the rows with part counts
        with arcpy.da.Editor(feature_class.workspace_path):
            upd_keys: list[str] = [str(k) for k in multipart_counts.keys()]
            # Use the OIDFieldName to build the SQL query, OBJECTID and OID@ dont work in queries
            update_query = f"{feature_class.OIDFieldName} IN ({','.join(upd_keys)})"  # Only update the rows that are in the dictionary
            # Use _update_rows to get a row dictionary so we can update the row using field names
            for cursor, row in feature_class.update_rows([feature_class.id_field, field_name], query=update_query):
                row[field_name] = multipart_counts[row[feature_class.id_field]]  # Get the part count from the dictionary
                cursor.updateRow(list(row.values()))  # Convert the dictionary to a list and update the row
                     
    print(f"{len(multipart_counts)} multipart features found in {feature_class.baseName}")

def main():
    
    # Set these
    feature_class = r"path\to\feature_class"
    count_field = 'PartCount'
    overwrite = True
    report_only = False
    
    count_multipart(feature_class, field_name=count_field, overwrite=overwrite, report_only=report_only)
    
    # Example of an iterative call (uncomment and fill out to use)
    #
    #workspace = r'path\to\workspace'
    #count_field = 'PartCount'
    #overwrite = True
    #dataset = 'Landbase'
    #wildcard = None
    #arcpy.env.workspace = workspace
    #for fc in arcpy.ListFeatureClasses(feature_dataset=dataset, wild_card=wildcard):
    #    count_multipart(fc, field_name=count_field, overwrite=True, report_only=True)

if __name__ == "__main__": 
    main()