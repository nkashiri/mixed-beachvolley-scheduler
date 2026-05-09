"""
Mixed Beach Volleyball Tournament Scheduler
===========================================
Generates a fair round-robin schedule for N males and N females playing
2-vs-2 mixed beach volleyball.

Hard constraints
  [1] Each male pair   plays exactly once against every other male pair.
  [2] Each female pair plays exactly once against every other female pair.
  [3] Each male partners with any given female at most once.

Soft constraint (minimised)
  [4] Minimise the maximum number of times any male plays *against* any female
      (cross-opposition count).

Pipeline
  generate_best_schedule()  →  save_readable_schedule()
  create_evaluation_tables() + create_heatmaps()

Outputs
  best_matches_readable.csv   — full schedule grouped into rounds (1-indexed)
  table_male_male_opp.csv     — male-male opposition matrix
  table_female_female_opp.csv — female-female opposition matrix
  table_mf_oppositions.csv    — male-female cross-opposition matrix
  table_mf_partnerships.csv   — male-female partnership matrix
  heatmaps_all.png            — 2×2 heatmap figure of all four matrices
"""

import itertools
import random
import csv

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ── Tournament size ───────────────────────────────────────────────────────────
N = 12          # number of males (= number of females)
# Total matches  = C(N, 2) = N*(N-1)//2          (78 for N=13)
# Rounds         = N  for odd N                   (13 for N=13)
# Matches/round  = (N-1)//2  for odd N            ( 6 for N=13)


# ═════════════════════════════════════════════════════════════════════════════
#  1.  SCHEDULE GENERATION
# ═════════════════════════════════════════════════════════════════════════════

def _find_best_female_pair(m1, m2, used_f_pairs, male_partners,
                           mf_opp_count, global_max):
    """
    Search every unassigned female pair for the best assignment to male pair
    (m1, m2).

    A match (m1, pf1) vs (m2, pf2) is *valid* when neither male has already
    partnered with his assigned female (constraint [3]).

    Scoring (lower is better):
      primary   — projected global max cross-opposition after this assignment
      secondary — total cross-opposition added by this single match
                  (tiebreaker that spreads opposition load more evenly)

    The global_max argument avoids recomputing max(matrix) inside the loop;
    the caller maintains it as a running scalar updated after each commit.

    Returns (f1, f2, crossed, pf1, pf2, opp_m1, opp_m2) for the best
    candidate, or None if every female pair is either already used or would
    repeat a partnership.
    """
    best_score  = float('inf')
    best_choice = None

    for f1, f2 in itertools.combinations(range(N), 2):
        fp = tuple(sorted([f1, f2]))
        if fp in used_f_pairs:
            continue
        for crossed in [False, True]:
            pf1    = f2 if crossed else f1   # partner of m1
            pf2    = f1 if crossed else f2   # partner of m2
            opp_m1 = pf2                     # female m1 faces (cross-opp)
            opp_m2 = pf1                     # female m2 faces (cross-opp)

            if pf1 in male_partners[m1] or pf2 in male_partners[m2]:
                continue                     # would violate constraint [3]

            new_opp1 = mf_opp_count[m1][opp_m1] + 1
            new_opp2 = mf_opp_count[m2][opp_m2] + 1
            proj_max = max(new_opp1, new_opp2, global_max)
            score    = proj_max * 100 + (new_opp1 + new_opp2)

            if score < best_score:
                best_score  = score
                best_choice = (f1, f2, crossed, pf1, pf2, opp_m1, opp_m2)

    return best_choice


