import asyncio
import json
import re
import os
from collections import Counter
from xml.parsers.expat import model
from tqdm import tqdm
from langchain_openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# ---------- CONFIG ----------

RESPONSE_FILE = "output/task_generation_responses.json"
OUTPUT_FILE = "output/investigation_eval.json"

JUDGE_MODELS = [
    # {"name": "gemini-2.5-flash"},
    # {"name": "gemini-2.5-pro"},
    # {"name": "gemini-3.1-flash-lite-preview"},
    # {"name": "gemini-3-flash-preview"},
    # {"name": "o3"},
    # {"name": "gpt-4o-mini-2024-07-18"},
    # {"name": "gpt-4o"},
    # {"name": "gpt-5.1-2025-11-13"},
    {"name": "claude-opus-4-6"},
    {"name": "claude-sonnet-4-6"},
    {"name": "claude-haiku-4-5"},
    # {"name": "openai/gpt-oss-20b", "url": "http://dgx:9000/v1"}
]

max_workers = 10

judge_prompt = """
You are a senior SOC analyst evaluating investigation plans.

You will be given the following:
- Case title: title of the security case
- Case description: detailed description of the security case
- Response A: Response from SOC analyst A
- Response B: Response from SOC analyst B

Compare the two responses and determine which one demonstrates higher quality.

High-level Evaluation Criteria:
- The provided response is high quality if it demonstrates strong SOC knowledge depth
- The provided terminologies within a high quality response must be correct
- The provided tasks within a high quality response must be comprehensive with respect to the security case

Key Aspects to Consider During Evaluation:
- Alert understanding
- Alert source identification
- Detection rule interpretation
- Alert severity assessment
- Alert prioritization
- Asset identification
- Asset criticality awareness
- User/account identification
- Business context awareness
- Relevant log source identification
- Evidence completeness
- Time range scoping
- Cross-log correlation
- Artifact identification (IPs, domains, hashes, processes, users)
- Event timeline reconstruction
- Pattern recognition of attacker behavior
- Hypothesis formulation
- Hypothesis validation
- False positive consideration
- Root cause identification
- Threat technique mapping
- SIEM query usage
- EDR investigation capability
- Threat intelligence lookup usage
- Query efficiency
- Automation/playbook usage
- Alert classification accuracy
- Incident scope determination
- Impact assessment
- Confidence in conclusions
- Appropriate escalation decisions
- Containment recommendation quality
- Remediation recommendation quality
- Follow-up investigation suggestions
- Detection improvement suggestions
- Investigation documentation clarity
- Evidence recording
- Timeline documentation
- Investigation step transparency
- Conclusion clarity
- Internal team communication
- Escalation communication quality
- Stakeholder communication clarity
- Investigation handoff quality
- Investigation efficiency
- Time-to-triage
- Logical investigation workflow
- Prioritization of tasks
- Security judgment
- Analytical reasoning quality
- Attention to anomalies
- Threat awareness
- Professional investigative mindset

Output Guidelines:
- Output plaintext only. Do not add markdown syntax to your output.
- Output a single paragraph of your analysis, following with a new line with your final verdict.

Output Format (follow strictly to this format):
Reasoning: <brief explanation>
Winner: <A or B>
"""

def build_llm(model):
    if "gpt" in model["name"]:
        return ChatOpenAI(
            model=model["name"],
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif "claude" in model["name"]:
        return ChatAnthropic(
            model=model["name"],
            api_key=os.getenv("CLAUDE_API_KEY")
        )
    else:
        return GoogleGenerativeAI(model=model["name"], google_api_key=os.getenv("GEMINI_API_KEY"))
        


async def judge_case(llm, judge_name, case, tasks_a, tasks_b, semaphore):
    async with semaphore:
        messages = [
            ("system", judge_prompt),
            ("human", f"Case title: {case['case_title']}"),
            ("human", f"Case description: {case['case_description']}"),
            ("human", f"Response A: {tasks_a}"),
            ("human", f"Response B: {tasks_b}"),
        ]

        response = await llm.ainvoke(messages)

        if isinstance(response, str):
            return response.strip()

        if judge_name == "gpt-5.2-pro-2025-12-11":
            return response.content[1]["text"]
        print(response.content)
        return response.content.strip()


def parse_judgement(text):
    reasoning_match = re.search(r"Reasoning:\s*(.*)", text, re.IGNORECASE)
    winner_match = re.search(r"Winner:\s*(A|B|Tie)", text, re.IGNORECASE)

    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
    winner = winner_match.group(1).upper() if winner_match else "Unknown"

    return reasoning, winner


async def run_judging(llm, judge_name, cases, tasks_a, tasks_b):
    semaphore = asyncio.Semaphore(max_workers)

    async def judge_wrapper(i):
        text = await judge_case(llm, judge_name, cases[i], tasks_a[i], tasks_b[i], semaphore)
        reasoning, winner = parse_judgement(text)

        return {
            "judge": judge_name,
            "reasoning": reasoning,
            "winner": winner,
            "raw": text
        }

    tasks = [judge_wrapper(i) for i in range(len(cases))]

    outputs = []

    for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc=f"Judging ({judge_name})"):
        outputs.append(await future)

    return outputs



def majority_vote(votes):
    votes = [v for v in votes if v in ["A", "B", "Tie"]]
    if not votes:
        return "Unknown"

    counter = Counter(votes)
    return counter.most_common(1)[0][0]


async def run():

    with open(RESPONSE_FILE) as f:
        cases = json.load(f)

    tasks_a = [c["model_a_tasks"] for c in cases]
    tasks_b = [c["model_b_tasks"] for c in cases]

    judge_results = {}

    # Run each judge
    for judge in JUDGE_MODELS:
        name = judge["name"]
        print(f"\nRunning judge: {name}")

        llm = build_llm(judge)

        results = await run_judging(llm, name, cases, tasks_a, tasks_b)

        judge_results[name] = results

    # Merge results
    final_results = []
    for i, case in enumerate(cases):
        judges = {}
        votes = []

        for judge_name in judge_results:
            r = judge_results[judge_name][i]
            judges[judge_name] = {
                "winner": r["winner"],
                "reasoning": r["reasoning"],
                "raw_output": r["raw"]
            }

            votes.append(r["winner"])

        final_winner = majority_vote(votes)
        entry = {
            "case_title": case["case_title"],
            "case_description": case["case_description"],
            "model_a_tasks": tasks_a[i],
            "model_b_tasks": tasks_b[i],
            "judges": judges,
            "final_winner": final_winner
        }

        final_results.append(entry)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_results, f, indent=2)

    print(f"\nSaved results to {OUTPUT_FILE}")


    scoreboard = Counter()

    for r in final_results:
        scoreboard[r["final_winner"]] += 1

    print("\nFinal Majority Vote Scoreboard:")

    for k, v in scoreboard.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    asyncio.run(run())