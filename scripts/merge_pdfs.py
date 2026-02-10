#!/usr/bin/env python3
"""
Merge Auto_Reorder_System_Plan.pdf and Voice_AI_Phone_Ordering_Plan.pdf
into a single WONTECH_System_Plans.pdf
"""

import os

try:
    from PyPDF2 import PdfMerger
except ImportError:
    print("PyPDF2 not installed. Installing...")
    import subprocess
    subprocess.check_call(['pip3', 'install', 'PyPDF2'])
    from PyPDF2 import PdfMerger

def merge_pdfs():
    docs_dir = os.path.dirname(__file__)

    pdf1 = os.path.join(docs_dir, 'Auto_Reorder_System_Plan.pdf')
    pdf2 = os.path.join(docs_dir, 'Voice_AI_Phone_Ordering_Plan.pdf')
    output = os.path.join(docs_dir, 'WONTECH_System_Plans.pdf')

    # Verify files exist
    if not os.path.exists(pdf1):
        print(f"Error: {pdf1} not found")
        return
    if not os.path.exists(pdf2):
        print(f"Error: {pdf2} not found")
        return

    merger = PdfMerger()

    # Add PDFs
    merger.append(pdf1)
    merger.append(pdf2)

    # Write combined PDF
    merger.write(output)
    merger.close()

    print(f"Combined PDF created: {output}")


if __name__ == '__main__':
    merge_pdfs()
