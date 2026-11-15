from rag import Retriever

# question -> sections that count as a correct find
CASES = [
    ("What does MTBF stand for?", ["MTBF, MTTF and MTTR"]),
    ("Inherent availability = MTBF / (MTBF + X). What is X?", ["Availability"]),
    ("Which distribution is commonly used in reliability for life data?", ["Weibull distribution"]),
    ("If the failure rate is constant, which distribution describes time to failure?", ["Exponential distribution"]),
    ("A Weibull shape parameter greater than 1 indicates what type of failures?", ["Weibull distribution"]),
    ("Name the two later phases of the bathtub curve.", ["Bathtub curve"]),
    ("What does HALT stand for in reliability testing?", ["HALT and HASS"]),
    ("Which accelerating stress does the Arrhenius model describe?", ["Arrhenius model"]),
    ("What does FMEA stand for?", ["FMEA"]),
    # reworded questions: no exact words from the knowledge file
    ("How do we check that a gauge gives consistent readings?", ["Measurement System Analysis"]),
    ("Why do old machines start failing more often?", ["Bathtub curve", "Weibull distribution"]),
    ("How often should a thermometer be checked against a reference?", ["Calibration"]),
]

r = Retriever()
print(f"Knowledge base: {len(r.chunks)} chunks\n")
for c in r.chunks:
    print(f"   - {c['title']}")
if len(r.chunks) < 2:
    raise SystemExit("\nERROR: knowledge base has fewer than 2 sections. Check the '## ' headings in docs/knowledge.md")
print()
hit1 = hit2 = 0
for q, expected in CASES:
    found = r.search(q, k=2)
    titles = [f["title"] for f in found]
    ok1 = titles[0] in expected
    ok2 = any(t in expected for t in titles)
    hit1 += ok1
    hit2 += ok2
    mark = "PASS" if ok1 else ("NEAR" if ok2 else "FAIL")
    print(f"{mark} | {q}")
    second = f"2) {titles[1]} ({found[1]['score']})" if len(found) > 1 else "2) -"
    print(f"       1) {titles[0]} ({found[0]['score']})   {second}")
    if not ok1:
        print(f"       expected: {', '.join(expected)}")

n = len(CASES)
print(f"\nHit@1: {hit1}/{n} ({100 * hit1 / n:.0f}%)   Hit@2: {hit2}/{n} ({100 * hit2 / n:.0f}%)")