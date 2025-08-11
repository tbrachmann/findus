"""
Services for the chat application.

This module contains service classes and helper functions for:
- Generating personalized learning prompts based on user levels and weaknesses
- Managing user profiles and expertise analysis
- Creating engaging scenarios for language practice
"""

import logging
import random
from typing import Dict, List, Any, Optional, Tuple, Union

from django.contrib.auth.models import User
from django.db.models import Count

from chat.models import UserProfile, AfterActionReport, Conversation

# Configure logging
logger = logging.getLogger(__name__)


def get_or_create_user_profile(user: User) -> UserProfile:
    """
    Get an existing user profile or create a new one if it doesn't exist.
    
    Args:
        user: The Django User object
        
    Returns:
        The UserProfile instance for the user
    """
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "level": UserProfile.Level.BEGINNER,
            "weaknesses": {},
        }
    )
    
    if created:
        logger.info(f"Created new profile for user {user.username}")
    
    return profile


def analyze_user_expertise(user: User) -> Dict[str, Any]:
    """
    Analyze a user's expertise based on conversation history.
    
    This function examines conversation patterns, message complexity,
    and after action reports to build a comprehensive profile of the
    user's language abilities.
    
    Args:
        user: The Django User object
        
    Returns:
        Dictionary with expertise metrics
    """
    # Get user's conversations
    conversations = Conversation.objects.filter(user=user)
    
    # Count total messages
    message_count = sum(c.messages.count() for c in conversations)
    
    # Get report count
    report_count = AfterActionReport.objects.filter(conversation__user=user).count()
    
    # Calculate average message length (as a simple complexity metric)
    avg_message_length = 0
    if message_count > 0:
        total_length = 0
        message_count = 0
        for conv in conversations:
            for msg in conv.messages.all():
                total_length += len(msg.message)
                message_count += 1
        
        if message_count > 0:
            avg_message_length = total_length / message_count
    
    return {
        "conversation_count": conversations.count(),
        "message_count": message_count,
        "report_count": report_count,
        "avg_message_length": avg_message_length,
    }


