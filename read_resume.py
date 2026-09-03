import subprocess, json, os

# 先尝试用 PyPDF2 或 pdfplumber 读取 PDF
pdf_path = r"C:\Users\11\Documents\xwechat_files\wxid_b6954cvs393s12_311b\business\favorite\temp\毛泽昂简历.pdf"

try:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                print(f"=== 第 {i+1} 页 ===")
                print(text)
                print()
except Exception as e:
    print(f"pdfplumber 失败: {e}")
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    print(f"=== 第 {i+1} 页 ===")
                    print(text)
                    print()
    except Exception as e2:
        print(f"PyPDF2 也失败: {e2}")
