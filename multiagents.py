import asyncio
import os
import json
import re
from dotenv import load_dotenv
import requests
import base64
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

def convert_web_url_to_api(url: str) -> str:
    try:
        if "github.com" in url and "/issues/" in url:
            parts = url.split("github.com/")[1].split("/issues/")
            repo_path = parts[0]
            issue_number = parts[1]
            return f"https://api.github.com/repos/{repo_path}/issues/{issue_number}"
        else:
            raise ValueError("URL format not recognized")
    except Exception as e:
        return f"Error converting URL: {str(e)}"

def get_github_issue(issue_url: str) -> str:
    try:
        response = requests.get(issue_url)
        response.raise_for_status()
        issue_data = response.json()

        return f"""
        Title: {issue_data['title']}
        State: {issue_data['state']}
        URL: {issue_data['html_url']}
        Body: {issue_data['body']}
        """
    except Exception as e:
        return f"Error fetching issue: {str(e)}"

def get_repository_structure(repo_owner: str, repo_name: str, path: str = "") -> str:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        contents = response.json()

        structure = []
        for item in contents:
            if item['type'] == 'file':
                structure.append(f"FILE: {item['path']}")
            elif item['type'] == 'dir':
                structure.append(f"DIR: {item['path']}/")
        return "\n".join(structure)
    except Exception as e:
        return f"Error fetching repository structure: {str(e)}"

def get_file_content(repo_owner: str, repo_name: str, file_path: str) -> str:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        file_data = response.json()

        if file_data.get('encoding') == 'base64':
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return f"Content of {file_path}:\n{content}"
        else:
            return f"Could not decode file content for {file_path}"
    except Exception as e:
        return f"Error fetching file {file_path}: {str(e)}"

class AnalyzerDataStore:
    def __init__(self):
        self.json_data = None
        self.raw_content = None
        self.timestamp = None
    
    def save_data(self, json_data, raw_content=None):
        self.json_data = json_data
        self.raw_content = raw_content
        self.timestamp = asyncio.get_event_loop().time()
        
    def get_data(self):
        return {
            'json_data': self.json_data,
            'raw_content': self.raw_content,
            'timestamp': self.timestamp
        }

    def has_data(self):
        return self.json_data is not None

