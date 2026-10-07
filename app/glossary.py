"""Vietnamese -> English term expansion for keyword (BM25) search.

The knowledge base is in English. A multilingual embedding model covers meaning across languages,
but BM25 only matches exact words, so Vietnamese queries get the English terms appended here.
Matching runs on accent-stripped lowercase text, so "chong nang" and "chống nắng" both match.

Terms that matter for compliance (waterproof, acne treatment, whitening, ...) are listed explicitly:
these must never depend on a model getting the translation right.
"""
import re
import unicodedata

GLOSSARY = {
    # products & categories
    "kem chống nắng": "sunscreen SPF",
    "chống nắng": "sunscreen SPF sun protection",
    "kem dưỡng": "moisturizer cream",
    "kem mắt": "eye cream",
    "sữa rửa mặt": "cleanser face wash",
    "sáp tẩy trang": "cleansing balm makeup remover",
    "tẩy trang": "makeup remover cleansing balm",
    "nước hoa hồng": "toner",
    "mặt nạ giấy": "sheet mask",
    "mặt nạ": "mask",
    "xịt khoáng": "mist",
    "son dưỡng": "lip balm",
    "bộ quà": "kit set gift",
    "dâu": "strawberry",
    "dưa hấu": "watermelon",
    "mận": "plum",
    "bơ": "avocado",
    "ổi": "guava",
    "việt quất": "blueberry",
    "đu đủ": "papaya",
    "thành phần": "ingredients",
    "giá": "price cost",
    "hoạt chất": "active ingredient",
    # claims & compliance
    "chống nước": "waterproof water resistant",
    "chống mồ hôi": "sweatproof sweat",
    "trị mụn": "treats acne acne treatment",
    "điều trị": "treat treatment cure",
    "chữa": "cure treat heal",
    "làm trắng": "whitening lightening",
    "trắng da": "whitening lightening",
    "mờ thâm": "dark spots",
    "nám": "melasma dark spots hyperpigmentation",
    "chứng minh lâm sàng": "clinically proven clinical",
    "lâm sàng": "clinical clinically",
    "bác sĩ da liễu": "dermatologist",
    "không hóa chất": "chemical-free",
    "không độc hại": "non-toxic",
    "tự nhiên": "natural clean",
    "thuần chay": "vegan",
    "không thử nghiệm trên động vật": "cruelty-free",
    "cảnh báo": "warning alert",
    "ánh nắng": "sun sunburn sensitivity",
    "cháy nắng": "sunburn",
    "mỹ phẩm": "cosmetic",
    "thuốc": "drug",
    "quảng cáo": "ad advertising copy claim",
    "tuyên bố": "claim",
    "vi phạm": "violation violated blocked",
    "gỡ": "pulled paused",
    "kol": "influencer creator",
    "người có ảnh hưởng": "influencer creator",
    "tặng": "gifted free product",
    "miễn phí": "free",
    "công bố": "disclose disclosure",
    "ghi rõ": "disclose disclosure",
    "hợp tác": "material connection paid partnership",
    "đánh giá tiêu cực": "negative reviews",
    "xóa": "delete suppress remove",
    "ẩn": "hide suppress",
    # reactions & complaints
    "kích ứng": "irritation reaction",
    "bỏng rát": "burning burned",
    "bỏng": "burn burned",
    "rát": "stinging burning",
    "mẩn đỏ": "rash redness",
    "nổi mụn": "breakouts acne pimples",
    "mụn": "acne breakouts",
    "vón": "pilling pills",
    "vệt trắng": "white cast",
    "nhờn": "greasy sticky",
    "dính": "sticky tacky",
    "mùi": "scent smell fragrance",
    "mùi hương": "scent smell fragrance",
    "da dầu": "oily skin",
    "da khô": "dry skin",
    "da hỗn hợp": "combination skin",
    "da nhạy cảm": "sensitive skin",
    "phản ứng phụ": "adverse event reaction",
    "nghiêm trọng": "serious",
    # customers, research, ops
    "khách hàng": "customers",
    "phàn nàn": "complain complaint",
    "chê": "complain negative",
    "khen": "praise positive",
    "đánh giá": "reviews rating",
    "thấp nhất": "lowest",
    "cao nhất": "highest best",
    "trả hàng": "return returns refund",
    "hoàn tiền": "refund",
    "đổi trả": "return exchange",
    "vận chuyển": "shipping",
    "giao hàng": "shipping delivery",
    "đơn hàng": "order",
    "cskh": "customer care",
    "chăm sóc khách hàng": "customer care",
    "quy trình": "process steps SOP",
    "duyệt": "approve approval review",
    "báo cáo": "report",
    "giọng văn": "voice tone",
    "thương hiệu": "brand",
    "hiệu quả nhất": "winner best performing",
    "mẫu quảng cáo": "ad creative",
    "thử nghiệm": "test",
}


def strip_accents(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# Longest terms first so "kem chống nắng" wins over "chống nắng". Two pattern sets: accented, for text typed
# with accents ("năm" must not match "nám"), and accent-stripped, for text typed without them.
_ORDER = sorted(GLOSSARY.items(), key=lambda kv: -len(kv[0]))
_PATTERNS_ACCENTED = [(re.compile(rf"(?<!\w){re.escape(vi.lower())}(?!\w)"), en) for vi, en in _ORDER]
_PATTERNS_PLAIN = [(re.compile(rf"(?<!\w){re.escape(strip_accents(vi).lower())}(?!\w)"), en) for vi, en in _ORDER]
_VI_LETTERS = re.compile(r"[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]")


def is_vietnamese(text):
    """Vietnamese-specific letters, or a glossary hit on accent-stripped text."""
    return bool(_VI_LETTERS.search(text.lower())) or bool(expand(text))


def expand(text):
    """English terms for the Vietnamese phrases found in text ('' if none).
    Matched phrases are blanked out so shorter sub-phrases don't match again."""
    accented = bool(_VI_LETTERS.search(text.lower()))
    norm = unicodedata.normalize("NFC", text).lower()
    plain = strip_accents(text).lower()
    terms = []
    for (acc_pat, en), (plain_pat, _), (vi, _) in zip(_PATTERNS_ACCENTED, _PATTERNS_PLAIN, _ORDER):
        if accented:
            # Accented text: match the accented term. Fall back to accent-free matching only for long terms,
            # which survive tone-mark variants ("hóa"/"hoá") and partial typing; short ones collide ("nám"/"năm").
            hit = acc_pat.search(norm) or (len(strip_accents(vi)) >= 6 and plain_pat.search(plain))
        else:
            hit = plain_pat.search(plain)
        if hit:
            terms.append(en)
            norm, plain = acc_pat.sub(" ", norm), plain_pat.sub(" ", plain)
    return " ".join(dict.fromkeys(" ".join(terms).split()))
