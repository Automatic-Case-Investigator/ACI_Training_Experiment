import json
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import numpy as np

# File paths
VOTES_FILE = "output/investigation_all.json"
PER_JUDGE_VOTES_PLOT_FILE = "output/images/vote_judges.png"
MAJORITY_VOTES_PLOT_FILE = "output/images/vote_majority.png"

# Model identification
SYMBOL_TO_MODEL_NAME = {
    "A": "openai/gpt-oss:20b",
    "B": "acezxn/ACI_Cyber_Base_GPT_OSS_20B",
    "Tie": "Tie"
}

def aggregate_votes(data):
    """
    Aggregate votes from judges and compute majority winners for each case.
    
    Args:
        data: List of cases, each containing judge verdicts
        
    Returns:
        Tuple of (judge_counts, majority_counts) where:
        - judge_counts: dict mapping judge names to Counter of their votes
        - majority_counts: Counter of majority winners across all cases
    """
    judge_counts = defaultdict(Counter)
    majority_counts = Counter()

    for case in data:
        case_votes = Counter()

        # Tally votes per judge and aggregate case votes
        for judge, result in case["judges"].items():
            winner = result["winner"]
            judge_counts[judge][winner] += 1

            if winner in ["A", "B"]:
                case_votes[winner] += 1

        # Determine majority winner for this case (A wins ties if equal votes)
        if case_votes["B"] > case_votes["A"]:
            majority_winner = "B"
        elif case_votes["A"] > 0 or case_votes["B"] > 0:
            majority_winner = "A"  # A wins ties or when A has more votes
        else:
            majority_winner = "Tie"

        majority_counts[majority_winner] += 1

    return judge_counts, majority_counts


# Load and aggregate voting data
with open(VOTES_FILE) as f:
    data = json.load(f)

judge_counts, majority_counts = aggregate_votes(data)


def plot_judge_votes():
    """
    Create a stacked bar chart showing each judge's vote distribution.
    
    Displays votes for Model A, Model B, and Tie outcomes per judge.
    Saves the plot to vote_judges.png.
    """
    judges = list(judge_counts.keys())

    # Extract vote counts for each outcome per judge
    votes_model_a = np.array([judge_counts[judge].get("A", 0) for judge in judges])
    votes_model_b = np.array([judge_counts[judge].get("B", 0) for judge in judges])
    votes_tie = np.array([judge_counts[judge].get("Tie", 0) for judge in judges])

    x = np.arange(len(judges))

    plt.figure(figsize=(10, 6))

    # Create stacked bars
    bar_a = plt.bar(x, votes_model_a, label=SYMBOL_TO_MODEL_NAME["A"])
    bar_b = plt.bar(x, votes_model_b, bottom=votes_model_a, label=SYMBOL_TO_MODEL_NAME["B"])
    bar_tie = plt.bar(x, votes_tie, bottom=votes_model_a + votes_model_b, label="Tie")

    # Add value labels on bars
    plt.bar_label(bar_a, label_type="center")
    plt.bar_label(bar_b, label_type="center")

    plt.xticks(x, judges, rotation=45)
    plt.ylabel("Number of Votes")
    plt.title("Per-Judge Vote Distribution for Highest Quality SOC Task Generation")
    plt.legend()

    plt.tight_layout()
    plt.savefig(PER_JUDGE_VOTES_PLOT_FILE)
    

def plot_majority_vote():
    """
    Create a pie chart showing the overall majority winner distribution.
    
    Displays the percentage of cases won by each model based on majority voting.
    Saves the plot to vote_majority.png.
    """
    model_labels = [SYMBOL_TO_MODEL_NAME[outcome] for outcome in majority_counts.keys()]
    vote_counts = [majority_counts[outcome] for outcome in majority_counts.keys()]

    fig, ax = plt.subplots(figsize=(8, 8))

    # Create pie chart with percentage labels
    wedges = ax.pie(
        vote_counts,
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.75,
        radius=0.8,
        textprops={'fontsize': 12}
    )[0]

    # Add legend outside the pie chart
    ax.legend(
        wedges,
        model_labels,
        title="Models",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=10
    )

    ax.set_title(
        "Majority Vote: Highest Quality SOC Task Generation",
        pad=25,
        fontsize=14
    )

    ax.axis('equal')
    plt.tight_layout()
    plt.savefig(MAJORITY_VOTES_PLOT_FILE, bbox_inches="tight")


if __name__ == "__main__":
    plot_judge_votes()
    plot_majority_vote()
