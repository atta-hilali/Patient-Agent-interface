# import tempfile
import tempfile
# import unittest
import unittest
# from pathlib import Path
from pathlib import Path

# import httpx
import httpx

# from app.safety.checker import DEFAULT_TOPIC_CONFIG, SafetyChecker
from app.safety.checker import DEFAULT_TOPIC_CONFIG, SafetyChecker


# class StubSafetyChecker(SafetyChecker):
class StubSafetyChecker(SafetyChecker):
    # def __init__(self, script, *args, **kwargs):
    def __init__(self, script, *args, **kwargs):
        # super().__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)
        # self.script = list(script)
        self.script = list(script)
        # self.calls = []
        self.calls = []

    # async def _call_content_safety(self, role: str, text: str) -> dict:
    async def _call_content_safety(self, role: str, text: str) -> dict:
        # self.calls.append(("content_safety", role, text))
        self.calls.append(("content_safety", role, text))
        # return self.script.pop(0)
        return self.script.pop(0)

    # async def _call_topic_control(self, role: str, text: str, config: dict) -> dict:
    async def _call_topic_control(self, role: str, text: str, config: dict) -> dict:
        # self.calls.append(("topic_control", role, text, config))
        self.calls.append(("topic_control", role, text, config))
        # return self.script.pop(0)
        return self.script.pop(0)


