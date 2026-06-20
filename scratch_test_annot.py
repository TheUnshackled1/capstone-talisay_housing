import fitz

doc = fitz.open()
page = doc.new_page()

# create a dummy image
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
print("Images on tmp:", images)
img_xref = images[0][0]

# Now back to real page, create a Widget
rect = fitz.Rect(300, 100, 400, 200)
widget = fitz.Widget()
widget.rect = rect
widget.field_type = fitz.PDF_WIDGET_TYPE_BUTTON
widget.field_name = 'photo_2x2'
widget.field_flags = fitz.PDF_BTN_FIELD_IS_PUSHBUTTON
widget.field_value = 'Off'
annot = page.add_widget(widget)

# Now we need to set the appearance. A button's appearance is usually a Form XObject, not an Image XObject.
# Can we set the normal appearance /N directly to the Image XObject?
doc.xref_set_key(annot.xref, "AP", f"<< /N {img_xref} 0 R >>")
doc.xref_set_key(annot.xref, "F", "4") # PRINT flag is bit 3 (value 4). If we want screen-only, we turn OFF bit 3, turn ON bit 1 (Invisible) ? No, we want visible. So flags = 0 ?
doc.xref_set_key(annot.xref, "F", "0")

# Delete tmp page
doc.delete_page(1)

doc.save("test_annot.pdf")
print("Saved test_annot.pdf")
