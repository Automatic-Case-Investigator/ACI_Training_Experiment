import asyncio
import json
import re
from tqdm import tqdm
from langchain_openai import ChatOpenAI

CASE_FILE = "output/cases.json"
OUTPUT_FILE = "output/task_generation_responses.json"

MODEL_A = {"name": "openai/gpt-oss-20b", "url": "http://dgx:9000/v1"}
MODEL_B = {"name": "acezxn/ACI_Cyber_Base_GPT_OSS_20B", "url": "http://dgx:9001/v1"}

max_workers = 30

investigation_prompt = """
You are a SOC analyst working in a SOAR platform.

You receive a security case containing:
- A title (brief summary of the alert)
- A description (detailed information)

Your task:
Generate a list of investigation tasks.

Output format:
Task #<number>
Title: <one concise sentence>
Description: <a few sentences explaining the investigation step>
"""

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
    return ChatOpenAI(
        model=model["name"],
        base_url=model["url"],
        api_key="",
        reasoning_effort="high"
    )

async def generate_tasks(llm, case, semaphore):
    async with semaphore:
        messages = [
            ("system", investigation_prompt),
            ("human", f"Case title: {case['case_title']}"),
            ("human", f"Case description: {case['case_description']}"),
        ]
        response = await llm.ainvoke(messages)
        return response.text.strip()

async def run_model_generation(llm, cases):
    semaphore = asyncio.Semaphore(max_workers)
    outputs = [None] * len(cases)

    async def worker(i, case):
        async with semaphore:
            messages = [
                ("system", investigation_prompt),
                ("human", f"Case title: {case['case_title']}"),
                ("human", f"Case description: {case['case_description']}"),
            ]
            response = await llm.ainvoke(messages)
            outputs[i] = response.text.strip()

    tasks = [worker(i, case) for i, case in enumerate(cases)]

    for f in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
        await f
    return outputs


async def run():
    with open(CASE_FILE) as f:
        cases = json.load(f)

    llm_a = build_llm(MODEL_A)
    llm_b = build_llm(MODEL_B)

    print("\nRunning Model A generation...")
    tasks_a = await run_model_generation(llm_a, cases)

    print("\nRunning Model B generation...")
    tasks_b = await run_model_generation(llm_b, cases)

    results = []
    for i, case in enumerate(cases):
        entry = {
            "case_title": case["case_title"],
            "case_description": case["case_description"],
            "model_a_tasks": tasks_a[i],
            "model_b_tasks": tasks_b[i],
        }
        results.append(entry)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(run())