analyzer_store = AnalyzerDataStore()
class CustomGroupChatManager(GroupChatManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.analyzer_json = None
        self.swe_json = None

    def _process_received_message(self, message, sender, silent):
        result = super()._process_received_message(message, sender, silent)

        if hasattr(sender, 'name'):
            content = ""
            if isinstance(message, dict):
                content = message.get('content', '') or str(message)
            elif isinstance(message, str):
                content = message
            else:
                content = str(message)

            if sender.name == "analyzer":
                match = re.search(r"\{[\s\S]*?\}", content)
                if match:
                    try:
                        analyzer_json = json.loads(match.group())
                        self.analyzer_json = analyzer_json
                        with open("analyzer_output.json", "w") as f:
                            json.dump(analyzer_json, f, indent=2)
                    except Exception as e:
                        print(f"Error parsing analyzer JSON: {e}")

            elif sender.name == "swe_agent":
                match = re.search(r"\{[\s\S]*?\}", content)
                if match:
                    try:
                        swe_json = json.loads(match.group())
                        with open("swe_agent_output.json", "w") as f:
                            json.dump(swe_json, f, indent=2)
                        reviser_agent = None
                        for agent in self.groupchat.agents:
                            if agent.name == "reviser":
                                reviser_agent = agent
                                break
                        if reviser_agent:
                            swe_message = json.dumps(swe_json, indent=2)
                            self.groupchat.send_message(
                                sender=self.groupchat.get_agent_by_name("swe_agent"),
                                recipient=reviser_agent,
                                message=swe_message
                            )
                            print("Sent SWE JSON output to reviser.")
                        else:
                            print("Reviser agent not found in groupchat.")

                    except Exception as e:
                        print(f"Error parsing SWE JSON: {e}")
        return result

    def get_analyzer_data(self):
        return self.analyzer_json

    def get_swe_data(self):
        return self.swe_json

async def main():
    load_dotenv()
    user_input_url = input("Enter GitHub issue url: ").strip()
    issue_url = convert_web_url_to_api(user_input_url)

    config = {
        "api_type": "azure",
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }

    analyzer = AssistantAgent(
        name="analyzer",
        llm_config={"config_list": [config], "temperature": 0.1},
        system_message="""You are a GitHub issue analyzer. Your job is to:

            1. Fetch GitHub issue details using get_github_issue function
            2. Get repository structure using get_repository_structure function  
            3. Get specific file content using get_file_content function
            4. Analyze the issue and identify the problematic file path
            5. Create a JSON analysis with ALL required fields filled

            IMPORTANT RULES:
            - ALWAYS say "This might be the filepath of the issue: [filepath]" when you identify a potential problematic file
            - ALWAYS fetch as much repository code as possible to understand the context
            - ALWAYS return a complete JSON file to the SWE agent with these exact fields:
            {
                "problem_statement": "Clear description of the issue",
                "filepath": "Path to the problematic file", 
                "first_guess": "Your hypothesis about what's wrong",
                "paradigm": "The programming paradigm used, possible return values must be 'Procedural Programming',
                'Objected-Oriented Programming', 'Procedural and Objected-Oriented Programming', 'Simple Text',
            }
            - ALWAYS print the JSON on the terminal
            - NEVER pass incomplete JSON to SWE-Agent - iterate until all fields are filled
            - If you need more information, fetch more files or ask for clarification
            - PLEASE make sure to always provide all the information needed for the SWE-agent to create a patch don't 
              stop iterating until you have all the information for the SWE-Agent"""
    )

    analyzer.register_for_execution(name="get_github_issue")(get_github_issue)
    analyzer.register_for_llm(description="Fetch GitHub issue details using the full issue API URL")(get_github_issue)
    analyzer.register_for_execution(name="get_repository_structure")(get_repository_structure)
    analyzer.register_for_llm(description="Get repository file and folder structure")(get_repository_structure)
    analyzer.register_for_execution(name="get_file_content")(get_file_content)
    analyzer.register_for_llm(description="Get content of a specific file from repository")(get_file_content)

    swe_agent = AssistantAgent(
        name="swe_agent",
        llm_config={"config_list": [config], "temperature": 0.1},
        system_message="""You're a software engineer. When you receive a JSON analysis from the analyzer:
            1. Read the problem_statement, filepath, first_guess, and paradigm
            2. Create a code fix/patch for the issue
            3. Format your response as a proper patch in diff format
            4. ALWAYS print the patch in this exact format:

            **Patch**:
            
            diff
            --- a/[filename]
            +++ b/[filename]  
            @@ -[old_line_start],[old_line_count] +[new_line_start],[new_line_count] @@
            -[removed lines with - prefix]
            +[added lines with + prefix]


            5. Return a JSON response with:
            {
                "patch": "The diff patch content",
                "filepath": "Path to the file being patched", 
                "solution_description": "Explanation of what the patch does"
                "problem_statement": "The problem statement from the analyzer"
            }

           """
    )

    reviser = AssistantAgent(
        name="reviser",
        llm_config={"config_list": [config], "temperature": 0.7},
        system_message="You review patches and determine if they solve the problem. Respond with 'LGTM 👍' if approved, otherwise go back to "
                       "SWE-Agent to create a new proper patch that will fix the error and check again if the patch is correct. Answer with 'LGTM 👍'"
                       "Don't ask for human input after approving the patch, just end the iteration."
    )

    user = UserProxyAgent(
        name="user",
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: "LGTM" in x.get("content", "") or "👍" in x.get("content", "")
    )

    groupchat = GroupChat(
        agents=[user, analyzer, swe_agent, reviser],
        messages=[],
        max_round=20
    )

    manager = CustomGroupChatManager(groupchat=groupchat, llm_config={"config_list": [config], "temperature": 0.5})
    user.initiate_chat(
        manager,
        message=f"Analyzer, please fetch and analyze the issue from {issue_url}"
    )

if __name__ == "__main__":
    asyncio.run(main())