import asyncio
import json
import re
from tqdm import tqdm
from langchain_openai import ChatOpenAI

instruction = """
You are responsible of generating dataset entries for case title and descriptions in Security Operations Center (SOC).
You will be provided a theme which you will use to generate the security case data from.

Note that your generated security case must be incomplete, meaning that additional investigation tasks is necessary. However, suggesting future investigation tasks is not your responsibility.

Output Guidelines:
- Case title should be a sentence long description of the security case
- Case description should list all the relevant artifacts and observations related to the security case
- Do not output extra explanations

Output Format:
Case title: <case title>
Case description: <case description>
"""

themes = [
    "Network scanning attempt",
    "Enumaration attempt",
    "Exploitation attempt",
    "Unexpected file modifications",
    "PrivEsc attempt"
]

max_workers = 10

def parse_output(text):
    title_match = re.search(r"Case title:\s*(.*)", text)
    desc_match = re.search(r"Case description:\s*(.*)", text, re.DOTALL)

    title = title_match.group(1).strip() if title_match else ""
    description = desc_match.group(1).strip() if desc_match else ""

    return {
        "case_title": title,
        "case_description": description
    }


async def generate_case(i, llm, semaphore):
    async with semaphore:
        theme = themes[i % len(themes)]

        messages = [
            ("system", instruction),
            ("human", f"Theme: {theme}"),
        ]

        ai_msg = await llm.ainvoke(messages)
        text = ai_msg.text

        print(text)

        parsed = parse_output(text)
        parsed["theme"] = theme

        return parsed


async def run_generation(
    model_name: str,
    base_url: str,
    output_file: str = "output/cases.json"
):

    llm = ChatOpenAI(
        model=model_name,
        base_url=base_url,
        api_key="",
        reasoning_effort="high"
    )

    semaphore = asyncio.Semaphore(max_workers)

    tasks = [
        generate_case(i, llm, semaphore)
        for i in range(100)
    ]

    results = []

    for future in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
        result = await future
        results.append(result)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} cases to {output_file}")


if __name__ == "__main__":
    asyncio.run(
        run_generation(
            "openai/gpt-oss-20b",
            "http://dgx:9000/v1"
        )
    )