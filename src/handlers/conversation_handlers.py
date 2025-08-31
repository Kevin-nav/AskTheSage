import logging
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, PollAnswerHandler
from sqlalchemy.exc import IntegrityError

from src.database import get_db
from src.services import navigation_service, quiz_service, scoring_service
from src.services.notification_service import send_new_feedback_notification
from src.models.models import QuestionReport, Question, User, Faculty, Program, QuizSessionQuestion, Course, Feedback # Import QuestionReport, Question, User, Faculty, and Program models

# Set up logger
logger = logging.getLogger(__name__)

    # State definitions
CHOOSE_FACULTY, CHOOSE_PROGRAM, CHOOSE_LEVEL, CHOOSE_COURSE, CHOOSE_QUIZ_LENGTH, IN_QUIZ, AWAITING_REPORT_REASON, CONFIRM_PREFERENCES = range(8)

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Check if the user is already in the quiz setup process
    if context.user_data.get('in_quiz_setup', False):
        await update.message.reply_text("You are already setting up a quiz. Please continue your selection or type /cancel to start over.")
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    context.user_data['chat_id'] = chat_id
    context.user_data['user_id'] = user_id
    context.user_data['in_quiz_setup'] = True  # Set the flag
    logger.info(f"Entering start_quiz for chat_id: {chat_id}, user_id: {user_id}")

    with get_db() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            # Create new user if not exists
            user = User(
                telegram_id=user_id,
                username=update.effective_user.username,
                full_name=update.effective_user.full_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        if user.preferred_faculty_id and user.preferred_program_id:
            preferred_faculty = db.query(Faculty).filter_by(id=user.preferred_faculty_id).first()
            preferred_program = db.query(Program).filter_by(id=user.preferred_program_id).first()

            if preferred_faculty and preferred_program:
                keyboard = [
                    [InlineKeyboardButton(f"Use previous: {preferred_faculty.name} - {preferred_program.name}", callback_data="use_previous_settings")],
                    [InlineKeyboardButton("Choose new settings", callback_data="choose_new_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Welcome back! Would you like to use your previous settings or choose new ones?", reply_markup=reply_markup)
                return CONFIRM_PREFERENCES
    
        faculties = navigation_service.get_all_faculties(db)
        keyboard = [[InlineKeyboardButton(fac.name, callback_data=f"fac_{fac.id}")] for fac in faculties]
        reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please choose a faculty:", reply_markup=reply_markup)
    return CHOOSE_FACULTY

async def confirm_preferences_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "use_previous_settings":
        with get_db() as db:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if user and user.preferred_faculty_id and user.preferred_program_id:
                context.user_data['faculty_id'] = user.preferred_faculty_id
                context.user_data['program_id'] = user.preferred_program_id
                
                # Directly move to choosing level
                levels = navigation_service.get_levels_for_program(db, user.preferred_program_id)
                keyboard = [[InlineKeyboardButton(lvl.name, callback_data=f"lvl_{lvl.id}")] for lvl in levels]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text="Using your previous settings. Now choose your level:", reply_markup=reply_markup)
                return CHOOSE_LEVEL
            else:
                await query.edit_message_text(text="Could not retrieve previous settings. Please choose new ones.")
                # Fallback to choosing faculty
                faculties = navigation_service.get_all_faculties(db)
                keyboard = [[InlineKeyboardButton(fac.name, callback_data=f"fac_{fac.id}")] for fac in faculties]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text="Please choose a faculty:", reply_markup=reply_markup)
                return CHOOSE_FACULTY
    elif query.data == "choose_new_settings":
        with get_db() as db:
            faculties = navigation_service.get_all_faculties(db)
            keyboard = [[InlineKeyboardButton(fac.name, callback_data=f"fac_{fac.id}")] for fac in faculties]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="Please choose a faculty:", reply_markup=reply_markup)
        return CHOOSE_FACULTY
    return ConversationHandler.END

