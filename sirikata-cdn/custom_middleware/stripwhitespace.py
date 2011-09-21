"""
Tightens up response content by removed superflous line breaks and whitespace.
By Doug Van Horn

---- CHANGES ----
v1.1 - 31st May 2011
Cal Leeming [Simplicity Media Ltd]
Modified regex to strip leading/trailing white space from every line, not just those with blank \n.

---- TODO ----
* Ensure whitespace isn't stripped from within <pre> or <code> or <textarea> tags.

"""

import re

class StripWhitespaceMiddleware:
    """
    Strips leading and trailing whitespace from response content.
    """

    def __init__(self):
        self.whitespace = re.compile('^\s+', re.MULTILINE)
        self.whitespace_trail = re.compile('\s+$', re.MULTILINE)


    def process_response(self, request, response):
        if "text" in response['Content-Type']:
            new_content = self.whitespace.sub('', response.content)
            new_content = self.whitespace_trail.sub('\n', new_content)
            response.content = new_content
            return response
        else:
            return response