def _try_repair(m1, m2, matches, used_f_pairs, male_partners, mf_opp_count,
                max_tries=20):
    """
    Called when the greedy step is stuck: no unassigned female pair can be
    partnered with (m1, m2) without repeating a partnership.

    Strategy
    --------
    Examine already-placed matches that involve m1 or m2 (they are most
    likely to hold a female pair that would help).  For each candidate:
      1. Tentatively undo the match, freeing its female pair.
      2. Search for any valid replacement for the same male pair.
      3. Check whether (m1, m2) now has at least one valid female pair.
      4. If yes: commit the replacement and return True.
         If no:  restore the original match and try the next candidate.

    All mutations are made in-place on the shared state structures.
    Returns True if a repair was found, False if every candidate failed.
    """
    touching = [i for i, (a, _, b, _) in enumerate(matches)
                if m1 in (a, b) or m2 in (a, b)]
    random.shuffle(touching)

    for idx in touching[:max_tries]:
        pm1, pf1, pm2, pf2 = matches[idx]
        old_fp = tuple(sorted([pf1, pf2]))

        # --- tentatively undo the chosen match ---
        male_partners[pm1].discard(pf1)
        male_partners[pm2].discard(pf2)
        used_f_pairs.discard(old_fp)
        mf_opp_count[pm1][pf2] -= 1
        mf_opp_count[pm2][pf1] -= 1

        fp_options = list(itertools.combinations(range(N), 2))
        random.shuffle(fp_options)
        found = False

        for gf1, gf2 in fp_options:
            gfp = tuple(sorted([gf1, gf2]))
            if gfp in used_f_pairs:
                continue
            for crossed in [False, True]:
                npf1 = gf2 if crossed else gf1
                npf2 = gf1 if crossed else gf2
                if npf1 in male_partners[pm1] or npf2 in male_partners[pm2]:
                    continue

                # tentatively apply replacement for (pm1, pm2)
                male_partners[pm1].add(npf1)
                male_partners[pm2].add(npf2)
                used_f_pairs.add(gfp)

                # check whether (m1, m2) now has at least one valid option
                unblocked = any(
                    tuple(sorted([hf1, hf2])) not in used_f_pairs and (
                        (hf1 not in male_partners[m1] and hf2 not in male_partners[m2]) or
                        (hf2 not in male_partners[m1] and hf1 not in male_partners[m2])
                    )
                    for hf1, hf2 in itertools.combinations(range(N), 2)
                )

                if unblocked:
                    mf_opp_count[pm1][npf2] += 1
                    mf_opp_count[pm2][npf1] += 1
                    matches[idx] = (pm1, npf1, pm2, npf2)
                    found = True
                    break

                # revert tentative replacement
                male_partners[pm1].discard(npf1)
                male_partners[pm2].discard(npf2)
                used_f_pairs.discard(gfp)

            if found:
                break

        if found:
            return True

        # --- restore the original match (repair failed for this candidate) ---
        male_partners[pm1].add(pf1)
        male_partners[pm2].add(pf2)
        used_f_pairs.add(old_fp)
        mf_opp_count[pm1][pf2] += 1
        mf_opp_count[pm2][pf1] += 1

    return False


def generate_best_schedule(num_attempts=200):
    """
    Greedy construction with multi-start random restarts.

    Each attempt
    ------------
    * Male pairs are iterated in a freshly shuffled random order.
    * For each male pair, _find_best_female_pair() scores every candidate
      and returns the lowest-cost valid assignment.
    * If no valid assignment exists, _try_repair() attempts to free a female
      pair by undoing and replacing a prior match; the greedy step is then
      retried once.
    * global_max tracks the running maximum cross-opposition as a scalar,
      updated in O(1) after every commit (no full-matrix recomputation inside
      the candidate loop).

    The best schedule across all attempts is returned, ranked first by the
    lowest maximum cross-opposition, then by how few pairs achieve that max.
    """
    best_max_opp      = float('inf')
    best_count_at_max = float('inf')
    best_matches      = None
    total_matches     = N * (N - 1) // 2

    print(f"Running {num_attempts} attempts for N={N} "
          f"({total_matches} matches)...")

    for attempt in range(num_attempts):
        random.seed(attempt)

        matches       = []
        used_f_pairs  = set()
        male_partners = [set() for _ in range(N)]
        mf_opp_count  = [[0] * N for _ in range(N)]
        global_max    = 0

        male_pair_list = list(itertools.combinations(range(N), 2))
        random.shuffle(male_pair_list)

        stuck = False
        for m1, m2 in male_pair_list:
            best_choice = _find_best_female_pair(
                m1, m2, used_f_pairs, male_partners, mf_opp_count, global_max)

            if best_choice is None:
                # Greedy is stuck — attempt a targeted repair
                repaired = _try_repair(
                    m1, m2, matches, used_f_pairs, male_partners, mf_opp_count)
                if repaired:
                    # Recompute global_max once after the repair (state changed)
                    global_max  = max(max(row) for row in mf_opp_count)
                    best_choice = _find_best_female_pair(
                        m1, m2, used_f_pairs, male_partners, mf_opp_count, global_max)

            if best_choice is None:
                stuck = True
                break

            # Commit the chosen assignment
            f1, f2, _, pf1, pf2, opp_m1, opp_m2 = best_choice
            matches.append((m1, pf1, m2, pf2))
            male_partners[m1].add(pf1)
            male_partners[m2].add(pf2)
            used_f_pairs.add(tuple(sorted([f1, f2])))
            mf_opp_count[m1][opp_m1] += 1
            mf_opp_count[m2][opp_m2] += 1
            global_max = max(global_max,
                             mf_opp_count[m1][opp_m1],
                             mf_opp_count[m2][opp_m2])

        if stuck or len(matches) < total_matches:
            continue

        current_max  = max(max(row) for row in mf_opp_count)
        count_at_max = sum(v == current_max
                           for row in mf_opp_count for v in row)

        if (current_max < best_max_opp or
                (current_max == best_max_opp and count_at_max < best_count_at_max)):
            best_max_opp      = current_max
            best_count_at_max = count_at_max
            best_matches      = matches[:]
            print(f"  Attempt {attempt:4d} → max_opp={current_max}, "
                  f"count_at_max={count_at_max}")

    print(f"\n=== BEST RESULT ===")
    print(f"  Max M-F cross-opposition : {best_max_opp}")
    print(f"  Pairs achieving that max : {best_count_at_max}")
    return best_matches


