import fitz

doc = fitz.open()
page = doc.new_page()

# Layer 1
xref1 = doc.add_ocg("ScreenOnlyLayer", on=True)
page.insert_text((100, 100), "This text should NOT print (Screen only)", oc=xref1)

# Modify the Usage dictionary of the OCG to force PrintState OFF
doc.xref_set_key(xref1, "Usage", "<< /Print << /PrintState /OFF >> >>")

doc.save("test_ocg_fixed.pdf")
print("Saved test_ocg_fixed.pdf")