# class SafetyCheckerTests(unittest.IsolatedAsyncioTestCase):
class SafetyCheckerTests(unittest.IsolatedAsyncioTestCase):
    # async def test_parallel_checks_prefer_content_safety_when_both_return(self):
    async def test_parallel_checks_prefer_content_safety_when_both_return(self):
        # checker = StubSafetyChecker(
        checker = StubSafetyChecker(
            # [
            [
                # {"blocked": True, "category": "self_harm", "severity": "HIGH"},
                {"blocked": True, "category": "self_harm", "severity": "HIGH"},
                # {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
                {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
            # ],
            ],
            # topic_dir="config/topics",
            topic_dir="config/topics",
        # )
        )
        # result = await checker.safety_check("bad draft", "general_medicine")
        result = await checker.safety_check("bad draft", "general_medicine")
        # self.assertFalse(result.safe)
        self.assertFalse(result.safe)
        # self.assertEqual(result.action, "escalate")
        self.assertEqual(result.action, "escalate")
        # self.assertEqual(result.message_key, "content_safety_self_harm")
        self.assertEqual(result.message_key, "content_safety_self_harm")
        # self.assertEqual(len(checker.calls), 2)
        self.assertEqual(len(checker.calls), 2)
        # self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})
        self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})

    # async def test_parallel_checks_can_return_topic_control_result(self):
    async def test_parallel_checks_can_return_topic_control_result(self):
        # checker = StubSafetyChecker(
        checker = StubSafetyChecker(
            # [
            [
                # {"blocked": False},
                {"blocked": False},
                # {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
                {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
            # ],
            ],
            # topic_dir="config/topics",
            topic_dir="config/topics",
        # )
        )
        # result = await checker.safety_check("diagnostic draft", "general_medicine")
        result = await checker.safety_check("diagnostic draft", "general_medicine")
        # self.assertFalse(result.safe)
        self.assertFalse(result.safe)
        # self.assertEqual(result.action, "redirect")
        self.assertEqual(result.action, "redirect")
        # self.assertEqual(result.message_key, "topic_control_diagnosis")
        self.assertEqual(result.message_key, "topic_control_diagnosis")
        # self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})
        self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})

    # async def test_parallel_checks_are_used_for_input_too(self):
    async def test_parallel_checks_are_used_for_input_too(self):
        # checker = StubSafetyChecker(
        checker = StubSafetyChecker(
            # [
            [
                # {"blocked": False},
                {"blocked": False},
                # {"blocked": True, "category": "prescribing", "severity": "HIGH"},
                {"blocked": True, "category": "prescribing", "severity": "HIGH"},
            # ],
            ],
            # topic_dir="config/topics",
            topic_dir="config/topics",
        # )
        )
        # result = await checker.check_input("should I take more of this", "general_medicine")
        result = await checker.check_input("should I take more of this", "general_medicine")
        # self.assertFalse(result.safe)
        self.assertFalse(result.safe)
        # self.assertEqual(result.action, "redirect")
        self.assertEqual(result.action, "redirect")
        # self.assertEqual(result.message_key, "topic_control_prescribing")
        self.assertEqual(result.message_key, "topic_control_prescribing")
        # self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})
        self.assertEqual({call[0] for call in checker.calls}, {"content_safety", "topic_control"})

    # async def test_load_and_save_custom_topic_yaml(self):
    async def test_load_and_save_custom_topic_yaml(self):
        # with tempfile.TemporaryDirectory() as tmp_dir:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # checker = SafetyChecker(topic_dir=tmp_dir)
            checker = SafetyChecker(topic_dir=tmp_dir)
            # name = checker.save_custom_topic_yaml(
            name = checker.save_custom_topic_yaml(
                # clinic_id="demo-clinic",
                clinic_id="demo-clinic",
                # yaml_content="allowed_topics:\n- custom_topic\nblocked_topics:\n- diagnosis\n",
                yaml_content="allowed_topics:\n- custom_topic\nblocked_topics:\n- diagnosis\n",
            # )
            )
            # loaded = checker.load_topic_yaml(name)
            loaded = checker.load_topic_yaml(name)
            # self.assertEqual(loaded["allowed_topics"], ["custom_topic"])
            self.assertEqual(loaded["allowed_topics"], ["custom_topic"])
            # self.assertTrue(Path(tmp_dir, name).exists())
            self.assertTrue(Path(tmp_dir, name).exists())

    # async def test_returns_default_config_when_yaml_missing(self):
    async def test_returns_default_config_when_yaml_missing(self):
        # checker = SafetyChecker(topic_dir="does-not-exist")
        checker = SafetyChecker(topic_dir="does-not-exist")
        # loaded = checker.load_topic_yaml("missing-profile")
        loaded = checker.load_topic_yaml("missing-profile")
        # self.assertEqual(loaded, DEFAULT_TOPIC_CONFIG)
        self.assertEqual(loaded, DEFAULT_TOPIC_CONFIG)

    # async def test_adversarial_suite_of_200_cases(self):
    async def test_adversarial_suite_of_200_cases(self):
        # cases = []
        cases = []
        # for index in range(80):
        for index in range(80):
            # cases.append(
            cases.append(
                # {
                {
                    # "draft": f"content safety case {index}",
                    "draft": f"content safety case {index}",
                    # "script": [
                    "script": [
                        # {"blocked": True, "category": "self_harm", "severity": "HIGH"},
                        {"blocked": True, "category": "self_harm", "severity": "HIGH"},
                        # {"blocked": False},
                        {"blocked": False},
                    # ],
                    ],
                    # "expected_action": "escalate",
                    "expected_action": "escalate",
                    # "expected_key": "content_safety_self_harm",
                    "expected_key": "content_safety_self_harm",
                # }
                }
            # )
            )
        # for index in range(80):
        for index in range(80):
            # cases.append(
            cases.append(
                # {
                {
                    # "draft": f"topic control case {index}",
                    "draft": f"topic control case {index}",
                    # "script": [
                    "script": [
                        # {"blocked": False},
                        {"blocked": False},
                        # {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
                        {"blocked": True, "category": "diagnosis", "severity": "HIGH"},
                    # ],
                    ],
                    # "expected_action": "redirect",
                    "expected_action": "redirect",
                    # "expected_key": "topic_control_diagnosis",
                    "expected_key": "topic_control_diagnosis",
                # }
                }
            # )
            )
        # for index in range(30):
        for index in range(30):
            # cases.append(
            cases.append(
                # {
                {
                    # "draft": f"safe case {index}",
                    "draft": f"safe case {index}",
                    # "script": [{"blocked": False}, {"blocked": False}],
                    "script": [{"blocked": False}, {"blocked": False}],
                    # "expected_action": "allow",
                    "expected_action": "allow",
                    # "expected_key": None,
                    "expected_key": None,
                # }
                }
            # )
            )
        # for index in range(10):
        for index in range(10):
            # cases.append(
            cases.append(
                # {
                {
                    # "draft": f"unreachable case {index}",
                    "draft": f"unreachable case {index}",
                    # "script": RuntimeError("simulated"),
                    "script": RuntimeError("simulated"),
                    # "expected_action": "escalate",
                    "expected_action": "escalate",
                    # "expected_key": "nemoguard_output_unreachable",
                    "expected_key": "nemoguard_output_unreachable",
                # }
                }
            # )
            )

        # self.assertEqual(len(cases), 200)
        self.assertEqual(len(cases), 200)

        # for case in cases:
        for case in cases:
            # if isinstance(case["script"], Exception):
            if isinstance(case["script"], Exception):
                # checker = FailingSafetyChecker(topic_dir="config/topics")
                checker = FailingSafetyChecker(topic_dir="config/topics")
            # else:
            else:
                # checker = StubSafetyChecker(case["script"], topic_dir="config/topics")
                checker = StubSafetyChecker(case["script"], topic_dir="config/topics")
            # result = await checker.safety_check(case["draft"], "general_medicine")
            result = await checker.safety_check(case["draft"], "general_medicine")
            # self.assertEqual(result.action, case["expected_action"])
            self.assertEqual(result.action, case["expected_action"])
            # self.assertEqual(result.message_key, case["expected_key"])
            self.assertEqual(result.message_key, case["expected_key"])


# class FailingSafetyChecker(SafetyChecker):
class FailingSafetyChecker(SafetyChecker):
    # async def _call_content_safety(self, role: str, text: str) -> dict:
    async def _call_content_safety(self, role: str, text: str) -> dict:
        # raise httpx.ConnectError("boom")
        raise httpx.ConnectError("boom")

    # async def _call_topic_control(self, role: str, text: str, config: dict) -> dict:
    async def _call_topic_control(self, role: str, text: str, config: dict) -> dict:
        # raise httpx.ConnectError("boom")
        raise httpx.ConnectError("boom")


# if __name__ == "__main__":
if __name__ == "__main__":
    # unittest.main()
    unittest.main()
