import fitz

doc = fitz.open()
page = doc.new_page()

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

# Set the appearance stream to the Image XObject
# To make it display correctly, we usually need a Form XObject, not just an Image XObject.
# Let's try Form XObject. How to create a Form XObject?
# Oh wait, we can just use the Image XObject? Let's try.
doc.xref_set_key(annot.xref, "AP", f"<< /N {img_xref} 0 R >>")

# Set flags: NO_PRINT
# PRINT is bit 3 (value 4).
annot.set_flags(fitz.ANNOT_FLAG_HIDDEN) # let's just clear flags manually
doc.xref_set_key(annot.xref, "F", "0") # clear all flags -> visible on screen, not printed

# Delete tmp page
doc.delete_page(1)

doc.save("test_annot.pdf")
print("Saved test_annot.pdf")
