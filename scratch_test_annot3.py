import fitz

# Open the actual template
doc = fitz.open("static/forms/APPLICATION-FORM-THA.pdf")
page = doc[0]

import io
from PIL import Image
img = Image.new('RGB', (100, 100), color = 'blue')
img_byte_arr = io.BytesIO()
img.save(img_byte_arr, format='PNG')
img_bytes = img_byte_arr.getvalue()

# Create a temporary page to insert the image XObject
tmp_page = doc.new_page()
# insert image to tmp page
tmp_page.insert_image(fitz.Rect(0,0,10,10), stream=img_bytes)

# Find the XObject xref inserted
images = tmp_page.get_images()
img_xref = images[0][0]

# Now back to real page, create a Stamp annot
rect = fitz.Rect(300, 100, 400, 200)
annot = page.add_stamp_annot(rect, stamp=0)

# The Appearance stream usually needs a Form XObject, but PyMuPDF's insert_image creates an Image XObject.
# A Form XObject is a stream that contains drawing commands. An Image XObject is just pixels.
# An annotation's AP dictionary /N must point to a Form XObject in standard PDF!
# If we point it to an Image XObject, it might not render. Let's see if it renders.
doc.xref_set_key(annot.xref, "AP", f"<< /N {img_xref} 0 R >>")

# Set flags: NO_PRINT
# PRINT is bit 3 (value 4). HIDDEN is bit 2 (value 2).
# We want it visible on screen, so HIDDEN is off. We want it NOT to print, so PRINT is off.
# Flags = 0 means visible, not printed.
annot.set_flags(0)
doc.xref_set_key(annot.xref, "F", "0")

# Delete tmp page
doc.delete_page(doc.page_count - 1)

doc.save("test_annot3.pdf")
print("Saved test_annot3.pdf")