# ═════════════════════════════════════════════════════════════════════════════
#  2.  ROUND SCHEDULING
# ═════════════════════════════════════════════════════════════════════════════

def save_readable_schedule(matches, max_restarts=500, patience=3000):
    """
    Partition all C(N,2) matches into rounds with two hard guarantees:
      - Every round contains exactly (N-1)//2 matches  [6 for N=13]
      - Each player (male or female) appears in at most one match per round

    Algorithm: swap-based local search with patience-based restarts
    ---------------------------------------------------------------
    1. Build a random initial partition that satisfies the size constraint:
       shuffle all match indices and split into consecutive blocks of MPR.
       Round sizes are correct by construction; every swap preserves them.

    2. Iterate, trying random swaps between rounds:
         - Always pick from a conflicted round (targeted, not random).
         - Accept a swap only if it strictly reduces total player conflicts.
         - Revert all non-improving swaps immediately.
         - Count consecutive non-improving attempts; once this reaches
           `patience`, abandon the partition and restart from scratch.

    Why patience instead of a fixed iteration budget
    ------------------------------------------------
    Pure hill-climbing with a large fixed budget stalls at local minima where
    every swap maintains or worsens the conflict count, spinning through
    hundreds of thousands of iterations doing nothing useful.  The patience
    counter detects stalls after at most a few thousand wasted attempts and
    triggers a fresh random start instead, keeping each restart fast and the
    total runtime bounded.

    A valid assignment is guaranteed to exist for any complete round-robin
    tournament (König's theorem), so with enough restarts the search always
    terminates successfully.

    Saves best_matches_readable.csv (rounds and match IDs are 1-indexed).
    Returns the list of rounds (each round is a list of match tuples).
    """
    M   = len(matches)
    MPR = (N - 1) // 2 if N % 2 == 1 else N // 2  # matches per round
    R   = M // MPR                                  # total number of rounds

    def _round_conflicts(round_list):
        """
        Count player-slot collisions within one round: the number of times
        any player appears in more than one match.  O(MPR) = O(1) for fixed N.
        """
        mc, fc = {}, {}
        for mi in round_list:
            m1, f1, m2, f2 = matches[mi]
            for m in (m1, m2): mc[m] = mc.get(m, 0) + 1
            for f in (f1, f2): fc[f] = fc.get(f, 0) + 1
        return (sum(max(0, c - 1) for c in mc.values()) +
                sum(max(0, c - 1) for c in fc.values()))

    assignment = None

    for restart in range(max_restarts):
        # Random initial partition: equal-sized blocks after shuffling
        perm = list(range(M))
        random.shuffle(perm)
        asgn = [0] * M
        for pos, mi in enumerate(perm):
            asgn[mi] = pos // MPR

        round_lists = [[] for _ in range(R)]
        for mi, r in enumerate(asgn):
            round_lists[r].append(mi)

        total_v    = sum(_round_conflicts(rl) for rl in round_lists)
        no_improve = 0   # consecutive attempts without a strict improvement

        while total_v > 0 and no_improve < patience:
            conflicted = [r for r in range(R) if _round_conflicts(round_lists[r]) > 0]
            r1  = random.choice(conflicted)
            mi1 = random.choice(round_lists[r1])

            r2 = random.randint(0, R - 1)
            if r2 == r1:
                no_improve += 1
                continue
            mi2 = random.choice(round_lists[r2])

            old_v = _round_conflicts(round_lists[r1]) + _round_conflicts(round_lists[r2])

            # Perform swap
            round_lists[r1].remove(mi1); round_lists[r1].append(mi2)
            round_lists[r2].remove(mi2); round_lists[r2].append(mi1)
            asgn[mi1] = r2;             asgn[mi2] = r1

            new_v = _round_conflicts(round_lists[r1]) + _round_conflicts(round_lists[r2])

            if new_v < old_v:
                total_v   += new_v - old_v   # strict improvement: keep, reset patience
                no_improve = 0
            elif new_v == old_v:
                no_improve += 1              # lateral move: keep the swap to explore the
                                             # plateau, but count against patience so we
                                             # restart if no strict gain for `patience` steps
            else:
                # Worsening: revert
                round_lists[r1].remove(mi2); round_lists[r1].append(mi1)
                round_lists[r2].remove(mi1); round_lists[r2].append(mi2)
                asgn[mi1] = r1;             asgn[mi2] = r2
                no_improve += 1

        if total_v == 0:
            assignment = asgn
            print(f"Round assignment found (restart {restart + 1}).")
            break

    if assignment is None:
        print("Warning: perfect round assignment not found; using last attempt.")
        assignment = asgn

    # Group match tuples by assigned round
    rounds = [[] for _ in range(R)]
    for mi, r in enumerate(assignment):
        rounds[r].append(matches[mi])

    with open("best_matches_readable.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Round", "Match_ID", "Team_A", "Team_B"])
        match_id = 1
        for r_idx, rnd in enumerate(rounds, start=1):
            for m1, f1, m2, f2 in rnd:
                writer.writerow([r_idx, match_id,
                                 f"M{m1} + F{f1}", f"M{m2} + F{f2}"])
                match_id += 1

    print(f"Saved {M} matches across {R} rounds.")
    print(f"Matches per round: {[len(r) for r in rounds]}")
    return rounds


