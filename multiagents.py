import asyncio
import os
from dotenv import load_dotenv
import requests
import base64
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

#issue_url = "https://github.com/SWE-agent/test-repo/issues/1"
def convert_web_url_to_api(url: str) -> str:
    """Convert GitHub web URL to GitHub API issue URL"""
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
    """Fetch GitHub issue details using the full API URL"""
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
    """Fetch repository file structure"""
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
    """Fetch specific file content from repository"""
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
                "paradigm": "The programming paradigm used, possible return valeus must be 'Procedural Programming',
                'Objected-Oriented Programming', 'Procedural and Objected-Oriented Programming', 'Simple Text',
            }
            - ALWAYS print the JSON on the terminal
            - NEVER pass incomplete JSON to SWE-Agent - iterate until all fields are filled
            - If you need more information, fetch more files or ask for clarification
            - PLEASE make sure to always provide all the information needed for the SWE-agent to create a patch don't 
            stop iterating until you have all the information for the SWE-Agent, always print the JSON on the terminal and pass info to SWE-Agent
            - Ask for the github issue url to analyze it and never ask for user input again after the first request"""
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
                ```diff
                --- a/[filename]
                +++ b/[filename]  
                @@ -[old_line_start],[old_line_count] +[new_line_start],[new_line_count] @@
                -[removed lines with - prefix]
                +[added lines with + prefix]
                ```

                5. Return a JSON response with:
                {
                "patch": "The diff patch content",
                "filepath": "Path to the file being patched", 
                "solution_description": "Explanation of what the patch does"
                }

                IMPORTANT: Always print the patch and JSON visually on terminal"""
    )

    reviser = AssistantAgent(
        name="reviser",
        llm_config={"config_list": [config], "temperature": 0.7},
        system_message="You review patches and determine if they solve the problem. Respond with 'LGTM 👍' if approved, otherwise go back to "
        "SWE-Agent to create a new proper patch that will fix the error and check again if the patch is correct. Answer with 'LGTM 👍'" \
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

    manager = GroupChatManager(groupchat=groupchat, llm_config={"config_list": [config]})

    user.initiate_chat(
        manager,
        message=f"Analyzer, please fetch and analyze the issue from {issue_url}"
    )

if __name__ == "__main__":
    asyncio.run(main())