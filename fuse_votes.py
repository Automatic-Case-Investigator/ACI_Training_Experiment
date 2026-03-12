import json
from collections import Counter

FILE_A = "output/investigation_openai.json"
FILE_B = "output/investigation_claude.json"
OUTPUT_FILE = "output/investigation_all.json"


def compute_majority(case):
    vote_counter = Counter()

    for judge, result in case["judges"].items():
        winner = result["winner"]
        if winner in ["A", "B"]:
            vote_counter[winner] += 1

    if vote_counter["A"] > vote_counter["B"]:
        return "A"
    elif vote_counter["B"] > vote_counter["A"]:
        return "B"
    else:
        return "Tie"


with open(FILE_A) as f:
    data_a = json.load(f)

with open(FILE_B) as f:
    data_b = json.load(f)


if len(data_a) != len(data_b):
    raise ValueError("Files must contain the same number of cases")


fused_cases = []

for case_a, case_b in zip(data_a, data_b):

    fused_case = dict(case_a)

    fused_judges = {}
    fused_judges.update(case_a["judges"])
    fused_judges.update(case_b["judges"])

    fused_case["judges"] = fused_judges

    fused_case["final_winner"] = compute_majority(fused_case)

    fused_cases.append(fused_case)


with open(OUTPUT_FILE, "w") as f:
    json.dump(fused_cases, f, indent=2)


print(f"Fused file written to: {OUTPUT_FILE}")