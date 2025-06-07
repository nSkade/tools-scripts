import fitz  # PyMuPDF
from PIL import Image
import io
import sys
import os
import shutil

def get_image_sizes(doc):
    total_img_bytes = 0
    img_info = []
    for page_number in range(len(doc)):
        page = doc[page_number]
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_ext = base_image["ext"]
            img_size = len(img_bytes)
            total_img_bytes += img_size
            img_info.append((page_number, xref, img_ext, img_size))
    return total_img_bytes, img_info

def remove_images_from_pdf(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    processed_xrefs = set()
    for page_number in range(len(doc)):
        page = doc[page_number]
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)
            try:
                page.delete_image(xref)
            except Exception as e:
                print(f"Warning: Could not delete xref {xref} on page {page_number+1}: {e}")
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()


def compress_pdf_images(input_pdf, output_pdf, scale_factor=1.0, jpeg_quality=100):
    doc = fitz.open(input_pdf)
    processed_xrefs = set()
    input_dir = os.path.dirname(os.path.abspath(input_pdf))
    for page_number in range(len(doc)):
        page = doc[page_number]
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_pil = Image.open(io.BytesIO(img_bytes))
            scale = min(scale_factor, 1.0)
            new_size = (max(1, int(img_pil.width * scale)), max(1, int(img_pil.height * scale)))
            img_resized = img_pil.resize(new_size, Image.LANCZOS)
            # Always save as JPEG for maximum compression
            temp_filename = os.path.join(input_dir, f"__tmp_img_{os.getpid()}_{xref}.jpg")
            img_resized = img_resized.convert("RGB")
            img_resized.save(temp_filename, format="JPEG", quality=jpeg_quality)
            new_size_bytes = os.path.getsize(temp_filename)
            orig_size = len(img_bytes)
            # Only replace if new image is smaller
            if new_size_bytes < orig_size:
                page.replace_image(xref, filename=temp_filename)
            else:
                print(f"Warning: Recompressed image (xref {xref}) is larger ({new_size_bytes/1024:.1f} KB) than original ({orig_size/1024:.1f} KB). Keeping original.")
            os.remove(temp_filename)
    # Save with garbage collection and deflate
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()

def main(input_pdf, output_pdf, scale_factor=1.0, jpeg_quality=100):
    print(f"Analyzing PDF: {input_pdf}")
    orig_pdf_size = os.path.getsize(input_pdf)
    print(f"Original PDF size: {orig_pdf_size/1024/1024:.2f} MB")

    # 1. Calculate total image size in PDF
    doc = fitz.open(input_pdf)
    total_img_bytes, img_info = get_image_sizes(doc)
    print(f"Total images in PDF: {len(img_info)}")
    print(f"Total image data size: {total_img_bytes/1024/1024:.2f} MB ({100*total_img_bytes/orig_pdf_size:.2f}% of PDF)")
    doc.close()

    # 2. Calculate PDF size without images
    temp_noimg_pdf = os.path.join(os.path.dirname(output_pdf), f"__tmp_noimg_{os.getpid()}.pdf")
    remove_images_from_pdf(input_pdf, temp_noimg_pdf)
    noimg_pdf_size = os.path.getsize(temp_noimg_pdf)
    print(f"PDF size without images: {noimg_pdf_size/1024/1024:.2f} MB ({100*noimg_pdf_size/orig_pdf_size:.2f}% of PDF)")

    # 3. Print per-image info (before compression)
    #print("Image breakdown (before compression):")
    #for page_number, xref, img_ext, img_size in img_info:
    #    print(f" - Page {page_number+1}, xref {xref}, {img_ext.upper()}, {img_size/1024:.1f} KB")

    print(f"Using scale factor: {scale_factor}")
    print(f"Using JPEG quality: {jpeg_quality}")

    # 4. Compress images and save new PDF
    compress_pdf_images(input_pdf, output_pdf, scale_factor=scale_factor, jpeg_quality=jpeg_quality)
    final_pdf_size = os.path.getsize(output_pdf)
    print(f"Final PDF size: {final_pdf_size/1024/1024:.2f} MB")

    # Cleanup
    os.remove(temp_noimg_pdf)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pdf-compress.py input.pdf output.pdf [scale_factor]")
        sys.exit(1)
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    scale_factor = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    jpeg_quality = int(100*scale_factor)
    main(input_pdf, output_pdf, scale_factor, jpeg_quality)
