from dotenv import load_dotenv
import os
import json
import ast
from typing import Dict, Any, List, Optional
import time
import signal
import asyncio
import uuid
from autogen_agentchat.messages import UserMessage
from credentials import az_model_client  # Assumes AzureOpenAIChatCompletionClient

def log_to_file(text, filename="conversation_log.txt"):
    try:
        parsed = json.loads(text)
        text = json.dumps(parsed, indent=4)
    except Exception:
        pass
    with open(filename, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def print_and_log(msg, filename="conversation_log.txt"):
    print(msg)
    with open(filename, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def log_tokens_to_file(usage, operation="generation", filename="conversation_log.txt"):
    prompt = getattr(usage, "prompt_tokens", 0)
    completion = getattr(usage, "completion_tokens", 0)
    total = prompt + completion
    line = f"TOKENS | {operation}: prompt={prompt}, completion={completion}, total={total}"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(line + "\n")

class Agent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.mailbox: List[Dict[str, Any]] = []

    def send_message(self, recipient: 'Agent', message: dict):
        message['sender'] = self.agent_id
        content_str = message.get('content', '')
        try:
            content_str = json.dumps(content_str, indent=4) if isinstance(content_str, (dict, list)) else str(content_str)
        except Exception:
            content_str = str(content_str)
        log_entry = f"SEND | {self.agent_id} -> {recipient.agent_id}: {message['protocol']} | {message.get('action', 'N/A')} | {content_str}"
        print_and_log(log_entry)
        recipient.receive_message(message)

    def receive_message(self, message: dict):
        content_str = message.get('content', '')
        try:
            content_str = json.dumps(content_str, indent=4) if isinstance(content_str, (dict, list)) else str(content_str)
        except Exception:
            content_str = str(content_str)
        log_entry = f"RECEIVE | {self.agent_id} <- {message['sender']}: {message['protocol']} | {message.get('action', 'N/A')} | {content_str}"
        print_and_log(log_entry)
        self.mailbox.append(message)

    async def process_messages(self):
        while self.mailbox:
            message = self.mailbox.pop(0)
            await self.handle_message(message)

    async def handle_message(self, message: dict):
        pass

class BaseReviewer(Agent):
    def __init__(self, agent_id: str, role: str, prompt_template: str):
        super().__init__(agent_id)
        self.role = role
        self.prompt_template = prompt_template

    async def handle_message(self, message: Dict[str, Any]):
        if message['protocol'] == 'A2A' and message['action'] == 'review_code':
            code = message['content']['code']
            feedback = await self.generate_feedback(code)
            feedback['reviewer'] = self.agent_id
            feedback['role'] = self.role
            manager = agent_manager.get_agent_by_id('Manager')
            if manager:
                self.send_message(manager, self.create_review_message(feedback))

    async def generate_feedback(self, code: str) -> Dict[str, Any]:
        prompt = self.prompt_template.format(code=code)
        try:
            result = await az_model_client.create([UserMessage(content=prompt, source="user")])
            feedback_text = None
            if hasattr(result, 'content'):
                feedback_text = result.content.strip()
            elif hasattr(result, 'text'):
                feedback_text = result.text.strip()
            elif hasattr(result, 'choices') and result.choices:
                feedback_text = result.choices[0].message.content.strip()
            else:
                raise AttributeError(f"Unexpected response structure: {result.__dict__}")
            log_tokens_to_file(result.usage, operation="code review")
            print_and_log(f"Debug: LLM response for {self.agent_id}: {feedback_text[:100]}...")
            if feedback_text.startswith("```"):
                feedback_text = feedback_text.split('\n', 1)[1].rsplit('\n', 1)[0].strip()
            try:
                return json.loads(feedback_text)
            except json.JSONDecodeError as e:
                print_and_log(f"JSON parsing error for {self.agent_id}: {e}. Raw response: {feedback_text[:200]}...")
                return {
                    'comments': ['Fallback: Invalid JSON response from LLM.'],
                    'severity': 'medium',
                    'suggested_fix': 'Review code for syntax and structure issues.'
                }
        except Exception as e:
            print_and_log(f"Error generating feedback for {self.agent_id}: {e}")
            return {
                'comments': ['Fallback: Review syntax and structure.'],
                'severity': 'medium',
                'suggested_fix': 'Add proper indentation and error handling.'
            }

    def create_review_message(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'protocol': 'CODE_REVIEW',
            'action': 'provide_feedback',
            'content': feedback
        }

class TLReviewer(BaseReviewer):
    def __init__(self):
        prompt = """
You are a Team Lead reviewing Python code for tactical issues. Focus on syntax errors, style (PEP8), readability, basic bugs, and team standards. Ignore high-level design. If the code is clean and meets standards, explicitly state "Code is clean and meets standards" with severity "low".

Code to review:
{code}

Provide feedback as JSON: {{"comments": ["Bullet-point list of 2-4 specific issues or 'Code is clean and meets standards'"], "severity": "low/medium/high", "suggested_fix": "Brief code snippet or change description."}}

Be concise, actionable, and encouraging.
"""
        super().__init__('TL', 'Team Lead', prompt)

class SAReviewer(BaseReviewer):
    def __init__(self):
        prompt = """
You are a Senior Architect reviewing Python code for system-level concerns. Focus on performance, error handling, security, testing, and robustness. If the code is robust and secure, explicitly state "Code is robust and secure" with severity "low".

Code to review:
{code}

Provide feedback as JSON: {{"comments": ["Bullet-point list of 2-4 system risks or 'Code is robust and secure'"], "severity": "low/medium/high", "suggested_fix": "Brief code or strategy to mitigate."}}

Be rigorous, metrics-driven, and practical.
"""
        super().__init__('SA', 'Senior Architect', prompt)

class LazyDeveloper(Agent):
    def __init__(self):
        super().__init__('LazyDeveloper')
        self.current_code = """
# welcome to chaos 🌀

def why(???):::
print "Welcome to Python 2.8.9.10.11.12"

def def def():
    def = def
    return def

if 10 >> "five":
    print(99999999999999999999999999999999999999999999999999999999999 / "zero")

def mystery_function(x y z):
    x = x++--**//y
    z <<==>> x
    return "result is" x + y + z + π

try:
    do something absolutely nothing maybe?
except:
    catch fire pls

class Confusion:
    def __innit__(self, names, ages, emotions, ):
        self.name = names
        self.age = ages
        self.mood = emotions
        self.feelings = undefinedvariable

    def __str__(self)
        return "My name is" + self.name + "and I am" + self.age + "years happy"

@decorator(that(doesnt)exist)
def decorated_mess:
    print("This is... something")

list = {1, 2, "three", [4, 5], (6: 7)}
for x in list:
    if x in x:
        breakdance()

with open("ghost_file.txt", "invisible") as 💀:
    data = 💀.readlines()
    data.write("this makes no sense")

import thisisnotapackage

print("End of the beginning of the end"

"""

    async def handle_message(self, message: Dict[str, Any]):
        if message['protocol'] == 'A2A' and message['action'] == 'review_code':
            self.current_code = message['content']['code']
            print_and_log(f"{self.agent_id} submitting code:\n{self.current_code}")
            reviewers = ['TL', 'SA']
            for reviewer_id in reviewers:
                reviewer = agent_manager.get_agent_by_id(reviewer_id)
                if reviewer:
                    self.send_message(reviewer, message)
        elif message['protocol'] == 'INSTRUCTION' and message['action'] == 'fix_code':
            comments = message['content'].get('comments', [])
            print_and_log(f"{self.agent_id} received fix instructions from Manager:")
            for c in comments:
                print_and_log(f"- {c}")
            fixed_code = await self.fix_code(comments)
            self.current_code = fixed_code
            print_and_log(f"{self.agent_id} applied fixes. New code preview:\n{self.current_code[:200]}...")
            # Resubmit for review
            review_message = {
                'protocol': 'A2A',
                'action': 'review_code',
                'content': {'code': self.current_code},
                'sender': self.agent_id
            }
            reviewers = ['TL', 'SA']
            for reviewer_id in reviewers:
                reviewer = agent_manager.get_agent_by_id(reviewer_id)
                if reviewer:
                    self.send_message(reviewer, review_message)

    async def fix_code(self, comments):
        aggregated_comments = "\n".join([f"- {comment}" for comment in comments])
        fix_prompt = f"""
You are a Python developer fixing code based on reviews. Rewrite the code to address all issues. Ensure it is executable, clean, and follows PEP8 standards. Output ONLY the fixed code, no explanations.

Original Code:
{self.current_code}

Feedback to Address:
{aggregated_comments}
"""
        try:
            result = await az_model_client.create([UserMessage(content=fix_prompt, source="user")])
            fixed_code = None
            if hasattr(result, 'content'):
                fixed_code = result.content.strip()
            elif hasattr(result, 'text'):
                fixed_code = result.text.strip()
            elif hasattr(result, 'choices') and result.choices:
                fixed_code = result.choices[0].message.content.strip()
            else:
                raise AttributeError(f"Unexpected response structure: {result.__dict__}")
            log_tokens_to_file(result.usage, operation="code fixing")
            print_and_log(f"Debug: LLM response for fixing code: {fixed_code[:100]}...")
            if fixed_code.startswith("```"):
                fixed_code = fixed_code.split('\n', 1)[1].rsplit('\n', 1)[0].strip()
            # Validate syntax
            try:
                ast.parse(fixed_code)
                return fixed_code
            except SyntaxError as e:
                print_and_log(f"Syntax error in fixed code: {e}. Falling back to original.")
                return f"# Syntax error in fixes: {e}\n\n{self.current_code}"
        except Exception as e:
            print_and_log(f"Error fixing code: {e}. Falling back to original.")
            return f"# Error applying fixes: {e}\n\n{self.current_code}"

class ManagerAgent(Agent):
    def __init__(self):
        super().__init__('Manager')
        self.feedbacks = {}
        self.approved_by = {'TL': False, 'SA': False}

    async def handle_message(self, message: Dict[str, Any]):
        if message['protocol'] == 'CODE_REVIEW' and message['action'] == 'provide_feedback':
            reviewer = message['content'].get('reviewer')
            feedback = message['content']
            self.feedbacks[reviewer] = feedback
            print_and_log(f"Manager received feedback from {reviewer}.")

            # Check if reviewer approves the code
            if reviewer in ['TL', 'SA']:
                is_approved = (
                    feedback.get('severity') == 'low' or
                    any("no issues" in comment.lower() or "clean" in comment.lower() or "robust" in comment.lower() for comment in feedback.get('comments', []))
                )
                self.approved_by[reviewer] = is_approved
                print_and_log(f"{reviewer} approval status: {is_approved}")

            required_reviewers = ['TL', 'SA']
            if all(r in self.feedbacks for r in required_reviewers):
                if all(self.approved_by[r] for r in required_reviewers):
                    print_and_log("Both TL and SA approve the code. Stopping review cycle.")
                else:
                    instruction = {
                        'protocol': 'INSTRUCTION',
                        'action': 'fix_code',
                        'content': {
                            'comments': [comment for r in required_reviewers for comment in self.feedbacks[r].get('comments', [])]
                        }
                    }
                    lazy_dev = agent_manager.get_agent_by_id('LazyDeveloper')
                    if lazy_dev:
                        print_and_log("Manager instructing LazyDeveloper to fix code based on feedback.")
                        self.send_message(lazy_dev, instruction)
                self.feedbacks.clear()
                self.approved_by = {'TL': False, 'SA': False}

class AgentManager:
    def __init__(self):
        self.agents = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.agent_id] = agent

    def get_agent_by_id(self, agent_id: str):
        return self.agents.get(agent_id)

    async def process_all_messages(self):
        while any(len(agent.mailbox) > 0 for agent in self.agents.values()):
            for agent in list(self.agents.values()):
                await agent.process_messages()

agent_manager = AgentManager()

lazy_dev = LazyDeveloper()
tl = TLReviewer()
sa = SAReviewer()
manager = ManagerAgent()

agent_manager.register_agent(lazy_dev)
agent_manager.register_agent(tl)
agent_manager.register_agent(sa)
agent_manager.register_agent(manager)

running = True

def signal_handler(sig, frame):
    global running
    print_and_log("\nShutdown signal received. Stopping review cycle...")
    running = False
    asyncio.create_task(az_model_client.close())

signal.signal(signal.SIGINT, signal_handler)

async def main():
    print_and_log("Starting Code Review Agentic System.")
    print_and_log("Submit Ctrl+C to stop after cycle.")

    initial_code = lazy_dev.current_code
    initial_message = {
        'protocol': 'A2A',
        'action': 'review_code',
        'content': {'code': initial_code},
        'sender': 'System'
    }

    lazy_dev.receive_message(initial_message)

    iteration = 1
    max_iterations = 5

    while iteration <= max_iterations and running:
        print_and_log(f"=== Iteration {iteration} ===")
        await agent_manager.process_all_messages()
        if manager.approved_by['TL'] and manager.approved_by['SA']:
            break
        iteration += 1

    print_and_log("Code Review System stopped.")
    print_and_log(f"Final code:\n{lazy_dev.current_code}")

    # Save final code to file
    with open("final_fixed_code.py", "w", encoding="utf-8") as f:
        f.write(lazy_dev.current_code)
    print_and_log("Final code saved to final_fixed_code.py")

if __name__ == "__main__":
    asyncio.run(main())