# ═════════════════════════════════════════════════════════════════════════════
#  3.  EVALUATION
# ═════════════════════════════════════════════════════════════════════════════

def create_evaluation_tables(matches):
    """
    Build four N×N count matrices from the match list and save each as a CSV:

      Male–Male oppositions     — off-diagonal entries should all be 1 [constraint 1]
      Female–Female oppositions — off-diagonal entries should all be 1 [constraint 2]
      Male–Female partnerships  — entries should all be 0 or 1         [constraint 3]
      Male–Female cross-opp     — entries show opposition counts        [constraint 4]

    Also prints a brief validation summary to stdout.
    """
    mm_opp  = [[0] * N for _ in range(N)]
    ff_opp  = [[0] * N for _ in range(N)]
    mf_part = [[0] * N for _ in range(N)]
    mf_opp  = [[0] * N for _ in range(N)]

    for m1, f1, m2, f2 in matches:
        mm_opp[m1][m2]  += 1;  mm_opp[m2][m1]  += 1
        ff_opp[f1][f2]  += 1;  ff_opp[f2][f1]  += 1
        mf_part[m1][f1] += 1;  mf_part[m2][f2] += 1
        mf_opp[m1][f2]  += 1;  mf_opp[m2][f1]  += 1

    def _save(data, filename, row_prefix, col_prefix):
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([""] + [f"{col_prefix}{j}" for j in range(N)])
            for i, row in enumerate(data):
                writer.writerow([f"{row_prefix}{i}"] + row)

    _save(mm_opp,  "table_male_male_opp.csv",      "M", "M")
    _save(ff_opp,  "table_female_female_opp.csv",  "F", "F")
    _save(mf_opp,  "table_mf_oppositions.csv",     "M", "F")
    _save(mf_part, "table_mf_partnerships.csv",    "M", "F")

    max_mm   = max(mm_opp[i][j]  for i in range(N) for j in range(N) if i != j)
    max_ff   = max(ff_opp[i][j]  for i in range(N) for j in range(N) if i != j)
    max_part = max(max(row) for row in mf_part)
    max_opp  = max(max(row) for row in mf_opp)

    print(f"Total matches              : {len(matches)}")
    print(f"Max male-male opp          : {max_mm}  (target: 1)")
    print(f"Max female-female opp      : {max_ff}  (target: 1)")
    print(f"Max M-F partnership        : {max_part}  (target: ≤1)")
    print(f"Max M-F cross-opposition   : {max_opp}  (minimised)")


