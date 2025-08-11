"""
Management command to analyze user after action reports and infer language skill levels.

This command:
1. Finds users with at least 2 after action reports
2. Uses Google Gemini AI to analyze reports and determine skill level
3. Extracts common weaknesses for personalized prompting
4. Updates or creates UserProfile objects with this information

Usage:
    python manage.py infer_user_levels
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Optional

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from chat.models import AfterActionReport, UserProfile

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to infer user language skill levels from after action reports."""

    help = "Analyzes users' after action reports to infer language skill levels"

    def __init__(self, *args, **kwargs):
        """Initialize the command and configure Google Gemini AI client."""
        super().__init__(*args, **kwargs)
        
        # Configure the Gemini model with the same settings as the chat system
        genai.configure(api_key=self._get_gemini_api_key())
        
        # Safety settings to match the chat application
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            safety_settings=self.safety_settings,
        )

    def _get_gemini_api_key(self) -> str:
        """
        Get the Gemini API key from environment variables.
        
        In a real application, this would use the same configuration
        mechanism as the chat system.
        """
        import os
        from django.conf import settings
        
        # Try to get API key from settings or environment
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Gemini API key not found. Set GEMINI_API_KEY in settings or environment."
            )
        
        return api_key

    def handle(self, *args, **options):
        """
        Main command execution logic.
        
        Finds users with 2+ reports, analyzes them with Gemini AI,
        and updates their profiles with inferred levels and weaknesses.
        """
        # Find users with at least 2 after action reports
        eligible_users = self._get_eligible_users()
        
        if not eligible_users:
            self.stdout.write(self.style.WARNING("No eligible users found with 2+ after action reports"))
            return
        
        self.stdout.write(f"Found {len(eligible_users)} eligible users for level inference")
        
        # Process each eligible user
        for user in eligible_users:
            try:
                self.stdout.write(f"Processing user: {user.username}")
                
                # Get the user's after action reports
                reports = self._get_user_reports(user)
                
                # Analyze reports with Gemini AI
                level, weaknesses = self._analyze_reports_with_ai(user, reports)
                
                # Update or create user profile
                self._update_user_profile(user, level, weaknesses)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated {user.username}'s profile: Level={level}, "
                        f"Weaknesses={json.dumps(weaknesses, indent=2)}"
                    )
                )
            except Exception as e:
                logger.error(f"Error processing user {user.username}: {str(e)}")
                self.stdout.write(
                    self.style.ERROR(f"Error processing user {user.username}: {str(e)}")
                )

    def _get_eligible_users(self) -> List[User]:
        """
        Find users who have at least 2 after action reports.
        
        Returns:
            List of User objects who qualify for level inference
        """
        # Query users with a count of their reports
        user_report_counts = User.objects.annotate(
            report_count=Count('conversations__reports')
        ).filter(report_count__gte=2)
        
        return list(user_report_counts)

    def _get_user_reports(self, user: User) -> List[AfterActionReport]:
        """
        Get all after action reports for a specific user.
        
        Args:
            user: The User object to get reports for
            
        Returns:
            List of AfterActionReport objects for the user
        """
        # Get reports from all user conversations, ordered by creation date
        reports = AfterActionReport.objects.filter(
            conversation__user=user
        ).order_by('-created_at')
        
        return list(reports)

    def _analyze_reports_with_ai(
        self, user: User, reports: List[AfterActionReport]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Use Google Gemini to analyze reports and determine user level.
        
        Args:
            user: The User being analyzed
            reports: List of AfterActionReport objects
            
        Returns:
            Tuple of (inferred_level, weaknesses_dict)
        """
        # Extract report content for analysis
        report_texts = [report.analysis_content for report in reports]
        
        # Create a prompt for Gemini
        prompt = self._create_analysis_prompt(user.username, report_texts)
        
        # Generate analysis with Gemini
        response = self.model.generate_content(prompt)
        
        # Parse the response to extract level and weaknesses
        try:
            analysis = json.loads(response.text)
            level = analysis.get("level", UserProfile.Level.BEGINNER)
            weaknesses = analysis.get("weaknesses", {})
            
            # Validate the level is one of our defined choices
            if level not in [choice[0] for choice in UserProfile.Level.choices]:
                logger.warning(f"Invalid level '{level}' returned by AI, defaulting to BEGINNER")
                level = UserProfile.Level.BEGINNER
                
            return level, weaknesses
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            logger.debug(f"Raw AI response: {response.text}")
            # Default values if parsing fails
            return UserProfile.Level.BEGINNER, {"parsing_error": True}

    def _create_analysis_prompt(self, username: str, report_texts: List[str]) -> str:
        """
        Create the prompt for Gemini AI to analyze user reports.
        
        Args:
            username: The user's username
            report_texts: List of after action report content strings
            
        Returns:
            Formatted prompt string for Gemini
        """
        reports_combined = "\n\n--- REPORT SEPARATOR ---\n\n".join(report_texts)
        
        prompt = f"""
        You are an expert language learning analyst. Analyze the following after-action 
        reports for user '{username}' and determine their language skill level.
        
        The reports contain AI-generated analyses of the user's language patterns,
        grammar issues, and areas for improvement.
        
        --- AFTER ACTION REPORTS ---
        
        {reports_combined}
        
        --- END OF REPORTS ---
        
        Based on these reports, please:
        
        1. Determine the user's language skill level as one of: BEGINNER, INTERMEDIATE, or ADVANCED
        2. Identify 3-5 specific weaknesses or areas for improvement
        3. For each weakness, suggest a specific type of practice that would help
        
        Return your analysis in JSON format like this:
        {{
            "level": "BEGINNER|INTERMEDIATE|ADVANCED",
            "weaknesses": {{
                "weakness1": {{
                    "description": "Brief description of the issue",
                    "examples": ["Example from reports", "Another example"],
                    "practice_suggestion": "Specific practice idea"
                }},
                "weakness2": {{
                    "description": "Brief description of the issue",
                    "examples": ["Example from reports"],
                    "practice_suggestion": "Specific practice idea"
                }}
            }}
        }}
        
        Your response must be valid JSON with no additional text before or after.
        """
        
        return prompt

    def _update_user_profile(self, user: User, level: str, weaknesses: Dict[str, Any]) -> None:
        """
        Update or create a UserProfile with the inferred level and weaknesses.
        
        Args:
            user: The User to update
            level: The inferred language skill level
            weaknesses: Dictionary of weaknesses and practice suggestions
        """
        # Get or create the user's profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update the profile with new information
        profile.level = level
        profile.weaknesses = weaknesses
        profile.save()
        
        if created:
            logger.info(f"Created new profile for {user.username} with level {level}")
        else:
            logger.info(f"Updated existing profile for {user.username} to level {level}")
