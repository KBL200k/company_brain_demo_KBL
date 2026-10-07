"""Download the raw Sephora dataset (~520 MB) into data/raw/.

Original: https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews
Mirror used here (no Kaggle token needed): https://huggingface.co/datasets/eyachawechi/my-sephora-data
"""
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/eyachawechi/my-sephora-data/resolve/main/"
FILES = [
    "product_info.csv",
    "reviews_0-250.csv",
    "reviews_250-500.csv",
    "reviews_500-750.csv",
    "reviews_750-1250.csv",
    "reviews_1250-end.csv",
]
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = RAW / name
        if dest.exists():
            print(f"skip {name} (exists)")
            continue
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(BASE + name, dest)
    print("done")


if __name__ == "__main__":
    main()