class PromptGeneratorService:
    """
    Service for generating personalized language learning prompts.
    
    This service creates engaging scenarios tailored to a user's language level
    and specific weaknesses identified in their after action reports.
    """
    
    # Prompt templates organized by level and category
    PROMPT_TEMPLATES = {
        UserProfile.Level.BEGINNER: {
            "daily_routine": [
                "Imagine you're describing your morning routine to a friend. What time do you wake up? What do you eat for breakfast?",
                "You're meeting a new roommate. Introduce yourself and ask about their daily schedule.",
                "You're at a café ordering breakfast. Ask the server about the menu options and place your order."
            ],
            "directions": [
                "You're lost in a new city. Ask a local for directions to the nearest subway station.",
                "Your friend is visiting your neighborhood. Give them directions from the bus stop to your home.",
                "You're at a hotel and need to find the restaurant. Ask the receptionist for directions."
            ],
            "shopping": [
                "You're at a clothing store and need help finding a specific item. Ask a shop assistant for help.",
                "You're buying groceries and can't find an ingredient for your recipe. Ask someone where to find it.",
                "You're at a market and want to buy some fruit. Ask about the prices and freshness."
            ],
            "grammar_practice": {
                "past_tense": "Write about what you did last weekend. Include at least 5 activities.",
                "present_continuous": "Describe what people are doing in a busy park right now.",
                "articles": "Describe the items you can see on your desk or table, using appropriate articles (a, an, the)."
            }
        },
        
        UserProfile.Level.INTERMEDIATE: {
            "hypothetical_scenarios": [
                "If you could travel anywhere in the world for a month, where would you go and why?",
                "Imagine you've been given $10,000 to start a small business. What would you create?",
                "If you could have dinner with any historical figure, who would you choose and what would you ask them?"
            ],
            "debates": [
                "Do you think remote work should continue to be the norm after the pandemic? Explain your reasoning.",
                "Is social media having a positive or negative impact on society? Defend your position.",
                "Should public transportation be free in major cities? Present arguments for or against."
            ],
            "storytelling": [
                "Continue this story: 'The train was late, and as Sarah waited on the platform, she noticed something unusual...'",
                "Write a short story that includes these elements: an old key, a mysterious letter, and a surprise encounter.",
                "Describe a childhood memory that had a significant impact on who you are today."
            ],
            "grammar_practice": {
                "conditionals": "Write three sentences using different conditional structures (first, second, and third conditionals).",
                "reported_speech": "Transform this conversation into reported speech: Tom: 'I'll meet you tomorrow.' Lisa: 'Where should we go?'",
                "passive_voice": "Rewrite these active sentences in passive voice: 'The chef prepares the meals. The waiter serves the customers.'"
            }
        },
        
        UserProfile.Level.ADVANCED: {
            "complex_discussions": [
                "Discuss the ethical implications of artificial intelligence in healthcare. Consider both benefits and potential risks.",
                "How might climate change affect global migration patterns in the next 50 years? What policies could help address these challenges?",
                "Analyze how cultural identity is shaped by language, and how language evolution reflects societal changes."
            ],
            "literary_analysis": [
                "Choose a book or film that explores themes of identity or belonging. Analyze how these themes are developed.",
                "Compare and contrast two literary or artistic movements and their impact on contemporary culture.",
                "Discuss how an author's background and historical context influence their work, using specific examples."
            ],
            "persuasive_arguments": [
                "Make a compelling argument for or against the implementation of universal basic income.",
                "Should governments regulate social media platforms? Present a nuanced perspective with supporting evidence.",
                "Argue for the importance of arts education in an increasingly STEM-focused educational system."
            ],
            "grammar_practice": {
                "subjunctive_mood": "Write sentences using the subjunctive mood to express wishes, suggestions, and hypothetical situations.",
                "complex_structures": "Combine these simple sentences into complex sentences using appropriate conjunctions and relative clauses.",
                "nuanced_vocabulary": "Rewrite this paragraph using more precise and sophisticated vocabulary: 'The movie was good. The actors did a good job. The story was interesting.'"
            }
        }
    }
    
    # Specific prompts targeting common weaknesses
    WEAKNESS_TARGETED_PROMPTS = {
        "verb_tenses": [
            "Tell a story about your childhood, focusing on using past tenses correctly.",
            "Describe your plans for next year, using future tenses appropriately.",
            "Explain what you have accomplished so far this week, using present perfect tense."
        ],
        "articles": [
            "Describe a visit to a museum, paying attention to article usage (a, an, the).",
            "Write directions to a famous landmark in your city, using articles correctly.",
            "Compare the education system in your country with another country, focusing on article usage."
        ],
        "prepositions": [
            "Explain how to get from your home to your workplace/school, using prepositions of place.",
            "Describe your daily routine with particular attention to time prepositions.",
            "Write about a memorable trip, focusing on movement prepositions."
        ],
        "word_order": [
            "Form questions about a partner's weekend activities.",
            "Rewrite these scrambled sentences in the correct order.",
            "Create complex sentences by combining these simple statements."
        ],
        "vocabulary_range": [
            "Describe your feelings about a recent event using precise emotion words.",
            "Explain a process or hobby using specialized terminology.",
            "Rewrite this basic paragraph using more sophisticated vocabulary."
        ]
    }
    
    @classmethod
    def generate_prompt(cls, user: User) -> Dict[str, Any]:
        """
        Generate a personalized learning prompt based on user level and weaknesses.
        
        Args:
            user: The Django User object
            
        Returns:
            Dictionary containing the prompt scenario, instructions, and metadata
        """
        # Get user profile
        profile = get_or_create_user_profile(user)
        
        # Determine user level
        level = profile.level
        
        # Get user weaknesses
        weaknesses = profile.weaknesses or {}
        
        # Select prompt type based on weaknesses and level
        if weaknesses and random.random() < 0.7:  # 70% chance to target a specific weakness
            # Select a random weakness to target
            weakness_keys = list(weaknesses.keys())
            if not weakness_keys:
                return cls._generate_general_prompt(level)
                
            target_weakness = random.choice(weakness_keys)
            
            # Check if we have specific prompts for this weakness
            if target_weakness in cls.WEAKNESS_TARGETED_PROMPTS:
                prompt_text = random.choice(cls.WEAKNESS_TARGETED_PROMPTS[target_weakness])
                
                # Get the weakness details
                weakness_details = weaknesses.get(target_weakness, {})
                practice_suggestion = weakness_details.get("practice_suggestion", "")
                
                return {
                    "prompt": prompt_text,
                    "instructions": f"This exercise helps with: {target_weakness}. {practice_suggestion}",
                    "level": level,
                    "targeted_weakness": target_weakness,
                    "is_targeted": True
                }
            
        # Default to general prompt if no weakness targeted
        return cls._generate_general_prompt(level)
    
    @classmethod
    def _generate_general_prompt(cls, level: str) -> Dict[str, Any]:
        """
        Generate a general prompt appropriate for the user's level.
        
        Args:
            level: The user's proficiency level
            
        Returns:
            Dictionary containing the prompt scenario and metadata
        """
        # Get templates for this level
        level_templates = cls.PROMPT_TEMPLATES.get(level, cls.PROMPT_TEMPLATES[UserProfile.Level.BEGINNER])
        
        # Select a random category
        category = random.choice(list(level_templates.keys()))
        
        # Get prompts for this category
        category_prompts = level_templates[category]
        
        # Handle different data structures (list vs dict)
        if isinstance(category_prompts, list):
            prompt_text = random.choice(category_prompts)
            instructions = f"Practice your {level.lower()} level {category.replace('_', ' ')} skills."
        else:
            # For grammar_practice which is a dict
            subcategory = random.choice(list(category_prompts.keys()))
            prompt_text = category_prompts[subcategory]
            instructions = f"Grammar practice: {subcategory.replace('_', ' ')}."
        
        return {
            "prompt": prompt_text,
            "instructions": instructions,
            "level": level,
            "category": category,
            "is_targeted": False
        }
    
    @classmethod
    def generate_conversation_starter(cls, user: User) -> str:
        """
        Generate a simple conversation starter based on user level.
        
        This is a lightweight version of generate_prompt that returns just
        the prompt text for starting a new conversation.
        
        Args:
            user: The Django User object
            
        Returns:
            String with conversation starter prompt
        """
        prompt_data = cls.generate_prompt(user)
        return prompt_data["prompt"]
    
    @classmethod
    def generate_scenario_prompt(cls, user: User) -> Dict[str, Any]:
        """
        Generate an immersive scenario prompt with roleplay elements.
        
        Creates a more elaborate prompt with character roles and a
        specific scenario for the user to engage with.
        
        Args:
            user: The Django User object
            
        Returns:
            Dictionary with scenario details, roles, and context
        """
        # Get user profile and level
        profile = get_or_create_user_profile(user)
        level = profile.level
        
        # Scenario templates by level
        scenarios = {
            UserProfile.Level.BEGINNER: [
                {
                    "title": "At the Restaurant",
                    "context": "You're at a restaurant and need to order food.",
                    "your_role": "Customer who has dietary restrictions",
                    "ai_role": "Waiter who is helping you order",
                    "goal": "Successfully order a meal that meets your dietary needs"
                },
                {
                    "title": "Lost in the City",
                    "context": "You're a tourist who is lost in a new city.",
                    "your_role": "Tourist with a map but confused about directions",
                    "ai_role": "Helpful local resident",
                    "goal": "Get directions to your hotel from your current location"
                }
            ],
            UserProfile.Level.INTERMEDIATE: [
                {
                    "title": "Job Interview",
                    "context": "You're interviewing for your dream job.",
                    "your_role": "Job applicant with relevant experience",
                    "ai_role": "Hiring manager asking about your qualifications",
                    "goal": "Convince the interviewer you're the right person for the position"
                },
                {
                    "title": "Planning a Trip",
                    "context": "You're planning a vacation with a friend who has different interests.",
                    "your_role": "Traveler who loves adventure and outdoor activities",
                    "ai_role": "Friend who prefers cultural sites and relaxation",
                    "goal": "Create an itinerary that satisfies both of your interests"
                }
            ],
            UserProfile.Level.ADVANCED: [
                {
                    "title": "Business Negotiation",
                    "context": "You're negotiating a business deal with international partners.",
                    "your_role": "Company representative seeking favorable terms",
                    "ai_role": "Business partner with different priorities",
                    "goal": "Reach a mutually beneficial agreement while addressing cultural differences"
                },
                {
                    "title": "Academic Debate",
                    "context": "You're participating in an academic panel discussion.",
                    "your_role": "Expert presenting a controversial theory in your field",
                    "ai_role": "Colleague with an opposing viewpoint",
                    "goal": "Defend your position with evidence while engaging constructively with criticism"
                }
            ]
        }
        
        # Select appropriate scenarios for user level
        level_scenarios = scenarios.get(level, scenarios[UserProfile.Level.BEGINNER])
        selected_scenario = random.choice(level_scenarios)
        
        # Add level info to the scenario
        selected_scenario["level"] = level
        
        return selected_scenario