async def faculty_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    faculty_id = int(query.data.split('_')[1])
    context.user_data['faculty_id'] = faculty_id
    user_id = update.effective_user.id
    with get_db() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if user:
            user.preferred_faculty_id = faculty_id
            db.commit()
        programs = navigation_service.get_programs_for_faculty(db, faculty_id)
        keyboard = [[InlineKeyboardButton(prog.name, callback_data=f"prog_{prog.id}")] for prog in programs]
        reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Great! Now choose your program:", reply_markup=reply_markup)
    return CHOOSE_PROGRAM

async def program_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    program_id = int(query.data.split('_')[1])
    context.user_data['program_id'] = program_id
    user_id = update.effective_user.id
    with get_db() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if user:
            user.preferred_program_id = program_id
            db.commit()
        levels = navigation_service.get_levels_for_program(db, program_id)
        keyboard = [[InlineKeyboardButton(lvl.name, callback_data=f"lvl_{lvl.id}")] for lvl in levels]
        reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Awesome! Now choose your level:", reply_markup=reply_markup)
    return CHOOSE_LEVEL

async def level_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    level_id = int(query.data.split('_')[1])
    program_id = context.user_data['program_id']
    with get_db() as db:
        courses = navigation_service.get_courses_for_program_and_level(db, program_id, level_id)
        keyboard = [[InlineKeyboardButton(course.name, callback_data=f"course_{course.id}")] for course in courses]
        reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Excellent! Finally, choose your course:", reply_markup=reply_markup)
    return CHOOSE_COURSE

