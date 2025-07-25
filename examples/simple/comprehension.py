from arcpy.da import SearchCursor, UpdateCursor

# A Cursor object can be immediately consumed by a comprehension to de-structure it

table = 'table_path'
fields = ['field1', 'field2']

# The simplest way to use a comprehension is to extract a list of rows
feature_list: list[tuple] = [row for row in SearchCursor(table, fields)]

# Filtering can be done with a predicate
feature_list_filtered: list[tuple] = [
    row 
    for row in SearchCursor(table, fields)
    if row[0] < 10 # field1 is < 10
]

# You can preprend a *token to a list of fields to grant access to a system field without knowing its name
# This is very useful for building a mapping of row Object IDs to row values
# 
# *https://pro.arcgis.com/en/pro-app/latest/arcpy/data-access/searchcursor-class.htm `Parameters > field_names`
dict_comp: dict[int, tuple] = {
    row[0]: row
    for row in SearchCursor(table, ['OID@'] + fields)
}

# You can also use a comprehension predicate to filter the results
dict_comp_filtered: dict[int, tuple] = {
    row[0]: row
    for row in SearchCursor(table, ['OID@'] + fields)
    if row[0] < 10 # OID is < 10 
}

# Cursors also have a `field` attribute that can be used to build a dictionary for each row
# to use this we can define a lazy row generator

from typing import Generator, Any

def as_dict(cursor: SearchCursor | UpdateCursor, yield_from: bool=True) -> Generator[dict[str, Any], None, None]:
    # zip will create a pairing of fieldname to fieldvalue that can be passed to a dict() constuctor
    # zip(['a', 'b'], [1,2]) -> (('a', 1), ('b', 2))
    # dict((('a', 1), ('b', 2))) -> {'a': 1, 'b': 2}
    
    # A yield statement will lazily yield values as the calling function requests them (generator)
    # At no point is the whole dataset in memory, this allows you to iterate large datasets without
    # worrying about memory
    if yield_from:
        yield from (dict(zip(cursor.fields, row)) for row in cursor)
    
    # An alternate way of writing this compact statment would be:
    else:
        for row in cursor:
            row_dict = {}
            for index, fieldname in enumerate(cursor.fields):
                row_dict.setdefault(fieldname, row[index])
            yield row_dict

# Now that we have an `as_dict` generator, we can use that in a seperate comprehension to 
# build a mapping of row records (row_dict) to object_ids        
dict_comp_record: dict[int, dict] = {
    row['OID@'] : row
    for row in as_dict(SearchCursor(table, ['OID@'] + fields))
    if row['OID@'] < 10
}

# This will give you an object like this:
# {
#     1: {'OID@': 1, 'field1': 'field1Val', 'field2': 'field2Val'},
#     ...
# }

# Which can now be used to say, update a table:

table2 = 'table2'
table2_fields = ['field1', 'field2']
with UpdateCursor(table2, ['OID@'] + table2_fields) as cur:
    for row in as_dict(cur):
        if row['OID@'] in dict_comp_record:
            row.update(dict_comp_record[row['OID@']])
            
            # `updateRow` requires a list of values, so we need to convert
            # our dictionary representation of the row to a list of mapped values
            # This works because as of Python 3.7+ dicts are ordered by default
            # and this is now a language feature and not an implementation detail 
            # like before
            cur.updateRow(list(row.values()))