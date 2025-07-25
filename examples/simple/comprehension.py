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



# The above code can be done with a comprehension!

def dict_vals(d: dict) -> list:
    """This function just makes the value conversion less cluttered"""
    return list(d.values())

with UpdateCursor(table2, ['OID@'] + table2_fields) as cur: # 1
    updated_records: list[int] = [                          # 2
        cur.updateRow(                                      # 3
            dict_vals(dict_comp_record[row['OID@']])        # 4
        ) or row['OID@']                                    # 5
        for row in as_dict(cur)                             # 6
        if row['OID'] in dict_comp_record                   # 7
    ]

# This is a monster of a comprehension. Lets break it down:
# 1) A cursor is initialized using its __enter__/context manager method
# 2) We declare a variable that will be of type list[int]
#    that will be used to collect OIDs of updated rows
# NOTE: 3-7 are in reversed order because comprehensions are read from bottom to top
# This is beause the meat of the comprehension is meant to be read first (the return values)
# and the filtering is read after so you immediately know what a comprehension creates then see
# how it creates it
# 7) Make sure that the current row has a matching record in the update mapping
# 6) Iterate the rows with the fields mapped to values
# 5) Because `updateRow` returns `None`, we can use an `or` statment to fallthrough to another value
#    In this case the fallthrough is row['OID@'] becasue we want to collect updated row IDs
# 4) We pull the row value of the matching update record
# 3) We update the row with that record

# Honestly, this is not a very good way to write this code, just because it's possible doesn't mean you 
# should do it. Here's a more readable version:

updated_records: list[int] = []
with UpdateCursor(table2, ['OID@'] + table2_fields) as cur:
    for row in as_dict(cur):
        oid = row['OID@']
        if oid not in dict_comp_record:
            continue
        cur.updateRow(dict_vals(dict_comp_record[oid]))
        updated_records.append(oid)

# As you can see, the comprehension is not that much shorter than the regular method and only
# saves on one assignment (oid), which should be there for readability's sake

# Now that we understand that cursors are lazy generators, we can do some fun things
# Record Count
record_count: int = sum(1 for _ in SearchCursor(table, ['OID@']))

# This pattern consumes a cursor by iterating all rows and adding 1 for each row.
# The nice thing about this is that at no point do we ever have more than one record
# in memory, in this case a (singleton tuple containing the ObjectID)
# I tend to prefer this to arcpy.GetCount() since the return type of that function is 
# a pain to deal with (Result[str, ...]).

# This pattern can be expanded upon by passing the Cursor a where_clause of a spatial_filter:
record_count_where: int = sum(1 for _ in SearchCursor(table, ['OID@'], where_clause='fieldname = <condition>'))

# Because the query doesn't need the field name to be included in the output, you can keep the minimal ['OID@']
# field list and define whatever field you want in the clause. That field does not need to be included in the output
# if you don't need it (in this case we need nothing since we're just counting)

# Python sets are a fantastic way to get unique values in a sequence. They have O(1) lookup time best case and O(n) worst case
# Lets say we have a table with a field that we want unique values from:

unique_values: set[str] = {row['fieldname'] for row in as_dict(SearchCursor(table, ['fieldname']))}

# A table like this:
# | OID | FIELDNAME|
# |  1  |   'A'    |
# |  2  |   'A'    |
# |  3  |   'C'    |
# |  4  |   'C'    |

# Would return: {'A, 'B', 'C'}