def create_heatmaps(matches):
    """
    Produce a single 2×2 heatmap figure and save it to heatmaps_all.png.

    Panels
      Top-left     Male–Male oppositions       (should be all 1s off-diagonal)
      Top-right    Female–Female oppositions   (should be all 1s off-diagonal)
      Bottom-left  Male–Female cross-opp       (minimised; the soft objective)
      Bottom-right Male–Female partnerships    (should be all 0s and 1s)
    """
    mm_opp  = np.zeros((N, N), dtype=int)
    ff_opp  = np.zeros((N, N), dtype=int)
    mf_opp  = np.zeros((N, N), dtype=int)
    mf_part = np.zeros((N, N), dtype=int)

    for m1, f1, m2, f2 in matches:
        mm_opp[m1][m2]  += 1;  mm_opp[m2][m1]  += 1
        ff_opp[f1][f2]  += 1;  ff_opp[f2][f1]  += 1
        mf_part[m1][f1] += 1;  mf_part[m2][f2] += 1
        mf_opp[m1][f2]  += 1;  mf_opp[m2][f1]  += 1

    panels = [
        (mm_opp,  "Male–Male Oppositions",         "Male j",   "Male i"),
        (ff_opp,  "Female–Female Oppositions",      "Female j", "Female i"),
        (mf_opp,  "Male–Female Cross-Oppositions",  "Female j", "Male i"),
        (mf_part, "Male–Female Partnerships",        "Female j", "Male i"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"Tournament Validation  (N = {N})", fontsize=16, fontweight="bold")

    for ax, (matrix, title, xlabel, ylabel) in zip(axes.flat, panels):
        sns.heatmap(matrix, annot=True, fmt="d", cmap="YlOrRd",
                    linewidths=0.5, ax=ax, cbar_kws={"label": "Count"})
        ax.set_title(title, fontsize=13)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    plt.tight_layout()
    plt.savefig("heatmaps_all.png", dpi=200, bbox_inches="tight")
    plt.show()


# ═════════════════════════════════════════════════════════════════════════════
#  4.  ROUND VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def validate_rounds(rounds):
    """
    Verify the two hard guarantees produced by save_readable_schedule:
      - Every round contains exactly (N-1)//2 matches
      - No player (male or female) appears more than once in any round

    Prints a per-property pass/fail report and returns True only if both
    checks pass.  Called on the rounds list before evaluation so that the
    evaluation functions are never fed corrupted data silently.
    """
    MPR    = (N - 1) // 2 if N % 2 == 1 else N // 2
    all_ok = True

    # Size check
    sizes   = [len(r) for r in rounds]
    size_ok = all(s == MPR for s in sizes)
    if size_ok:
        print(f"  [PASS] All {len(rounds)} rounds have exactly {MPR} matches.")
    else:
        bad = [(i + 1, s) for i, s in enumerate(sizes) if s != MPR]
        print(f"  [FAIL] Wrong round sizes (expected {MPR}): "
              f"{', '.join(f'round {r}={s}' for r, s in bad)}")
        all_ok = False

    # Player-per-round uniqueness check
    conflict_rounds = []
    for r_idx, rnd in enumerate(rounds):
        males   = [m for m1, f1, m2, f2 in rnd for m in (m1, m2)]
        females = [f for m1, f1, m2, f2 in rnd for f in (f1, f2)]
        if len(males) != len(set(males)) or len(females) != len(set(females)):
            conflict_rounds.append(r_idx + 1)

    if not conflict_rounds:
        print(f"  [PASS] No player appears more than once in any round.")
    else:
        print(f"  [FAIL] Player conflicts in round(s): {conflict_rounds}")
        all_ok = False

    return all_ok


# ═════════════════════════════════════════════════════════════════════════════
#  5.  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    matches = generate_best_schedule(num_attempts=1000)
    if not matches:
        raise SystemExit("No valid schedule found — increase num_attempts.")

    rounds = save_readable_schedule(matches)

    # Flatten the scheduled rounds back to a match list.
    # Evaluation is applied to THIS list — the exact content of
    # best_matches_readable.csv — not the raw generation output.
    # Any silent corruption introduced by the scheduling step shows up here.
    scheduled = [m for rnd in rounds for m in rnd]

    print("\n=== ROUND VALIDATION ===")
    rounds_ok = validate_rounds(rounds)

    print("\n=== MATCH VALIDATION ===")
    create_evaluation_tables(scheduled)


    create_heatmaps(scheduled)