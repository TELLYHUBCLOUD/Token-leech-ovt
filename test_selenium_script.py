# In bypass command, the user expects to either get links returned or buttons.
# If I return a string with all the options, or a list of dicts: `[{'url': link}]`.
# Wait, `direct_link_generator` can return a dictionary: `{'contents': [{'url': '...'}]}`.
# Or if it returns a string with newlines.
