from datetime import datetime

from arcpy import (
    Exists, 
    Describe,
    Geometry,
)

from typing import (
    Generator,
    Any,
)

from arcpy.da import (
    Editor,
    SearchCursor,
    UpdateCursor,
    InsertCursor,
)

import arcpy.typing.describe as typedesc

from dataclasses import dataclass

@dataclass
class Changes:
    updates: list[int]
    inserts: list[int]
    deletes: list[int]
           
class TableUpdater: 
    
    Row = tuple[int, Geometry, datetime] # Type first 3 values of Row records
     
    def __init__(self, source_table: str, target_table: str) -> None:
        if not Exists(source_table) and Exists(target_table):
            raise ValueError('Invalid table paths!')
        
        self.target_table = target_table
        self.target_desc: typedesc.FeatureClass = Describe(target_table)
        
        self.source_table = source_table
        self.source_desc: typedesc.FeatureClass = Describe(source_table)
        
        # Do some filering to make sure we can use OID@ and SHAPE@ for the table cursors
        # By default a cursor will return SHAPE@XY
        self.source_shape_field = self.source_desc.shapeFieldName
        self.source_oid_field = self.source_desc.OIDFieldName
        self.source_fields = [field.name for field in self.source_desc.fields]
        
        self.target_shape_field = self.target_desc.shapeFieldName
        self.target_oid_field = self.target_desc.OIDFieldName
        self.target_fields = [field.name for field in self.target_desc.fields]
        
        self.target_editor = Editor(self.target_desc.workspace.catalogPath)
                
        self.fields = ['OID@', 'SHAPE@', 'EDITED@'] + [
            field
            for field in 
            set(self.source_fields) | set(self.target_fields)
            if field not in [self.source_oid_field, self.target_oid_field, self.source_shape_field, self.target_shape_field]
        ]
        
        self._table_diff = None
        
    @property
    def source_state(self):
        return self._gather_rows(self.source_table)
    
    @property
    def target_state(self):
        return self._gather_rows(self.target_table)
    
    @property
    def table_diff(self):
        if not self._table_diff:
            self._table_diff = self._get_table_diff()
        return self._table_diff
    
    def _gather_rows(self, table: str) -> dict[int, str]:
        """Gather all rows and their last updated times
        
        Parameters:
            table (str): Path to the table that needs updating
            
        Returns:
            ( dict[int, str] ): Mapping of OID to updated_at string
        """
        return {oid: updated_at for oid, updated_at in SearchCursor(table, ['OID@', 'EDITED@'])}
    
    def _get_table_diff(self) -> Changes:
        """Filter out records from the new_table that are unchanged from the old_table
        
        Returns:
            a list of OIDs in the new_table that need to be 
        """
        old_rows = self.target_state
        new_rows = self.source_state
        return Changes(
            updates=list(oid for oid in new_rows if oid in old_rows and old_rows[oid] < new_rows[oid]), 
            inserts=list(new_rows.keys() - old_rows.keys()), 
            deletes=list(old_rows.keys() - new_rows.keys()),
        )
    
    # Change Detection methods
    def _inserts(self) -> list[tuple[Any, ...]] | None:
        inserts = self.table_diff.inserts
        if inserts:
            if len(inserts) == 1:
                where_clause = f"{self.source_oid_field} = {inserts[0]}"
            else:    
                where_clause = f"{self.source_oid_field} IN ({','.join(map(str, inserts))})"
                
            return [row for row in SearchCursor(self.source_table, self.fields, where_clause=where_clause)]
    
    def _updates(self) -> dict[int, tuple[Any, ...]] | None:
        updates = self.table_diff.updates
        if updates:
            if len(updates) == 1:
                where_clause=f"{self.source_oid_field} = ({updates[0]})"
            else:
                where_clause=f"{self.source_oid_field} IN ({','.join(map(str, updates))})"
                
            return {
                row[0]: row
                for row in SearchCursor(self.source_table, self.fields, where_clause=where_clause)
            }
    
    def _deletes(self) -> list[int] | None:
        return self.table_diff.deletes or None
    
    def apply_changes(self) -> dict[str, list[int]]:
        """Applies all changed rows to target dataset
        
        Returns:
            ( dict[str, list[int]] ): A dictionary with 'updates' and 'insert' keys that have a list of oids updated or inserted
        """
        changes: dict[str, list[int]] = {
            'updates': [],
            'inserts': [],
            'deletes': [],
        }
        
        if ( updates := self._updates() ):
            if len(updates) == 1:
                oid = list(updates.keys())[0]
                where_clause = f"{self.target_oid_field} = {oid}"
            else:
                where_clause = f"{self.target_oid_field} IN ({','.join(map(str, updates.keys()))})"
            with self.target_editor, UpdateCursor(self.target_table, self.fields, where_clause=where_clause) as cur:
                changes['updates'] = [cur.updateRow(updates[oid]) or int(oid) for oid, *_ in cur]
        
        if ( inserts := self._inserts() ):
            with self.target_editor, InsertCursor(self.target_table, self.fields) as cur:
                changes['inserts'] = [cur.insertRow(row) for row in inserts]
        
        if ( deletes := self._deletes() ):
            if len(deletes) == 1:
                oid = deletes[0]
                where_clause = f"{self.target_oid_field} = {oid}"
            else:
                where_clause = f"{self.target_oid_field} IN ({','.join(map(str, deletes))})"
            with self.target_editor, UpdateCursor(self.target_table, self.fields, where_clause=where_clause) as cur:
                changes['deletes'] = [cur.deleteRow() or oid for oid, *_ in cur]
        
        # Clear the diff after operations are completed in case the object is re-used later
        self._table_diff = None
        return changes
    
def main():
    from pprint import pprint
    source = r'source_table'
    target = r'target_table'
    
    table_updater = TableUpdater(source, target)
    changes = table_updater.apply_changes()
    print(f"Updated {len(changes['updates'])} rows")
    print(f"Inserted {len(changes['inserts'])} rows")
    print(f"Deleted {len(changes['deletes'])} rows")
    pprint(changes)
    
if __name__ == '__main__':
    main()