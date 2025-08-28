import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import random
from collections import defaultdict

class SelectionReason(Enum):
    WEAKNESS = "weakness"
    SRS_DUE = "srs_due"
    NEW_QUESTION = "new"
    RANDOM_REVIEW = "random_review"

@dataclass
class QuestionScore:
    question_id: int
    score: float
    reason: SelectionReason
    metadata: Dict = field(default_factory=dict)

@dataclass
class UserPerformance:
    question_id: int
    correct_streak: int
    last_attempt_correct: bool
    last_attempt_date: datetime
    total_attempts: int
    total_correct: int
    next_review_date: Optional[datetime] = None

class UniversalQuestionSelector:
    """
    Universal question selection algorithm that works across all courses.
    Focuses on learning patterns rather than subject-specific difficulty.
    """
    
    def __init__(self, config: Dict = None, rng: Optional[random.Random] = None):
        # Default configuration - easily adjustable per course
        default_config = {
            'weakness_weight': 100,      # High priority for wrong answers
            'new_question_weight': 50,   # Medium priority for unseen questions
            'srs_due_weight': 30,        # SRS questions ready for review
            'srs_overdue_bonus': 20,     # Extra points for overdue SRS
            'random_review_weight': 5,   # Low priority for random review
            
            # Distribution targets (as percentages)
            'target_weakness_pct': 0.60,     # 60% weakness questions
            'target_new_pct': 0.25,          # 25% new questions  
            'target_srs_pct': 0.15,          # 15% SRS questions
            
            # SRS intervals in days (universal across subjects)
            'srs_intervals': [1, 3, 7, 14, 30, 60, 120, 240, 480],
            
            # Minimum performance data for reliable scoring
            'min_attempts_for_stats': 3,
        }
        
        self.config = {**default_config, **(config or {})}
        self.rng = rng or random.Random()
    
    def select_questions(self, 
                        user_id: int, 
                        course_id: int, 
                        quiz_length: int,
                        user_performance: List[UserPerformance],
                        available_questions: List[int]) -> List[QuestionScore]:
        """
        Main question selection method.
        Returns a list of questions with their selection reasoning.
        """
        
        if not isinstance(quiz_length, int) or quiz_length <= 0:
            return []

        if not available_questions:
            return []

        # Deduplicate and handle invalid inputs
        available_questions = list(set(available_questions))
        if user_performance is None:
            user_performance = []

        # Create performance lookup for fast access
        performance_map = {p.question_id: p for p in user_performance}
        
        # Score all available questions
        scored_questions = []
        for question_id in available_questions:
            score_data = self._score_question(question_id, performance_map.get(question_id))
            scored_questions.append(score_data)
        
        # Sort by score (highest first)
        scored_questions.sort(key=lambda x: x.score, reverse=True)
        
        # Apply intelligent selection with distribution control
        selected = self._apply_distribution_control(scored_questions, quiz_length)
        
        return selected
    
    def _score_question(self, question_id: int, performance: Optional[UserPerformance]) -> QuestionScore:
        """
        Score a single question based on user's performance history.
        This is the core of our universal algorithm.
        """
        
        # Case 1: New question (never attempted)
        if performance is None:
            return QuestionScore(
                question_id=question_id,
                score=self.config['new_question_weight'],
                reason=SelectionReason.NEW_QUESTION,
                metadata={'is_new': True}
            )
        
        # Case 2: Weakness (last attempt was wrong)
        if not performance.last_attempt_correct:
            # Clamp values to prevent invalid calculations from corrupt data
            total_attempts = max(performance.total_attempts, 1)
            total_correct = max(0, performance.total_correct)
            if total_correct > total_attempts:
                total_correct = 0 # Data integrity issue, assume worst case

            error_rate = 1 - (total_correct / total_attempts)
            weakness_boost = error_rate * 20  # Up to 20 extra points
            
            return QuestionScore(
                question_id=question_id,
                score=self.config['weakness_weight'] + weakness_boost,
                reason=SelectionReason.WEAKNESS,
                metadata={
                    'error_rate': error_rate,
                    'total_attempts': performance.total_attempts,
                    'consecutive_errors': self._calculate_consecutive_errors(performance)
                }
            )
        
        # Case 3: SRS - question answered correctly, check if due for review
        if performance.next_review_date:
            now = datetime.now(timezone.utc)
            next_review_date = performance.next_review_date
            if next_review_date.tzinfo is None:
                next_review_date = next_review_date.replace(tzinfo=timezone.utc)
            
            days_until_due = (next_review_date - now).days
            
            # Due or overdue
            if days_until_due <= 0:
                overdue_bonus = min(abs(days_until_due) * 2, self.config['srs_overdue_bonus'])
                return QuestionScore(
                    question_id=question_id,
                    score=self.config['srs_due_weight'] + overdue_bonus,
                    reason=SelectionReason.SRS_DUE,
                    metadata={
                        'days_overdue': abs(days_until_due),
                        'correct_streak': performance.correct_streak
                    }
                )
        
        # Case 4: Random review (correct but not in SRS system yet, or not due)
        # Lower priority, but still valuable for reinforcement
        recency_factor = self._calculate_recency_factor(performance.last_attempt_date)
        
        return QuestionScore(
            question_id=question_id,
            score=self.config['random_review_weight'] * recency_factor,
            reason=SelectionReason.RANDOM_REVIEW,
            metadata={
                'recency_factor': recency_factor,
                'days_since_last': (datetime.now(timezone.utc) - performance.last_attempt_date).days
            }
        )
    
    def _apply_distribution_control(self, 
                                  scored_questions: List[QuestionScore], 
                                  quiz_length: int) -> List[QuestionScore]:
        """
        Ensure we get a good distribution of question types, not just the highest scores.
        This prevents the quiz from being 100% weakness questions for struggling students.
        This version uses a more robust fallback and redistribution logic.
        """
        
        # Separate questions by type
        question_pools = {
            SelectionReason.WEAKNESS: sorted([q for q in scored_questions if q.reason == SelectionReason.WEAKNESS], key=lambda x: x.score, reverse=True),
            SelectionReason.NEW_QUESTION: sorted([q for q in scored_questions if q.reason == SelectionReason.NEW_QUESTION], key=lambda x: x.score, reverse=True),
            SelectionReason.SRS_DUE: sorted([q for q in scored_questions if q.reason == SelectionReason.SRS_DUE], key=lambda x: x.score, reverse=True),
            SelectionReason.RANDOM_REVIEW: sorted([q for q in scored_questions if q.reason == SelectionReason.RANDOM_REVIEW], key=lambda x: x.score, reverse=True)
        }

        # Calculate ideal counts for each category
        target_counts = {
            SelectionReason.WEAKNESS: int(quiz_length * self.config['target_weakness_pct']),
            SelectionReason.NEW_QUESTION: int(quiz_length * self.config['target_new_pct']),
            SelectionReason.SRS_DUE: int(quiz_length * self.config['target_srs_pct'])
        }
        target_counts[SelectionReason.RANDOM_REVIEW] = quiz_length - sum(target_counts.values())

        selected_ids = set()
        final_selection = []

        # Primary selection loop to fill quotas
        for reason, target_count in target_counts.items():
            pool = question_pools[reason]
            count = 0
            for question in pool:
                if count < target_count and question.question_id not in selected_ids:
                    final_selection.append(question)
                    selected_ids.add(question.question_id)
                    count += 1
        
        # Fallback loop to fill remaining slots if quotas weren't met
        remaining_slots = quiz_length - len(final_selection)
        if remaining_slots > 0:
            # Create a combined pool of all available, unselected questions
            fallback_pool = []
            for pool in question_pools.values():
                for question in pool:
                    if question.question_id not in selected_ids:
                        fallback_pool.append(question)
            
            # Sort the combined pool by score to get the best available questions
            fallback_pool.sort(key=lambda x: x.score, reverse=True)
            
            for question in fallback_pool:
                if len(final_selection) < quiz_length:
                    final_selection.append(question)
                    selected_ids.add(question.question_id)
                else:
                    break

        # Shuffle to avoid predictable patterns
        self.rng.shuffle(final_selection)
        
        # Log the final selection distribution for debugging
        final_dist = defaultdict(int)
        for q in final_selection:
            final_dist[q.reason.value] += 1
        logging.info(f"Final selection distribution for quiz_length {quiz_length}: {dict(final_dist)}")

        return final_selection[:quiz_length]
    
    def _calculate_consecutive_errors(self, performance: UserPerformance) -> int:
        """
        Estimate consecutive errors (would need actual attempt history for precision).
        For now, use inverse of correct streak as approximation.
        """
        if performance.correct_streak == 0:
            # Rough estimate based on total performance
            return min(performance.total_attempts - performance.total_correct, 5)
        return 0
    
    def _calculate_recency_factor(self, last_attempt_date: datetime) -> float:
        """
        Calculate a recency factor that slightly favors questions not seen recently.
        """
        now = datetime.now(timezone.utc)
        if last_attempt_date.tzinfo is None:
            last_attempt_date = last_attempt_date.replace(tzinfo=timezone.utc)
        days_since = (now - last_attempt_date).days
        
        if days_since < 1:
            return 0.5  # Just answered, lower priority
        elif days_since < 7:
            return 0.8  # Recent, but not too recent
        elif days_since < 30:
            return 1.0  # Good time frame for review
        else:
            return 1.2  # Haven't seen in a while, slight boost
    
    def calculate_next_review_date(self, correct_streak: int) -> datetime:
        """
        Universal SRS calculation - works for any subject.
        """
        intervals = self.config['srs_intervals']
        if not intervals:
            return datetime.now(timezone.utc) + timedelta(days=1)
            
        streak = max(0, correct_streak) # Clamp streak to be non-negative
        interval_days = intervals[min(streak, len(intervals) - 1)]
        return datetime.now(timezone.utc) + timedelta(days=interval_days)
    
    def get_selection_analytics(self, selected_questions: List[QuestionScore]) -> Dict:
        """
        Generate analytics about the selection for debugging/optimization.
        """
        reason_counts = defaultdict(int)
        for q in selected_questions:
            reason_counts[q.reason.value] += 1
        
        if not selected_questions:
            return {
                'total_questions': 0,
                'distribution': {},
                'distribution_percentages': {},
                'average_score': 0
            }

        return {
            'total_questions': len(selected_questions),
            'distribution': dict(reason_counts),
            'distribution_percentages': {
                reason: count / len(selected_questions) 
                for reason, count in reason_counts.items()
            },
            'average_score': sum(q.score for q in selected_questions) / len(selected_questions)
        }