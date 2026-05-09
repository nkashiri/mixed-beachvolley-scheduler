"""
Player Assignment Optimiser
============================
Reads the tournament schedule (best_matches_readable.csv) produced by the
schedule generator and assigns real players to the abstract Male/Female indices
so that matches are as balanced as possible.

Optimisation objectives (priority order)
  1. Minimise max score difference across all matches        (primary)
  2. Minimise total sum of score differences                 (secondary)

Outputs
  best_matches_assigned.csv  —  full schedule with real player names and scores
"""

import csv
import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# ─────────────────────────────────────────────────────────────────────────────
#  1.  LOAD SCHEDULE
# ─────────────────────────────────────────────────────────────────────────────

def read_matches_from_csv(filename="best_matches_readable.csv"):
    """
    Parse the schedule CSV into a flat list of matches.

    Each match is stored as (m1, f1, m2, f2) where the integers are the
    abstract Male/Female slot indices produced by the schedule generator.
    """
    matches = []

    with open(filename, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            m1 = int(row[2].split(" + ")[0][1:])
            f1 = int(row[2].split(" + ")[1][1:])
            m2 = int(row[3].split(" + ")[0][1:])
            f2 = int(row[3].split(" + ")[1][1:])
            matches.append((m1, f1, m2, f2))

    print(f"Loaded {len(matches)} matches.\n")
    return matches


# ─────────────────────────────────────────────────────────────────────────────
#  2.  EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_assignment(matches, male_map, female_map, male_scores, female_scores):
    """
    Compute quality metrics for a (male_map, female_map) assignment.

    Returns (max_diff, total_abs, signed_spread, max_abs_signed).

      max_diff       — largest score difference across all matches
      total_abs      — sum of score differences across all matches
      signed_spread  — spread of per-player signed sums (max − min);
                       a signed sum is the total of (my_team_score −
                       opponent_score) across all of a player's matches,
                       so positive = net winning, negative = net losing
      max_abs_signed — largest absolute signed sum: the single player
                       who is furthest from zero in either direction
    """
    N = len(male_scores)
    max_diff  = 0.0
    total_abs = 0.0
    signed    = [0.0] * (2 * N)   # [0..N-1] males, [N..2N-1] females

    for m1, f1, m2, f2 in matches:
        ma = male_map[m1];  fa = female_map[f1]
        mb = male_map[m2];  fb = female_map[f2]

        score_A = male_scores[ma] + female_scores[fa]
        score_B = male_scores[mb] + female_scores[fb]
        diff    = abs(score_A - score_B)

        total_abs += diff
        if diff > max_diff:
            max_diff = diff

        d = score_A - score_B          # positive → team A won
        signed[ma]     += d            # team-A male  benefits
        signed[N + fa] += d            # team-A female benefits
        signed[mb]     -= d            # team-B male  suffers
        signed[N + fb] -= d            # team-B female suffers

    signed_spread  = max(signed) - min(signed)
    max_abs_signed = max(abs(s) for s in signed)

    return max_diff, total_abs, signed_spread, max_abs_signed


def _composite(max_diff, total_abs, signed_spread, max_abs_signed):
    """
    Single scalar objective (lower = better).

    Priority order (each weight strictly dominates all lower-priority terms
    given realistic score ranges):
      1. max_diff       × 10⁹   — no match should be wildly unbalanced
      2. signed_spread  × 10⁶   — spread of per-player net signed sums
      3. max_abs_signed × 10³   — worst individual net signed sum
      4. total_abs      × 1     — overall total of score differences
    """
    return (max_diff       * 1_000_000_000 +
            signed_spread  * 1_000_000     +
            max_abs_signed * 1_000         +
            total_abs)


# ─────────────────────────────────────────────────────────────────────────────
#  3.  PLAYER ASSIGNMENT OPTIMISATION
# ─────────────────────────────────────────────────────────────────────────────

def assign_players_optimized(matches, male_scores, female_scores,
                              num_restarts=300, steps_per_restart=800):
    """
    Multi-start hill climbing over the space of (male permutation, female
    permutation) assignments.

    Each restart begins from a random initial permutation for both genders.
    At every step, a random male swap or female swap is tried and kept only
    if it strictly improves the composite objective.  The globally best
    assignment across all restarts is returned.
    """
    N = len(male_scores)
    print(f"Optimising player assignment "
          f"({num_restarts} restarts x {steps_per_restart} steps) ...\n")

    best_obj    = float('inf')
    best_male   = None
    best_female = None
    best_stats  = None

    for _ in range(num_restarts):
        male_map   = list(range(N)); random.shuffle(male_map)
        female_map = list(range(N)); random.shuffle(female_map)

        stats   = evaluate_assignment(matches, male_map, female_map,
                                      male_scores, female_scores)
        cur_obj = _composite(*stats)

        for _ in range(steps_per_restart):
            if random.random() < 0.5:
                i, j = random.sample(range(N), 2)
                male_map[i], male_map[j] = male_map[j], male_map[i]
                new_stats = evaluate_assignment(matches, male_map, female_map,
                                                male_scores, female_scores)
                new_obj = _composite(*new_stats)
                if new_obj < cur_obj:
                    cur_obj = new_obj;  stats = new_stats
                else:
                    male_map[i], male_map[j] = male_map[j], male_map[i]
            else:
                i, j = random.sample(range(N), 2)
                female_map[i], female_map[j] = female_map[j], female_map[i]
                new_stats = evaluate_assignment(matches, male_map, female_map,
                                                male_scores, female_scores)
                new_obj = _composite(*new_stats)
                if new_obj < cur_obj:
                    cur_obj = new_obj;  stats = new_stats
                else:
                    female_map[i], female_map[j] = female_map[j], female_map[i]

        if cur_obj < best_obj:
            best_obj    = cur_obj
            best_male   = male_map[:]
            best_female = female_map[:]
            best_stats  = stats

    md, ta, ss, ma_s = best_stats
    print(f"  Result ({len(matches)} matches): "
          f"Max diff={md:.0f} | Signed spread={ss:.0f} | "
          f"Max abs signed={ma_s:.0f} | Total abs diff={ta:.0f}\n")
    return best_male, best_female, best_stats


# ─────────────────────────────────────────────────────────────────────────────
#  4.  OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def print_player_mapping(male_map, female_map, male_names, female_names):
    """Print which real player is assigned to each abstract slot."""
    print("=" * 65)
    print("          PLAYER -> SLOT MAPPING")
    print("=" * 65)
    print("MALES   (slot <- real player):")
    for slot in range(len(male_map)):
        print(f"  M{slot:2d}  <-  {male_names[male_map[slot]]}")
    print("\nFEMALES (slot <- real player):")
    for slot in range(len(female_map)):
        print(f"  F{slot:2d}  <-  {female_names[female_map[slot]]}")
    print("=" * 65 + "\n")


def create_final_csv(matches, male_map, female_map, male_names, female_names,
                     male_scores, female_scores,
                     filename="best_matches_assigned.csv"):
    """
    Write the full schedule CSV with real player names and team scores.
    Match_ID is 1-indexed, in the same order as the input file.
    """
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Match_ID",
                         "Team_A_M", "Team_A_F", "Team_A_Score",
                         "Team_B_M", "Team_B_F", "Team_B_Score",
                         "Diff"])

        for match_id, (m1, f1, m2, f2) in enumerate(matches, start=1):
            ma = male_map[m1];  fa = female_map[f1]
            mb = male_map[m2];  fb = female_map[f2]

            score_A = male_scores[ma] + female_scores[fa]
            score_B = male_scores[mb] + female_scores[fb]
            diff    = abs(score_A - score_B)

            writer.writerow([match_id,
                             male_names[ma],   female_names[fa], round(score_A, 1),
                             male_names[mb],   female_names[fb], round(score_B, 1),
                             round(diff, 1)])

    print(f"Saved: {filename}")


