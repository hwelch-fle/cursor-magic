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

# Lets inspect the Cursor code:
#class SearchCursor(Iterator[tuple[Any, ...]]):
#    """Create a read-only cursor on a feature class or table."""
#
#    def __init__(
#        self,
#        in_table: Any,
#        field_names: str | Sequence[str],
#        where_clause: str | None = None,
#        spatial_reference: str | int | SpatialReference | None = None,
#        explode_to_points: bool | None = False,
#        sql_clause: list[str | None] | tuple[str | None, str | None] = (None, None),
#        datum_transformation: str | None = None,
#        spatial_filter: Any = None,
#        spatial_relationship: SpatialRelationship | None = None,
#        search_order: SearchOrder | None = None,
#    ) -> None: ...
#    def __enter__(self) -> Self: ...
#    def __exit__(
#        self,
#        exc_type: type[BaseException],
#        exc_val: BaseException,
#        exc_tb: TracebackType | None,
#    ) -> bool: ...
#    def __next__(self) -> tuple[Any, ...]: ...
#    def __iter__(self) -> Iterator[tuple[Any, ...]]: ...
#    def next(self) -> tuple[Any, ...]: ...
#    def reset(self) -> None:
#        """Reset cursor position"""
#        ...
#    @property
#    def fields(self) -> tuple[str, ...]:
#        """Returns fields name"""
#        ...
#    @property
#    def _dtype(self) -> numpy.dtype[Any]:
#        """Returns fields numpy dtype"""
#        ...
#    def _as_narray(self) -> numpy.record:
#        """Returns snapshot of the current state as NumPy array."""

# You can see that it implements both the Iterator and the ContextManager protocol:

# class Iterator(Protocol):
#     def __iter__(self): ...
#     def __next__(self): ...

# class ContextManager(Protocol):
#     def __enter__(self): ...
#     def __exit__(self, exc_type, exc_val, exc_tb): ...