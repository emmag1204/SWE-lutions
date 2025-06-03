import json
import os
from dotenv import load_dotenv
import requests
import base64
import yaml
from autogen import AssistantAgent, GroupChat, UserProxyAgent


def convert_web_url_to_api(url: str) -> str:
    """Convert GitHub web URL to GitHub API URL"""
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
    """Fetch GitHub issue details from API"""
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
    """Get repository file and folder structure"""
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
    """Get content of a specific file from repository"""
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


class AnalyzerAgent:
    """Analyzer agent responsible for fetching and analyzing GitHub issues"""
    def __init__(self, config):
        self.config = config
        self.agent = None
        self._load_agent()
        self._register_functions()
        self.user_proxy = None
    
    def _load_agent(self):
        """Load analyzer agent from YAML configuration"""
        try:
            # Try UTF-8 first
            with open("analyzer.yaml", 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except UnicodeDecodeError:
            # If fails, try UTF-8 with BOM
            try:
                with open("analyzer.yaml", 'r', encoding='utf-8-sig') as f:
                    data = yaml.safe_load(f)
            except UnicodeDecodeError:
                # Last resort, use latin-1
                with open("analyzer.yaml", 'r', encoding='latin-1') as f:
                    data = yaml.safe_load(f)
        except FileNotFoundError:
            print("Error: Could not find analyzer.yaml file")
            print("Make sure the file exists in the current directory")
            raise
        
        # Create the agent based on YAML configuration
        self.agent = AssistantAgent(
            name=data["name"],
            system_message=data["system_message"],
            llm_config={
                "config_list": [self.config], 
                "temperature": data.get("temperature", 0.1)
            }
        )
    
    def _register_functions(self):
        print("🔧 Registering functions for the analyzer...")
        self.agent.register_for_execution(name="get_github_issue")(get_github_issue)
        self.agent.register_for_llm(
            description="Fetch GitHub issue details using the full issue API URL"
        )(get_github_issue)

        self.agent.register_for_execution(name="get_repository_structure")(get_repository_structure)
        self.agent.register_for_llm(
            description="Get repository file and folder structure"
        )(get_repository_structure)

        self.agent.register_for_execution(name="get_file_content")(get_file_content)
        self.agent.register_for_llm(
            description="Get content of a specific file from repository"
        )(get_file_content)

        print("✅ Functions registered successfully")

    def _register_functions_user_proxy(self):
        self.user_proxy.register_for_execution(name="get_github_issue")(get_github_issue)
        self.user_proxy.register_for_llm(
            description="Fetch GitHub issue details using the full issue API URL"
        )(get_github_issue)

        self.user_proxy.register_for_execution(name="get_repository_structure")(get_repository_structure)
        self.user_proxy.register_for_llm(
            description="Get repository file and folder structure"
        )(get_repository_structure)

        self.user_proxy.register_for_execution(name="get_file_content")(get_file_content)
        self.user_proxy.register_for_llm(
            description="Get content of a specific file from repository"
        )(get_file_content)

        print("✅ Functions registered successfully")
    
    def get_agent(self):
        """Return the configured analyzer agent"""
        return self.agent
    
    def get_final_dict(self, github_issue_url: str) -> dict:
        """
        Is the main method that initializes the agent, fetches all the necessary data
        until the final dictionary is completed to be returned.
        Final dictionary contains:
        {
            "problem_statement": str,
            "filepath": str or "",
            "paradigm": "Procedural Programming","Objected-Oriented Programming", "Procedural and Objected-Oriented Programming" or "",
            "first_guess": str or ""
        }
        Basically it runs and iterates through GitHub calls until the agent is able to return a valid dictionary.
        """
        print(f"🔍 Analyzing issue: {github_issue_url}")

        result = {}
        valid_paradigms = set([
            "Procedural Programming",
            "Objected-Oriented Programming",
            "Procedural and Objected-Oriented Programming",
            ""
        ])

        try:
            # Convert web URL to API URL
            issue_api_url = convert_web_url_to_api(github_issue_url)
            if "Error" in issue_api_url:
                raise ValueError(issue_api_url)

            # Fetch raw issue data from GitHub
            issue_text = get_github_issue(issue_api_url)

            # Create prompt for agent
            prompt = f"""
You are an assistant analyzing a GitHub issue. Based on the following issue details, return a JSON response with:
1. "problem_statement": clear explanation of the issue
2. "filepath": most likely file(s) to be modified (can be a list or string)
3. "paradigm": programming paradigm involved (OOP, functional, procedural, etc.)
4. "first_guess": your initial thoughts on how the issue might be resolved

Issue:
{issue_text}
            """.strip()

            # Chat session
            self.user_proxy = UserProxyAgent(
                name="user_proxy",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=1,
                code_execution_config=False,
            )
            # Let the analyzer talk to itself
            self.agent.initiate_chat(self.agent, message=prompt)
            history = self.agent.chat_messages[self.agent]


            # Get last response
            history = self.user_proxy.chat_messages[self.agent]
            if not history:
                raise RuntimeError("No response from agent")

            reply = history[-1]['content']

            # Try to extract JSON
            try:
                json_start = reply.find('{')
                json_end = reply.rfind('}') + 1
                json_str = reply[json_start:json_end]
                print(f"🔍 Extracted JSON: {json_str}")
                return json.loads(json_str)
            except Exception:
                print("❌ Failed to parse JSON from agent response")
                print(f"🔍 Agent reply: {reply}")
                return {"problem_statement": reply, "filepath": "", "paradigm": "", "first_guess": ""}

        except Exception as e:
            print(f"❌ Error analyzing issue: {e}")
            return {"problem_statement": str(e), "filepath": "", "paradigm": "", "first_guess": ""}

def create_analyzer_agent(issue_link: str):
    """Factory function to create and return an analyzer agent"""
    config = {
        "api_type": "azure",
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }
    analyzer = AnalyzerAgent(config)
    print("✅ Analyzer agent created successfully")
    groupchat = GroupChat(
        agents=[analyzer.get_agent()],
        messages=[],
        max_round= 10,
    )
    final_dict = analyzer.get_final_dict(issue_link)
    print("🔍 Final analysis result:", final_dict)
    

    return final_dict





# import os
# import re
# import json
# import base64
# import requests
# import yaml
# from typing import Dict, Any
# from autogen import AssistantAgent, UserProxyAgent


# class AnalyzerAgent:
#     def _init_(self, config):
#         print("🔧 Initializing AnalyzerAgent...")
#         self.config = config
#         self.agent = None
#         self.user_proxy = None
#         self._load_agent()
#         print("✅ AnalyzerAgent initialized")

#     def _load_agent(self):
#         try:
#             with open("analyzer.yaml", 'r', encoding='utf-8') as f:
#                 data = yaml.safe_load(f)

#             self.agent = AssistantAgent(
#                 name=data["name"],
#                 system_message=data["system_message"],
#                 llm_config={
#                     "config_list": [self.config],
#                     "temperature": data.get("temperature", 0.1),
#                 }
#             )

#             self.user_proxy = UserProxyAgent(
#                 name="user_proxy",
#                 human_input_mode="NEVER",
#                 max_consecutive_auto_reply=1,
#                 code_execution_config=False,
#             )

#         except Exception as e:
#             raise RuntimeError(f"❌ Failed to load agent: {e}")

#     def _convert_web_url_to_api(self, url: str) -> str:
#         if "github.com" in url and "/issues/" in url:
#             parts = url.split("github.com/")[1].split("/issues/")
#             repo_path = parts[0]
#             issue_number = parts[1]
#             return f"https://api.github.com/repos/{repo_path}/issues/{issue_number}"
#         return url

#     def _fetch_github_issue(self, issue_url: str) -> str:
#         api_url = self._convert_web_url_to_api(issue_url)
#         print(f"🌐 Fetching GitHub issue: {api_url}")
#         try:
#             response = requests.get(api_url)
#             response.raise_for_status()
#             issue_data = response.json()
#             return (
#                 f"Title: {issue_data['title']}\n"
#                 f"State: {issue_data['state']}\n"
#                 f"URL: {issue_data['html_url']}\n"
#                 f"Body:\n{issue_data['body']}"
#             )
#         except Exception as e:
#             return f"❌ Error fetching issue: {e}"

#     def analyze_issue(self, github_issue_url: str) -> Dict[str, Any]:
#         print(f"🔍 Analyzing issue: {github_issue_url}")

#         try:
#             # Fetch raw issue data from GitHub
#             issue_text = self._fetch_github_issue(github_issue_url)

#             # Create prompt for agent
#             prompt = f"""
# You are an assistant analyzing a GitHub issue. Based on the following issue details, return a JSON response with:
# 1. "problem_statement": clear explanation of the issue
# 2. "filepath": most likely file(s) to be modified (can be a list or string)
# 3. "paradigm": programming paradigm involved (OOP, functional, procedural, etc.)
# 4. "first_guess": your initial thoughts on how the issue might be resolved

# Issue:
# {issue_text}
#             """.strip()

#             # Chat session
#             self.user_proxy.initiate_chat(self.agent, message=prompt)

#             # Get last response
#             history = self.user_proxy.chat_messages[self.agent]
#             if not history:
#                 raise RuntimeError("No response from agent")

#             reply = history[-1]['content']

#             # Try to extract JSON
#             try:
#                 json_start = reply.find('{')
#                 json_end = reply.rfind('}') + 1
#                 json_str = reply[json_start:json_end]
#                 return json.loads(json_str)
#             except Exception:
#                 return {
#                     "problem_statement": reply.strip(),
#                     "filepath": "",
#                     "paradigm": "",
#                     "first_guess": ""
#                 }

#         except Exception as e:
#             return {
#                 "problem_statement": f"❌ Error: {str(e)}",
#                 "filepath": "",
#                 "paradigm": "",
#                 "first_guess": ""
#             }


# def analyze_issue(github_issue_url: str) -> Dict[str, Any]:
#     config = {
#         "api_type": "azure",
#         "api_key": os.getenv("AGENTS_API_KEY"),
#         "base_url": os.getenv("AGENTS_API_BASE_URL"),
#         "api_version": os.getenv("AGENTS_API_VERSION"),
#         "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
#     }
#     analyzer = AnalyzerAgent(config)
#     return analyzer.analyze_issue(github_issue_url)


# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 2:
#         print("Usage: python analyzer.py <github_issue_url>")
#         sys.exit(1)

#     issue_url = sys.argv[1]
#     print(f"🚀 Analyzing issue: {issue_url}")
#     result = analyze_issue(issue_url)
#     print("\n=== ANALYSIS RESULT ===")
#     print(json.dumps(result, indent=2))