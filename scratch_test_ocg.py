import fitz

doc = fitz.open()
page = doc.new_page()

# Layer 1: usage Print
xref1 = doc.add_ocg("LayerPrint", on=True, intent="View", usage="Print")
page.insert_text((100, 100), "This is usage=Print", oc=xref1)

# Layer 2: usage View
xref2 = doc.add_ocg("LayerView", on=True, intent="View", usage="View")
page.insert_text((100, 150), "This is usage=View", oc=xref2)

doc.save("test_ocg.pdf")
print("Saved test_ocg.pdf")
