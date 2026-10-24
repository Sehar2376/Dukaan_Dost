"""Day 3 check: run the classifier on real-style messages and see how accurate it is.

    python test_classify.py

Needs NEBIUS_API_KEY in backend/.env. Add more messages (aim for 30+) - especially the
spellings your friends and family actually use on WhatsApp.
"""
import time

import ai

# (message, expected_language, expected_intent)
CASES = [
    ("Assalam o alaikum", "roman_urdu", "greeting"),
    ("Delivery charges kitne hain?", "roman_urdu", "faq"),
    ("2kg chocolate cake kal shaam chahiye", "roman_urdu", "order"),
    ("Thora kam kar dein na bhai", "roman_urdu", "bargain"),
    ("Mera order 2 ghantay late hai, ye kya tareeqa hai!!", "roman_urdu", "complaint"),
    ("Do you deliver to DHA?", "english", "faq"),
    ("I want to order 2 boxes of brownies", "english", "order"),
    ("What's your last price for the red velvet?", "english", "bargain"),
    ("کیک کی قیمت کیا ہے؟", "urdu", "faq"),
    ("مجھے کل ایک کیک چاہیے", "urdu", "order"),
    ("I need 3 boxes of cookies, kal tak mil jayenge?", "mixed", "order"),
    ("Kya aap Friday ko open hote hain?", "roman_urdu", "faq"),
    ("Cake bilkul kharab tha, paise wapis karein", "roman_urdu", "complaint"),
    ("Saturday 5 baje ka slot book kar dein", "roman_urdu", "booking"),
    ("eggless cake bnate ho?", "roman_urdu", "faq"),
]

if __name__ == "__main__":
    print(f"Model: {ai.NANO}   mock={ai.MOCK}\n")
    ok_lang = ok_intent = 0
    for msg, lang, intent in CASES:
        t = time.time()
        r = ai.classify(msg)
        ms = (time.time() - t) * 1000
        l_ok, i_ok = r["language"] == lang, r["intent"] == intent
        ok_lang += l_ok
        ok_intent += i_ok
        mark = "OK " if (l_ok and i_ok) else "XX "
        print(f"{mark}{ms:6.0f}ms  {msg[:45]:45}  -> {r['language']:10} {r['intent']:9} urgent={r['urgent']}"
              + ("" if l_ok and i_ok else f"   (expected {lang}/{intent})"))
    n = len(CASES)
    print(f"\nLanguage: {ok_lang}/{n}   Intent: {ok_intent}/{n}")
