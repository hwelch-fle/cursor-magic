from arcpy.da import SearchCursor

# Python is a garbage collected language. This means that objects with out any reference will be immediately deleted
# by the garbage collector. If an object has an __exit__ method, that will be called during deletion.

def foo():
    """Elevate a local object to a global state"""
    local_object = object()        
    global GLOBAL_OBJECT
    GLOBAL_OBJECT = local_object
    return id(local_object)

local_id = foo()
print(f'{( local_id == id(GLOBAL_OBJECT) ) = }')

del GLOBAL_OBJECT
print(f"After del GLOBAL_OBJECT : {'GLOBAL_OBJECT' in globals() = }")

# In this contrived example, we elevate a local object to a global state, then check that the id of the object 
# created localy is the same as the id of the global object after the funtion returns

# If you run this code, you can see that indeed it is the same object that's created locally that's now available on
# the global scope!

# If we never elevated that local object to the global scope, it would have been removed as soon as the function exited:

print('-'*50)
print('Scopes: \n')
print('script started')
class Foo:
    """Minimal implementation of Context Manager protocol (__enter__, __exit__)
    
    NOTE: __del__ defined because deletion of the object is done after __exit__ is called
    The default object.__del__ is fine, this just allows me to print when the method is called
    """
    def __init__(self, name: str, level: int=0):
        self.name = name
        self.level = level
        print('\t'*self.level, f'Initialized {self.name}...')
    def __enter__(self):
        print('\t'*self.level, f'Entering {self.name}...')
    def __exit__(self, *args):
        print('\t'*self.level, f'Exiting {self.name}...')
    def __del__(self):
        print('\t'*self.level, f'Deleting {self.name}...')

F = Foo('Global Foo', 0)
def baz():
    f = Foo('baz Foo', 1)
    with f:
        pass
with F:
    baz()

# OUTPUT:   
# script started
# Initialized Global Foo...
# Entering Global Foo...
#         Initialized baz Foo...
#         Entering baz Foo...
#         Exiting baz Foo...
#         Deleting baz Foo...
# Exiting Global Foo...
# Deleting Global Foo... 

# As you can see here, using the with block allows us to run code as an object transitions between scopes

# Lets inspect the SearchCursor code (simplified):
# class SearchCursor(Iterator[tuple[Any, ...]]):#
#     def __init__(self, ...) -> None: ...
#     def __enter__(self) -> Self: ...
#     def __exit__(self, ...) -> bool: ...
#     def __next__(self) -> tuple[Any, ...]: ...
#     def __iter__(self) -> Iterator[tuple[Any, ...]]: ...

# You can see that it implements both the Iterator and the ContextManager protocols:

# class Iterator(Protocol):
#     def __iter__(self): ...
#     def __next__(self): ...

# class ContextManager(Protocol):
#     def __enter__(self): ...
#     def __exit__(self, exc_type, exc_val, exc_tb): ...

# Lets re-do that Foo example above with a cursor:
print('-'*50)
print('Cursor Lifetime: \n')
print('script started')

table = "<Table Path>"

class LoudSearchCursor(SearchCursor):
    """Wrap a SearchCursor to print when dunders are called"""
    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop('name', None)
        self.level = kwargs.pop('level', 0)
        super().__init__(*args, **kwargs)
        print('\t'*self.level, f'Initialized Cursor {self.name}')
    def __enter__(self):
        print('\t'*self.level, f'Entering Cursor {self.name}')
        super().__enter__()
    def __exit__(self, *args):
        print('\t'*self.level, f'Exiting Cursor {self.name}')
        super().__exit__(*args)
    def __del__(self):
        print('\t'*self.level, f'Deleting Cursor {self.name}')

GLOBAL_CURSOR = LoudSearchCursor(table, ['OID@'], name='Global Cursor')

with GLOBAL_CURSOR as cur:
    pass

def buzz():
    print('buzz Called')
    local_cursor = LoudSearchCursor(table, ['OID@'], name='buzz Cursor', level=1)
    print('buzz Completed')
buzz()

# OUTPUT:
# script started
#  Initialized Cursor Global Cursor
#  Entering Cursor Global Cursor
#  Exiting Cursor Global Cursor
# buzz Called
#          Initialized Cursor buzz Cursor
# buzz Completed
#          Deleting Cursor buzz Cursor
#  Deleting Global Foo...
#  Deleting Cursor Global Cursor

# Look at that! Global Foo is still in scope until the very end of the script!
# You can also see that the local_cursor is deleted as soon as the function it lives in exits

# Of note here is that you don't have to call del on local cursors if you put them in a function and
# the function returns after you finish using the cursor

# Now lets try this in a comprehension:

print('Getting Vals')
vals = [row[0] for row in LoudSearchCursor(table, ['OID@'], name='Comprehension Cursor', level=1)]
print('Got Vals')

# OUTPUT:
# Getting Vals
#      Initialized Cursor Comprehension Cursor
#      Deleting Cursor Comprehension Cursor
# Got Vals
# Deleting Global Foo...
# Deleting Cursor Global Cursor

# Look at that! Even though we never deleted the cursor, it was deleted as soon as the comprehension completed!