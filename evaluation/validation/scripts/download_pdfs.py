#!/usr/bin/env python3
"""
Download all arXiv PDFs from repo_list.csv.
Run on the LOGIN NODE (has internet) before submitting GPU jobs.
Usage: python download_pdfs.py --csv repo_list.csv --output-dir pdfs
"""
import csv, os, sys, urllib.request, time

def main():
    csv_path = sys.argv[sys.argv.index("--csv")+1] if "--csv" in sys.argv else "repo_list.csv"
    out_dir = sys.argv[sys.argv.index("--output-dir")+1] if "--output-dir" in sys.argv else "pdfs"
    os.makedirs(out_dir, exist_ok=True)

    with open(csv_path, newline='') as f:
        rows = list(csv.DictReader(f))

    done, fail = 0, 0
    for i, row in enumerate(rows):
        sid = row.get('study_id', '').strip()
        url = row.get('paper_url_pdf', '').strip()
        if not sid or not url: continue
        path = os.path.join(out_dir, f"{sid}.pdf")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            done += 1; continue
        print(f"  [{i+1}/{len(rows)}] {sid}...", end=" ")
        try:
            urllib.request.urlretrieve(url, path)
            print(f"✓ ({os.path.getsize(path)//1024}KB)")
            done += 1
        except Exception as e:
            print(f"✗ {e}")
            fail += 1
        time.sleep(0.5)  # be nice to arXiv

    print(f"\nDone: {done} downloaded, {fail} failed")

if __name__ == "__main__": main()
