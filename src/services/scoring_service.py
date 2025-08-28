from src.config import TIME_LIMIT_CONFIG

def calculate_question_time_limit(difficulty_score: float | None) -> int:
    """
    Calculates the time limit for a question based on its difficulty score.
    This is a data-driven and more maintainable version of the original logic.
    Returns the time limit in seconds.
    """
    if difficulty_score is None:
        return TIME_LIMIT_CONFIG['base_time']

    # Default multiplier for scores outside the defined ranges (e.g., < 1.0)
    # This matches the original implementation's final 'else' block.
    multiplier = 1.0

    # The tiers are sorted by their difficulty score threshold.
    # We find the first tier that the question's score fits into.
    for score_threshold, mult in sorted(TIME_LIMIT_CONFIG['tiers'].items()):
        if difficulty_score <= score_threshold:
            multiplier = mult
            break
    else:
        # If the loop completes without breaking, the score is higher than all defined tiers.
        # In this case, we use the multiplier from the highest tier.
        highest_tier_multiplier = max(TIME_LIMIT_CONFIG['tiers'].values())
        multiplier = highest_tier_multiplier

    time_limit = TIME_LIMIT_CONFIG['base_time'] * multiplier
    return round(time_limit)