# ─────────────────────────────────────────────────────────────────────────────
#  5.  BALANCE HEATMAP
# ─────────────────────────────────────────────────────────────────────────────

def plot_balance_heatmap(matches, male_map, female_map, male_names, female_names,
                         male_scores, female_scores,
                         filename="balance_heatmap.png"):
    """
    For every player, collect the score difference of each match they play,
    sort those diffs low → high, and display the result as a heatmap.

    Layout
    ------
    Rows    — players (males above the divider, females below),
              each labelled with their real name and skill score.
    Columns — match rank: column 1 is their most balanced match,
              the last column their most unbalanced one.
    Colour  — score difference (green = balanced, red = unbalanced).
    """
    N = len(male_scores)

    # Collect diffs per real player index
    male_diffs   = [[] for _ in range(N)]
    female_diffs = [[] for _ in range(N)]

    for m1, f1, m2, f2 in matches:
        ma = male_map[m1];  fa = female_map[f1]
        mb = male_map[m2];  fb = female_map[f2]

        score_A = male_scores[ma] + female_scores[fa]
        score_B = male_scores[mb] + female_scores[fb]

        # Signed from each player's team perspective:
        # positive → their team outscored the opponent (favourable)
        # negative → their team was outscored (unfavourable)
        male_diffs[ma].append(score_A - score_B)
        male_diffs[mb].append(score_B - score_A)
        female_diffs[fa].append(score_A - score_B)
        female_diffs[fb].append(score_B - score_A)

    # Sort each player's diffs low → high
    for lst in male_diffs + female_diffs:
        lst.sort()

    n_cols = max(len(d) for d in male_diffs + female_diffs)

    def to_row(diffs):
        row = np.full(n_cols, np.nan)
        row[:len(diffs)] = diffs
        return row

    male_matrix   = np.array([to_row(d) for d in male_diffs])
    female_matrix = np.array([to_row(d) for d in female_diffs])
    matrix = np.vstack([male_matrix, female_matrix])

    # Row labels: "Name (score)"
    ylabels = ([f"{male_names[i]}  [{male_scores[i]}]"   for i in range(N)] +
               [f"{female_names[i]}  [{female_scores[i]}]" for i in range(N)])

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig_h = max(7, (2 * N) * 0.38)
    fig_w = max(10, n_cols * 0.72)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    vmax = int(np.nanmax(np.abs(matrix)))
    cmap = plt.cm.RdYlGn            # red = negative (lost), green = positive (won)

    im = ax.imshow(matrix, aspect='auto', cmap=cmap, vmin=-vmax, vmax=vmax)

    # Annotate every cell with its value
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            val = matrix[r, c]
            if not np.isnan(val):
                # Dark text on pale cells (near zero), white on saturated cells
                saturation = abs(val) / vmax if vmax else 0
                txt_col = 'white' if saturation > 0.6 else 'black'
                ax.text(c, r, f"{int(val):+}", ha='center', va='center',
                        fontsize=7.5, color=txt_col, fontweight='bold')

    # Axes labels
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=9)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([f"#{i+1}" for i in range(n_cols)], fontsize=8)
    ax.set_xlabel("Match rank  (sorted: most unfavourable → most favourable)", fontsize=9)
    ax.set_title("Match Balance per Player — signed score difference (negative = lost, positive = won)",
                 fontsize=11, pad=10)

    # Divider between males and females
    ax.axhline(N - 0.5, color='black', linewidth=2)
    ax.text(-0.7, N / 2 - 0.5,      "MALES",   va='center', ha='right',
            fontsize=8, fontstyle='italic', rotation=90)
    ax.text(-0.7, N + N / 2 - 0.5,  "FEMALES", va='center', ha='right',
            fontsize=8, fontstyle='italic', rotation=90)

    # Colourbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.55, pad=0.02)
    cbar.set_label("Score difference", fontsize=9)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


# ─────────────────────────────────────────────────────────────────────────────
#  6.  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # =========================================================================
    #  CHANGE THESE to match your actual players and skill scores
    # =========================================================================
    male_names  = ["MC", "FG", "PP", "TP", "MX", "CX", "SR", "NV", "GB", "DS", "TB", "FC"]
    male_scores = [5,     4,    5,    6,    6,    6,    6,    5,    6,    5,    6,    4]

    female_names  = ["CZ", "CS", "AV", "RB", "GP", "MD", "IC", "GL", "MT", "GC", "RC", "WL"]
    female_scores = [5,      5,    4,    4,    5,    4,    5,    6,    3,    5,    3,    3]
    # =========================================================================

    matches = read_matches_from_csv("best_matches_readable.csv")

    male_map, female_map, stats = assign_players_optimized(
        matches, male_scores, female_scores)

    print_player_mapping(male_map, female_map, male_names, female_names)

    create_final_csv(matches, male_map, female_map, male_names, female_names,
                     male_scores, female_scores)

    plot_balance_heatmap(matches, male_map, female_map, male_names, female_names,
                         male_scores, female_scores)
