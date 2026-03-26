# Include the shared yoyo framework class.
#
# We do not pass parameters here.
# Instead, Puppet will automatically look up class parameters
# from Hiera using keys like:
#   yoyo::instance_name
#   yoyo::local_imports
include yoyo