async def course_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    course_id = int(query.data.split('_')[1])
    context.user_data['course_id'] = course_id
    keyboard = [
        [InlineKeyboardButton("10 Questions", callback_data="len_10")],
        [InlineKeyboardButton("20 Questions", callback_data="len_20")],
        [InlineKeyboardButton("50 Questions", callback_data="len_50")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="How many questions would you like for your quiz?", reply_markup=reply_markup)
    return CHOOSE_QUIZ_LENGTH

async def quiz_length_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    quiz_length = int(query.data.split('_')[1])
    course_id = context.user_data['course_id']
    telegram_id = update.effective_user.id
    context.user_data['user_id'] = telegram_id
    logger.info(f"User chose quiz length: {quiz_length} for course_id: {course_id}")
    with get_db() as db:
        try:
            context.user_data.pop('in_quiz_setup', None)  # Clear the setup flag
            quiz_session = quiz_service.start_new_quiz(db, telegram_id, course_id, quiz_length)
            context.user_data['current_quiz_session_id'] = quiz_session.id
            logger.info(f"DEBUG: Context object in quiz_length_choice before ask_question: {context} (Type: {type(context)})")
            await query.edit_message_text(text=f"Starting your {quiz_session.total_questions}-question quiz...")
            chat_id = context.user_data['chat_id'] # Retrieve chat_id from user_data
            return await ask_question(context, chat_id, telegram_id)
        except IntegrityError:
            logger.warning(f"User {telegram_id} tried to start a quiz while another was in progress, caught by DB constraint.")
            await query.edit_message_text(text="You already have an ongoing quiz. Please complete it or use /cancel to end it.")
            return ConversationHandler.END
        except Exception as e:
            error_message = str(e)
            if "ongoing quiz" in error_message:
                await query.edit_message_text(text="You already have an ongoing quiz. Please complete it or use /cancel to end it.")
            else:
                await query.edit_message_text(text=f"An error occurred while starting the quiz: {error_message}")
            logger.error(f"Error starting quiz for user {telegram_id}: {error_message}")
            return ConversationHandler.END

async def poll_timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback function for when a poll's timer runs out."""
    job = context.job
    if job.removed:
        return

    # Check if the quiz session is still active
    if 'current_quiz_session_id' not in context.user_data:
        logger.info(f"Poll timed out for job {job.name}, but quiz session has already ended. Ignoring.")
        return

    session_id = job.data['session_id']
    question_id = job.data['question_id']
    chat_id = job.chat_id
    user_id = job.user_id

    await context.bot.send_message(chat_id=chat_id, text="Time's up!")
    context.user_data.pop('current_poll_id', None) # Clear poll ID as it timed out.
    context.user_data.pop('current_poll_message_id', None) # Clear poll message ID as it timed out.
    with get_db() as db:
        skipped_question = quiz_service.skip_question(db, session_id, question_id)
        if skipped_question:
            if skipped_question.explanation_image_url:
                await context.bot.send_photo(chat_id=chat_id, photo=skipped_question.explanation_image_url, caption="Here is the explanation for the skipped question:")
            elif skipped_question.explanation:
                await context.bot.send_message(chat_id=chat_id, text=f"Explanation:\n{skipped_question.explanation}")
            await asyncio.sleep(3)
    
    await ask_question(context, chat_id, user_id)

async def ask_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> int:
    with get_db() as db:
        session_id = context.user_data['current_quiz_session_id']
        session = quiz_service.get_quiz_results(db, session_id)

        answered_count = db.query(quiz_service.QuizSessionQuestion).filter(
            quiz_service.QuizSessionQuestion.session_id == session_id,
            quiz_service.QuizSessionQuestion.is_answered == True
        ).count()
        current_q_number = answered_count + 1

        question = quiz_service.get_next_question_for_session(db, session_id, context.user_data.get('reported_in_session', []))
        if question:
            logger.info(f"Asking question_id: {question.id}")
            context.user_data['current_question_id'] = question.id
            context.user_data['current_poll_answered'] = False # Reset flag
            
            keyboard = [
                [InlineKeyboardButton("Skip Question", callback_data="skip_question"), InlineKeyboardButton("Stop Quiz & See Score", callback_data="stop_quiz")],
                [InlineKeyboardButton("🚨 Report Issue", callback_data=f"report_{question.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(chat_id=chat_id, text=f"Question {current_q_number} of {session.total_questions}")

            if question.image_url:
                await context.bot.send_photo(chat_id=chat_id, photo=question.image_url, reply_markup=reply_markup)
            else:
                options_text = "\n".join([f"{chr(ord('A') + i)}.) {opt}" for i, opt in enumerate(question.options.values())])
                await context.bot.send_message(chat_id=chat_id, text=f"{question.question_text}\n\n{options_text}", reply_markup=reply_markup)

            time_limit = scoring_service.calculate_question_time_limit(question.difficulty_score)

            db_options = list(question.options.values())
            poll_options = [chr(ord('A') + i) for i in range(len(db_options))]
            
            try:
                # First, try to treat the answer as an integer index.
                correct_option_id = int(question.correct_answer)
            except ValueError:
                # If that fails, assume it's a string and find its index.
                try:
                    correct_answer_text = question.correct_answer
                    correct_option_id = db_options.index(correct_answer_text)
                except ValueError:
                    # If the text is not in the options, the question is flawed.
                    logger.error(f"Correct answer text '{question.correct_answer}' not found in options for question {question.id}")
                    await context.bot.send_message(chat_id=chat_id, text="Sorry, there was an error with this question's data. Skipping.")
                    quiz_service.skip_question(db, session_id, question.id)
                    return await ask_question(context, chat_id, user_id)

            # Final check to ensure the index is valid.
            if not 0 <= correct_option_id < len(poll_options):
                logger.error(f"Correct answer index {correct_option_id} is out of bounds for question {question.id}")
                await context.bot.send_message(chat_id=chat_id, text="Sorry, there was an error with this question's data. Skipping.")
                quiz_service.skip_question(db, session_id, question.id)
                return await ask_question(context)

            context.user_data['question_start_time'] = time.time()

            message = await context.bot.send_poll(
                chat_id=chat_id,
                question="Select the correct option:",
                options=poll_options,
                is_anonymous=False,
                type='quiz',
                correct_option_id=correct_option_id,
                open_period=time_limit
            )
            context.user_data['current_poll_id'] = message.poll.id
            context.user_data['current_poll_message_id'] = message.message_id

            context.job_queue.run_once(
                poll_timeout_callback, 
                time_limit + 2, 
                chat_id=chat_id,
                user_id=user_id,
                name=f"poll_timeout_{message.poll.id}",
                data={'session_id': session_id, 'question_id': question.id}
            )
            return IN_QUIZ
        else:
            # All questions are answered, complete the session to calculate score
            quiz_service.complete_quiz_session(db, session_id)
            results = quiz_service.get_quiz_results(db, session_id)
            
            score_msg = ""
            if results and results.final_score is not None:
                percentage = results.final_score
                if percentage == 100:
                    score_msg = "🎉 Perfect score! You aced it! Keep up the excellent work! 🎉"
                elif percentage >= 75:
                    score_msg = "🌟 Great job! You're doing really well. Keep practicing to master it! 🌟"
                elif percentage >= 50:
                    score_msg = "👍 Good effort! There's room for improvement, but you're on your way. Keep learning! 👍"
                else:
                    score_msg = "💪 You're making progress! Don't worry, every mistake is a step forward. Let's review and try again! 💪"
                score_msg = f"Quiz finished! 🏁\n\nYour score: {results.final_score:.0f}%\n{score_msg}"
            else:
                score_msg = "Quiz finished! You've completed all available questions, but your score could not be calculated."
            
            await context.bot.send_message(chat_id=chat_id, text=score_msg)
            logger.info("No more questions. Ending conversation.")
            return ConversationHandler.END

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll_answer = update.poll_answer
    context.user_data['user_id'] = poll_answer.user.id
    
    jobs = context.job_queue.get_jobs_by_name(f"poll_timeout_{poll_answer.poll_id}")
    for job in jobs:
        job.schedule_removal()

    context.user_data.pop('current_poll_id', None) # Clear poll ID as it's been answered.
    context.user_data.pop('current_poll_message_id', None) # Clear poll message ID as it's been answered.

    start_time = context.user_data.get('question_start_time', time.time())
    time_taken = int(time.time() - start_time)
    
    chosen_option_id = poll_answer.option_ids[0]
    
    session_id = context.user_data['current_quiz_session_id']
    question_id = context.user_data['current_question_id']

    with get_db() as db:
        question = db.query(quiz_service.Question).filter_by(id=question_id).first()
        chosen_option_str = list(question.options.values())[chosen_option_id]
        is_correct = quiz_service.submit_answer(db, session_id, question_id, chosen_option_str, time_taken)
        
        if question:
            correct_answer_text = question.correct_answer
            result_text = "Correct!" if is_correct else f"Sorry, the correct answer was {correct_answer_text}."
            await context.bot.send_message(chat_id=context.user_data['chat_id'], text=result_text)
            if question.explanation_image_url:
                await context.bot.send_photo(chat_id=context.user_data['chat_id'], photo=question.explanation_image_url, caption="Here is the explanation:")
            elif question.explanation:
                await context.bot.send_message(chat_id=context.user_data['chat_id'], text=f"Explanation:\n{question.explanation}")
            await asyncio.sleep(3)

    return await ask_question(context, context.user_data['chat_id'], context.user_data['user_id'])

async def skip_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['user_id'] = update.effective_user.id
    
    poll_id = context.user_data.get('current_poll_id')
    if poll_id:
        jobs = context.job_queue.get_jobs_by_name(f"poll_timeout_{poll_id}")
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Removed timeout job for poll {poll_id} due to skip.")
        # Explicitly stop the poll message, handling cases where it might already be closed
        try:
            await context.bot.stop_poll(chat_id=query.message.chat_id, message_id=context.user_data.get('current_poll_message_id'))
        except Exception as e:
            logger.warning(f"Could not stop poll {poll_id} (might already be closed): {e}")
        context.user_data.pop('current_poll_id', None) # Clear poll ID after attempting to stop
        context.user_data.pop('current_poll_message_id', None) # Clear poll message ID


    session_id = context.user_data['current_quiz_session_id']
    question_id = context.user_data['current_question_id']
    with get_db() as db:
        skipped_question = quiz_service.skip_question(db, session_id, question_id)
        if skipped_question:
            await context.bot.send_message(chat_id=context.user_data['chat_id'], text="Question skipped. The correct answer and explanation are below.")
            if skipped_question.explanation_image_url:
                await context.bot.send_photo(chat_id=context.user_data['chat_id'], photo=skipped_question.explanation_image_url)
            elif skipped_question.explanation:
                await context.bot.send_message(chat_id=context.user_data['chat_id'], text=f"Explanation:\n{skipped_question.explanation}")
            await asyncio.sleep(3)
        else:
            await context.bot.send_message(chat_id=context.user_data['chat_id'], text="Could not skip question, already answered. Moving to the next one.")
    return await ask_question(context, context.user_data['chat_id'], context.user_data['user_id'])

async def stop_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    poll_id = context.user_data.get('current_poll_id')
    if poll_id:
        jobs = context.job_queue.get_jobs_by_name(f"poll_timeout_{poll_id}")
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Removed timeout job for poll {poll_id} due to quiz stop.")
        # Explicitly stop the poll message, handling cases where it might already be closed
        try:
            await context.bot.stop_poll(chat_id=query.message.chat_id, message_id=context.user_data.get('current_poll_message_id'))
        except Exception as e:
            logger.warning(f"Could not stop poll {poll_id} (might already be closed): {e}")
        context.user_data.pop('current_poll_id', None) # Clear poll ID after attempting to stop
        context.user_data.pop('current_poll_message_id', None) # Clear poll message ID


    session_id = context.user_data['current_quiz_session_id']
    with get_db() as db:
        correct_answers, answered_count = quiz_service.end_quiz_early(db, session_id)

    if answered_count > 0:
        percentage = (correct_answers / answered_count) * 100
        if percentage == 100:
            score_msg = "🎉 Perfect score on answered questions! You aced them! 🎉"
        elif percentage >= 75:
            score_msg = "🌟 Great job on the questions you answered! Keep up the good work! 🌟"
        elif percentage >= 50:
            score_msg = "👍 Good effort on the questions you answered! Keep learning! 👍"
        else:
            score_msg = "💪 You're making progress! Don't worry, every mistake is a step forward. 💪"
        score_msg = f"Quiz stopped. The last question was not graded.\n\nYour score: {correct_answers}/{answered_count} ({percentage:.0f}%)\n{score_msg}"
    else:
        score_msg = "Quiz stopped. No questions were answered."
    await context.bot.send_message(chat_id=context.user_data['chat_id'], text=score_msg)
    logger.info(f"User stopped quiz session {session_id}. Ending conversation.")
    context.user_data.clear() # Clear all user data for this conversation
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation and any active quiz session."""
    chat_id = update.effective_chat.id
    session_id = context.user_data.get('current_quiz_session_id')

    if session_id:
        with get_db() as db:
            quiz_service.cancel_quiz_session(db, session_id)
        logger.info(f"User {update.effective_user.id} cancelled quiz session {session_id}.")
        # Clear session-related data
        context.user_data.pop('current_quiz_session_id', None)
        context.user_data.pop('current_question_id', None)

        message = 'Quiz cancelled. You can start a new one with /quiz.'
    else:
        message = "There is nothing to cancel."

    context.user_data.pop('in_quiz_setup', None) # Clear the setup flag
    logger.warning(f"User {update.effective_user.id} cancelled the conversation.")
    
    poll_id = context.user_data.get('current_poll_id')
    if poll_id:
        jobs = context.job_queue.get_jobs_by_name(f"poll_timeout_{poll_id}")
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Removed timeout job for poll {poll_id} due to cancel command.")
        context.user_data.pop('current_poll_id', None)
        context.user_data.pop('current_poll_message_id', None)

    await update.message.reply_text(message)
    return ConversationHandler.END

async def report_issue_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_id = int(query.data.split('_')[1])
    context.user_data['reported_question_id'] = question_id

    with get_db() as db:
        question = db.query(quiz_service.Question).filter_by(id=question_id).first()
        if not question:
            await query.edit_message_text("Sorry, I couldn't find that question.")
            return IN_QUIZ # Stay in quiz state

        # Determine reporting options based on has_latex
        if question.has_latex:
            report_options = [
                ["Incorrect Answer", "reason_incorrect_answer"],
                ["Typo in Text", "reason_typo_text"],
                ["Equation Not Rendering", "reason_equation_rendering"],
                ["Other", "reason_other"]
            ]
        else:
            report_options = [
                ["Incorrect Answer", "reason_incorrect_answer"],
                ["Typo in Text", "reason_typo_text"],
                ["Confusing Wording", "reason_confusing_wording"],
                ["Other", "reason_other"]
            ]

        keyboard = [[InlineKeyboardButton(text, callback_data=data)] for text, data in report_options]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text="What is the issue with this question?",
            reply_markup=reply_markup
        )
    return AWAITING_REPORT_REASON

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    report_reason = query.data.split('_', 1)[1]  # Split only on first underscore
    question_id = context.user_data.get('reported_question_id')
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.full_name

    if not question_id:
        await query.edit_message_text("Error: Could not find question to report.")
        return IN_QUIZ

    # Stop the poll for the reported question
    poll_id = context.user_data.get('current_poll_id')
    if poll_id:
        jobs = context.job_queue.get_jobs_by_name(f"poll_timeout_{poll_id}")
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Removed timeout job for poll {poll_id} due to report.")
        try:
            await context.bot.stop_poll(chat_id=query.message.chat_id, message_id=context.user_data.get('current_poll_message_id'))
        except Exception as e:
            logger.warning(f"Could not stop poll {poll_id} (might already be closed): {e}")
        context.user_data.pop('current_poll_id', None)
        context.user_data.pop('current_poll_message_id', None)

    with get_db() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            logger.error(f"User with telegram_id {user_id} not found in DB during report submission.")
            await query.edit_message_text("Sorry, your user account could not be found. Please try starting a new quiz.")
            return ConversationHandler.END

        question = db.query(Question).filter_by(id=question_id).first()
        if not question:
            await query.edit_message_text("Sorry, an error occurred while fetching report details.")
            return IN_QUIZ

        try:
            # Create a Feedback object instead of a QuestionReport
            feedback = Feedback(
                user_id=user.id,
                question_id=question_id,
                feedback_type='question_report',
                text_content=report_reason,
                status='open'
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            # Mark the question as reported in the session
            db.query(QuizSessionQuestion).filter_by(
                session_id=context.user_data['current_quiz_session_id'],
                question_id=question_id
            ).update({'is_reported': True})
            db.commit()

            # Add to reported_in_session list to skip for this quiz
            context.user_data.setdefault('reported_in_session', []).append(question_id)

            await query.edit_message_text("Thank you for your feedback! The question has been reported and will be skipped for this quiz.")

            # Send notification to admins using the existing feedback notification service
            await send_new_feedback_notification(context.bot, feedback, username)

            # Move to the next question
            return await ask_question(context, context.user_data['chat_id'], context.user_data['user_id'])
        except Exception as e:
            logger.error(f"Error submitting report for question {question_id} by user {user_id}: {e}")
            db.rollback()
            await query.edit_message_text("Sorry, an error occurred while submitting your report.")
            return IN_QUIZ

quiz_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('quiz', start_quiz)],
    states={
        CHOOSE_FACULTY: [CallbackQueryHandler(faculty_choice, pattern='^fac_')],
        CHOOSE_PROGRAM: [CallbackQueryHandler(program_choice, pattern='^prog_')],
        CHOOSE_LEVEL: [CallbackQueryHandler(level_choice, pattern='^lvl_')],
        CHOOSE_COURSE: [CallbackQueryHandler(course_choice, pattern='^course_')],
        CHOOSE_QUIZ_LENGTH: [CallbackQueryHandler(quiz_length_choice, pattern='^len_')],
        CONFIRM_PREFERENCES: [
            CallbackQueryHandler(confirm_preferences_callback, pattern='^use_previous_settings'),
            CallbackQueryHandler(confirm_preferences_callback, pattern='^choose_new_settings')
        ],
        IN_QUIZ: [
            CallbackQueryHandler(stop_quiz_callback, pattern='^stop_quiz'),
            CallbackQueryHandler(skip_question_callback, pattern='^skip_question'),
            CallbackQueryHandler(report_issue_start, pattern='^report_'), # New entry point for reporting
            PollAnswerHandler(handle_poll_answer)
        ],
        AWAITING_REPORT_REASON: [
            CallbackQueryHandler(submit_report, pattern='^reason_')
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_chat=False,
    per_user=True,
    per_message=False
)
