from pdf2image import convert_from_path

pages = convert_from_path(
    "test.pdf",
    poppler_path=r"C:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
)

print(f"Converted {len(pages)} pages")