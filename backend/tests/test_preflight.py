# import unittest
import unittest

# from app.safety.preflight import PreflightChecker
from app.safety.preflight import PreflightChecker


# class PreflightCheckerTests(unittest.IsolatedAsyncioTestCase):
class PreflightCheckerTests(unittest.IsolatedAsyncioTestCase):
    # def setUp(self) -> None:
    def setUp(self) -> None:
        # self.checker = PreflightChecker()
        self.checker = PreflightChecker()

    # async def test_crisis_patterns_trigger_for_30_cases(self):
    async def test_crisis_patterns_trigger_for_30_cases(self):
        # crisis_cases = [
        crisis_cases = [
            # "I have chest pain right now",
            "I have chest pain right now",
            # "I can't breathe",
            "I can't breathe",
            # "I cannot breathe well",
            "I cannot breathe well",
            # "I feel suicidal",
            "I feel suicidal",
            # "I want to kill myself",
            "I want to kill myself",
            # "I think this is a heart attack",
            "I think this is a heart attack",
            # "Could this be a stroke",
            "Could this be a stroke",
            # "This is severe pain",
            "This is severe pain",
            # "This is an emergency",
            "This is an emergency",
            # "Should I call 911",
            "Should I call 911",
            # "I took an overdose",
            "I took an overdose",
            # "They are unconscious",
            "They are unconscious",
            # "There is a lot of bleeding",
            "There is a lot of bleeding",
            # "I am passing out",
            "I am passing out",
            # "I fainted again",
            "I fainted again",
            # "My chest-pain started suddenly",
            "My chest-pain started suddenly",
            # "I cant breathe lying down",
            "I cant breathe lying down",
            # "He is unconscious on the floor",
            "He is unconscious on the floor",
            # "This feels like heart attack symptoms",
            "This feels like heart attack symptoms",
            # "I am suicidal tonight",
            "I am suicidal tonight",
            # "I might overdose on these pills",
            "I might overdose on these pills",
            # "She said call 911 now",
            "She said call 911 now",
            # "He may be having a stroke",
            "He may be having a stroke",
            # "I have severe pain in my abdomen",
            "I have severe pain in my abdomen",
            # "This sounds like an emergency to me",
            "This sounds like an emergency to me",
            # "There is severe chest pain",
            "There is severe chest pain",
            # "I cannot breathe and feel dizzy",
            "I cannot breathe and feel dizzy",
            # "I feel like I will pass out",
            "I feel like I will pass out",
            # "I have bleeding a lot after surgery",
            "I have bleeding a lot after surgery",
            # "He fainted and is unconscious",
            "He fainted and is unconscious",
        # ]
        ]
        # for phrase in crisis_cases:
        for phrase in crisis_cases:
            # with self.subTest(phrase=phrase):
            with self.subTest(phrase=phrase):
                # result = await self.checker.preflight_check(phrase)
                result = await self.checker.preflight_check(phrase)
                # self.assertTrue(result.escalate)
                self.assertTrue(result.escalate)
                # self.assertEqual(result.message_key, "crisis_escalation")
                self.assertEqual(result.message_key, "crisis_escalation")

    # async def test_false_positives_do_not_trigger_for_20_cases(self):
    async def test_false_positives_do_not_trigger_for_20_cases(self):
        # safe_cases = [
        safe_cases = [
            # "My dad had a stroke years ago.",
            "My dad had a stroke years ago.",
            # "I read an article about suicide prevention.",
            "I read an article about suicide prevention.",
            # "Can you explain what chest pain means in general?",
            "Can you explain what chest pain means in general?",
            # "I was told to call 911 only in emergencies.",
            "I was told to call 911 only in emergencies.",
            # "This clinic helps overdose survivors.",
            "This clinic helps overdose survivors.",
            # "I cannot breathe through my nose because of allergies.",
            "I cannot breathe through my nose because of allergies.",
            # "The movie gave me a heart attack joke.",
            "The movie gave me a heart attack joke.",
            # "I fainted in a dream I had.",
            "I fainted in a dream I had.",
            # "My pain was 5 out of 10 yesterday.",
            "My pain was 5 out of 10 yesterday.",
            # "Pain score is 6 today.",
            "Pain score is 6 today.",
            # "I want to understand my medication schedule.",
            "I want to understand my medication schedule.",
            # "Should I track symptoms in case of an emergency?",
            "Should I track symptoms in case of an emergency?",
            # "Please explain what unconscious means.",
            "Please explain what unconscious means.",
            # "My aunt had severe pain before surgery years ago.",
            "My aunt had severe pain before surgery years ago.",
            # "Can you summarize the overdose prevention leaflet?",
            "Can you summarize the overdose prevention leaflet?",
            # "What does chest pain education usually include?",
            "What does chest pain education usually include?",
            # "I skipped breakfast, not my medication.",
            "I skipped breakfast, not my medication.",
            # "I need help reading my lab result.",
            "I need help reading my lab result.",
            # "This support group talks about suicide awareness.",
            "This support group talks about suicide awareness.",
            # "My appointment was called an emergency follow-up last year.",
            "My appointment was called an emergency follow-up last year.",
        # ]
        ]
        # for phrase in safe_cases:
        for phrase in safe_cases:
            # with self.subTest(phrase=phrase):
            with self.subTest(phrase=phrase):
                # result = await self.checker.preflight_check(phrase)
                result = await self.checker.preflight_check(phrase)
                # self.assertFalse(result.escalate)
                self.assertFalse(result.escalate)

    # async def test_high_pain_score_escalates(self):
    async def test_high_pain_score_escalates(self):
        # for phrase in ["pain is 8/10", "8 out of 10", "pain score: 9"]:
        for phrase in ["pain is 8/10", "8 out of 10", "pain score: 9"]:
            # with self.subTest(phrase=phrase):
            with self.subTest(phrase=phrase):
                # result = await self.checker.preflight_check(phrase)
                result = await self.checker.preflight_check(phrase)
                # self.assertTrue(result.escalate)
                self.assertTrue(result.escalate)
                # self.assertEqual(result.message_key, "pain_escalation")
                self.assertEqual(result.message_key, "pain_escalation")

    # async def test_medication_change_request_escalates_without_bypass_flag(self):
    async def test_medication_change_request_escalates_without_bypass_flag(self):
        # result = await self.checker.preflight_check("Can I stop taking this medication")
        result = await self.checker.preflight_check("Can I stop taking this medication")
        # self.assertTrue(result.escalate)
        self.assertTrue(result.escalate)
        # self.assertFalse(result.bypass_llm)
        self.assertFalse(result.bypass_llm)
        # self.assertEqual(result.message_key, "medication_change_blocked")
        self.assertEqual(result.message_key, "medication_change_blocked")

    # async def test_specialty_specific_terms_can_trigger(self):
    async def test_specialty_specific_terms_can_trigger(self):
        # result = await self.checker.preflight_check("I have palpitations with dizziness", profile="cardiology")
        result = await self.checker.preflight_check("I have palpitations with dizziness", profile="cardiology")
        # self.assertTrue(result.escalate)
        self.assertTrue(result.escalate)
        # self.assertEqual(result.message_key, "crisis_escalation")
        self.assertEqual(result.message_key, "crisis_escalation")


# if __name__ == "__main__":
if __name__ == "__main__":
    # unittest.main()
    unittest.main()
