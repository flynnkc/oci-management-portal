#!/usr/bin/python3.11

# ResourceType plugins live in this package. Each module should define one
# ResourceType subclass for one OCI resource type. BaseAction imports every
# non-private module in this package, so adding actions/types/myresource.py is
# enough to register support for Deleter/Extender.
